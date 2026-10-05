from picamera2 import Picamera2
from libcamera import Transform
import cv2

picam2 = Picamera2()

config = picam2.create_preview_configuration(
    main={"size": (640, 480), "format": "RGB888"},
    transform=Transform(hflip=1, vflip=1)
)

picam2.configure(config)
picam2.start()

try:
    while True:
        frame = picam2.capture_array()

        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        cv2.imshow("FollowerBot Camera", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

except KeyboardInterrupt:
    pass

finally:
    picam2.stop()
    cv2.destroyAllWindows()
