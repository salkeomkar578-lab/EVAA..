from pathlib import Path
import json
import time
import cv2
from picamera2 import Picamera2

ROOT = Path(__file__).resolve().parents[1]
YUNET = ROOT / "models" / "face_detection_yunet_2023mar.onnx"
SFACE = ROOT / "models" / "face_recognition_sface_2021dec.onnx"
DB = ROOT / "data" / "faces.json"
COSINE_THRESHOLD = 0.363

if not YUNET.exists() or not SFACE.exists():
    raise SystemExit("Missing models. Run: bash scripts/download_models.sh")
if not DB.exists():
    raise SystemExit("No face database. First run: python scripts/enroll_face.py --name YOUR_NAME")

database = json.loads(DB.read_text())
if not database:
    raise SystemExit("Face database is empty")

picam2 = Picamera2()
config = picam2.create_preview_configuration(main={"size": (640, 480), "format": "RGB888"})
picam2.configure(config)
picam2.start()
time.sleep(1)

frame = cv2.cvtColor(picam2.capture_array(), cv2.COLOR_RGB2BGR)
h, w = frame.shape[:2]
detector = cv2.FaceDetectorYN.create(str(YUNET), "", (w, h), 0.8, 0.3, 5000)
recognizer = cv2.FaceRecognizerSF.create(str(SFACE), "", 0, 0)

reference_features = []
for name, record in database.items():
    reference_features.append((name, record["features"]))

try:
    while True:
        frame = cv2.cvtColor(picam2.capture_array(), cv2.COLOR_RGB2BGR)
        detector.setInputSize((frame.shape[1], frame.shape[0]))
        _, faces = detector.detect(frame)

        if faces is not None:
            for face in faces:
                x, y, fw, fh = map(int, face[:4])
                aligned = recognizer.alignCrop(frame, face)
                feature = recognizer.feature(aligned)

                best_name = "Unknown"
                best_score = -1.0
                for name, samples in reference_features:
                    for sample in samples:
                        ref = __import__("numpy").array(sample, dtype="float32").reshape(1, -1)
                        score = float(recognizer.match(ref, feature, 0))
                        if score > best_score:
                            best_score = score
                            best_name = name

                known = best_score >= COSINE_THRESHOLD
                label = f"{best_name} {best_score:.3f}" if known else f"Unknown {best_score:.3f}"
                color = (0, 255, 0) if known else (0, 0, 255)
                cv2.rectangle(frame, (x, y), (x + fw, y + fh), color, 2)
                cv2.putText(frame, label, (x, max(20, y - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        cv2.imshow("FollowerBot - Face Recognition", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
finally:
    picam2.stop()
    cv2.destroyAllWindows()
