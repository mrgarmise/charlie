import urllib.request
import cv2
import numpy as np


class ElegooCamera:
    """
    MJPEG camera on the ELEGOO car.

    Proven stream endpoint:
        http://192.168.4.1:81/stream
    """

    def __init__(
        self,
        stream_url="http://192.168.4.1:81/stream",
        timeout=10,
        user_agent="CharlieVision/2.0",
    ):
        self.stream_url = stream_url
        self.timeout = timeout
        self.user_agent = user_agent

        self.response = None
        self.buffer = bytearray()

    def open(self):
        if self.response is not None:
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

    def close(self):
        if self.response is not None:
            try:
                self.response.close()
            except Exception:
                pass

        self.response = None

    def read(self):
        """
        Return one decoded BGR frame.

        This follows the proven JPEG marker parsing used in the
        Mint diagnostics and face tracker.
        """
        if self.response is None:
            self.open()

        while True:
            jpg_start = self.buffer.find(b"\xff\xd8")
            jpg_end = self.buffer.find(b"\xff\xd9")

            if (
                jpg_start != -1
                and jpg_end != -1
            ):
                if jpg_end < jpg_start:
                    del self.buffer[:jpg_end + 2]
                    continue

                jpg = bytes(
                    self.buffer[
                        jpg_start:jpg_end + 2
                    ]
                )

                del self.buffer[:jpg_end + 2]

                frame = cv2.imdecode(
                    np.frombuffer(
                        jpg,
                        dtype=np.uint8,
                    ),
                    cv2.IMREAD_COLOR,
                )

                if frame is not None:
                    return frame

            chunk = self.response.read(4096)

            if not chunk:
                raise EOFError(
                    "Elegoo camera stream ended"
                )

            self.buffer.extend(chunk)

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
