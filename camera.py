import threading
import time

from picamera2 import Picamera2
from libcamera import Transform


class FastCamera:

    def __init__(self, width=640, height=480):

        self.picam2 = Picamera2()

        config = self.picam2.create_video_configuration(
            main={
                "size": (width, height),
                "format": "RGB888"
            },
            transform=Transform(
                hflip=1,
                vflip=1
            ),
            controls={
                "FrameRate": 45
            },
            buffer_count=2
        )

        self.picam2.configure(config)

        self.picam2.set_controls({
            "ColourGains": (1.0, 1.0)
        })

        self.picam2.start()

        self.running = True
        self.frame = None
        self.lock = threading.Lock()

        self.thread = threading.Thread(
            target=self._capture_loop,
            daemon=True
        )

        self.thread.start()

    def _capture_loop(self):

        while self.running:

            try:

                frame = self.picam2.capture_array(
                    "main"
                )

                with self.lock:
                    self.frame = frame

            except Exception:

                if self.running:
                    time.sleep(0.002)

    def read(self):

        while self.running:

            with self.lock:

                if self.frame is not None:
                    return self.frame.copy()

            time.sleep(0.001)

        return None

    def stop(self):

        self.running = False

        try:
            self.thread.join(timeout=1.0)
        except Exception:
            pass

        try:
            self.picam2.stop()
        except Exception:
            pass


def start_camera(width=640, height=480):

    return FastCamera(
        width,
        height
    )


def get_frame(camera):

    return camera.read()
