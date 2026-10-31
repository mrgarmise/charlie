import threading
import time
import urllib.request

import cv2
import numpy as np


class _ElegooCameraDevice:
    """
    Threaded MJPEG reader for the ELEGOO camera.

    A background thread continuously consumes the stream and keeps
    only the newest decoded frame. This prevents stale buffered
    frames from being processed after slow servo/motor commands.
    """

    def __init__(
        self,
        stream_url="http://192.168.4.1:81/stream",
        timeout=10,
        user_agent="CharlieVision/3.0",
    ):
        self.stream_url = stream_url
        self.timeout = timeout
        self.user_agent = user_agent

        self.response = None
        self.buffer = bytearray()

        self._running = False
        self._thread = None

        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)

        self._latest_frame = None
        self._frame_id = 0
        self._last_read_id = 0

        self._error = None
        self._received_at = None
        self._generation = 0
        self._closed = False
        self._ownership = None

    def open(self):
        if self._running:
            return

        self.close()  # Release a previous failed stream before reconnecting.
        if self._thread is not None and self._thread.is_alive():
            raise TimeoutError("previous camera reader has not stopped")
        self._closed = False
        request = urllib.request.Request(
            self.stream_url,
            headers={
                "User-Agent": self.user_agent
            },
        )

        from hardware.camera_ownership import ElegooCameraLease
        self._ownership = ElegooCameraLease(self.stream_url)
        try:
            self.response = urllib.request.urlopen(request, timeout=self.timeout)
        except BaseException:
            self._ownership.close()
            self._ownership = None
            raise

        self.buffer = bytearray()
        self._error = None
        with self._condition:
            self._latest_frame = None
            self._received_at = None
        self._running = True

        self._thread = threading.Thread(
            target=self._reader_loop,
            args=(self.response, self._generation),
            name="ElegooCameraRX",
            daemon=True,
        )
        self._thread.start()

    def close(self):
        self._closed = True
        self._generation += 1
        self._running = False

        response = self.response
        self.response = None

        if response is not None:
            try:
                response.close()
            except Exception:
                pass

        if self._thread is not None:
            self._thread.join(timeout=1)
            if not self._thread.is_alive():
                self._thread = None

        if self._ownership is not None and self._thread is None:
            self._ownership.close()
            self._ownership = None
        with self._condition:
            self._condition.notify_all()

    def _reader_loop(self, response=None, generation=None):
        response = response or self.response
        generation = self._generation if generation is None else generation
        try:
            while self._running and generation == self._generation:
                chunk = response.read(4096)

                if not chunk:
                    raise EOFError(
                        "Elegoo camera stream ended"
                    )

                self.buffer.extend(chunk)
                if len(self.buffer) > 2 * 1024 * 1024:
                    raise ValueError("MJPEG frame exceeds bounded buffer")

                while True:
                    jpg_start = self.buffer.find(
                        b"\xff\xd8"
                    )
                    jpg_end = self.buffer.find(
                        b"\xff\xd9"
                    )

                    if (
                        jpg_start == -1
                        or jpg_end == -1
                    ):
                        break

                    if jpg_end < jpg_start:
                        del self.buffer[
                            :jpg_end + 2
                        ]
                        continue

                    jpg = bytes(
                        self.buffer[
                            jpg_start:jpg_end + 2
                        ]
                    )

                    del self.buffer[
                        :jpg_end + 2
                    ]

                    frame = cv2.imdecode(
                        np.frombuffer(
                            jpg,
                            dtype=np.uint8,
                        ),
                        cv2.IMREAD_COLOR,
                    )

                    if frame is None:
                        continue

                    # Store only the newest frame. Older frames are
                    # intentionally discarded.
                    with self._condition:
                        if generation != self._generation:return
                        self._received_at = time.monotonic()
                        self._latest_frame = frame
                        self._frame_id += 1
                        self._condition.notify_all()

        except Exception as exc:
            if generation == self._generation:self._error = exc

        finally:
            if generation == self._generation:self._running = False

            with self._condition:
                self._condition.notify_all()

    def read(
        self,
        timeout=2.0,
        require_new=True,
        with_metadata=False,
    ):
        """
        Return the latest decoded frame.

        require_new=True means wait for a frame newer than the one
        returned by the previous read(), preventing repeated analysis
        of the same image.
        """
        if not self._running:
            self.open()

        deadline = time.monotonic() + timeout

        with self._condition:
            while True:
                if self._error is not None:
                    raise self._error

                if self._closed:
                    raise InterruptedError("camera closed")

                has_frame = (
                    self._latest_frame
                    is not None
                )

                is_new = (
                    self._frame_id
                    > self._last_read_id
                )

                if has_frame and (
                    is_new or not require_new
                ):
                    frame = (
                        self._latest_frame.copy()
                    )

                    self._last_read_id = (
                        self._frame_id
                    )

                    if with_metadata:
                        return frame, dict(sequence=self._frame_id, received_at=self._received_at,
                            clock_domain="pi-monotonic", stream_generation=self._generation, captured_at_source=None,
                            sync_uncertainty_seconds=None, compression="MJPEG")
                    return frame

                remaining = (
                    deadline
                    - time.monotonic()
                )

                if remaining <= 0:
                    raise TimeoutError(
                        "Timed out waiting for "
                        "fresh Elegoo camera frame"
                    )

                self._condition.wait(
                    timeout=remaining
                )

    def discard_until_new(
        self,
        frame_count=2,
        timeout=2.0,
    ):
        """
        Wait through a few fresh camera frames after a physical
        head/chassis movement.

        Because the reader thread is always draining the network
        stream, these are genuinely current frames rather than a
        TCP backlog.
        """
        frame = None

        for _ in range(frame_count):
            frame = self.read(
                timeout=timeout,
                require_new=True,
            )

        return frame

    def __enter__(self):
        self.open()
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        tb,
    ):
        self.close()


