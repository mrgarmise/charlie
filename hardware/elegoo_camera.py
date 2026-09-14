import threading
import time
import urllib.request

import cv2
import numpy as np


class ElegooCamera:
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

    def open(self):
        if self._running:
            return

        request = urllib.request.Request(
            self.stream_url,
            headers={
                "User-Agent": self.user_agent
            },
        )

        self.response = urllib.request.urlopen(
            request,
            timeout=self.timeout,
        )

        self.buffer = bytearray()
        self._error = None
        self._running = True

        self._thread = threading.Thread(
            target=self._reader_loop,
            name="ElegooCameraRX",
            daemon=True,
        )
        self._thread.start()

    def close(self):
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
            self._thread = None

        with self._condition:
            self._condition.notify_all()

    def _reader_loop(self):
        try:
            while self._running:
                chunk = self.response.read(4096)

                if not chunk:
                    raise EOFError(
                        "Elegoo camera stream ended"
                    )

                self.buffer.extend(chunk)

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
                        self._latest_frame = frame
                        self._frame_id += 1
                        self._condition.notify_all()

        except Exception as exc:
            self._error = exc

        finally:
            self._running = False

            with self._condition:
                self._condition.notify_all()

    def read(
        self,
        timeout=2.0,
        require_new=True,
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
