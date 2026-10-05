from pathlib import Path
import cv2
from picamera2 import Picamera2

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "models" / "face_detection_yunet_2023mar.onnx"

if not MODEL.exists():
    raise SystemExit("Missing YuNet model. Run: bash scripts/download_models.sh")

picam2 = Picamera2()
config = picam2.create_preview_configuration(main={"size": (640, 480), "format": "RGB888"})
picam2.configure(config)
picam2.start()

frame = picam2.capture_array()
h, w = frame.shape[:2]
detector = cv2.FaceDetectorYN.create(str(MODEL), "", (w, h), 0.75, 0.3, 5000)

try:
    while True:
        frame = picam2.capture_array()
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        detector.setInputSize((frame.shape[1], frame.shape[0]))
        _, faces = detector.detect(frame)

        if faces is not None:
            for face in faces:
                x, y, fw, fh = map(int, face[:4])
                conf = float(face[14])
                cv2.rectangle(frame, (x, y), (x + fw, y + fh), (0, 255, 0), 2)
                cv2.putText(frame, f"Face {conf:.2f}", (x, max(20, y - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                cx = x + fw // 2
                cy = y + fh // 2
                cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)

        cv2.imshow("FollowerBot - Face Detection", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
finally:
    picam2.stop()
    cv2.destroyAllWindows()