class ElegooCamera:
    """Compatibility subscriber; only the application feeder opens the MJPEG URL."""
    def __init__(self,stream_url='http://192.168.4.1:81/stream',timeout=10,user_agent='CharlieVision/3.0'):
        self.is_subscription=True
        self.stream_url,self.timeout=stream_url,timeout
        self.subscription=None
        self.closed=False
        self._last_frame=None

    def open(self):
        if self.subscription is None:
            from stimulus.bus import subscribe_to_frames
            self.subscription=subscribe_to_frames('elegoo-v4')
            self.closed=False

    def read(self,timeout=2.,require_new=True,with_metadata=False):
        if self.closed:raise InterruptedError('camera subscription closed')
        self.open()
        frame=self.subscription.wait(timeout=min(timeout,5))
        from urllib.parse import urlsplit
        identity=frame.camera_identity or {}
        endpoint=identity.get('endpoint')
        if endpoint and urlsplit(endpoint).hostname!=urlsplit(self.stream_url).hostname:
            raise ValueError('subscribed ELEGOO endpoint identity mismatch')
        self._last_frame=frame
        image=frame.image.copy()
        if with_metadata:
            return image,dict(sequence=frame.sequence,received_at=frame.received_at,
                clock_domain=frame.clock_domain,stream_generation=frame.stream_generation,
                captured_at_source=frame.captured_at_source,sync_uncertainty_seconds=frame.sync_uncertainty_seconds,
                compression=frame.compression)
        return image

    def discard_until_new(self,frame_count=2,timeout=2.):
        frame=None
        for _ in range(frame_count):frame=self.read(timeout=timeout)
        return frame

    def close(self):
        if self.subscription is not None:self.subscription.close()
        self.subscription=None
        self.closed=True
    def __enter__(self):self.open();return self
    def __exit__(self,*args):self.close()
