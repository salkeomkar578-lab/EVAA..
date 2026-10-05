from pathlib import Path
import argparse
import json
import time
import cv2
from picamera2 import Picamera2

ROOT = Path(__file__).resolve().parents[1]
YUNET = ROOT / "models" / "face_detection_yunet_2023mar.onnx"
SFACE = ROOT / "models" / "face_recognition_sface_2021dec.onnx"
DB = ROOT / "data" / "faces.json"

parser = argparse.ArgumentParser()
parser.add_argument("--name", required=True)
args = parser.parse_args()

if not YUNET.exists() or not SFACE.exists():
    raise SystemExit("Missing models. Run: bash scripts/download_models.sh")

picam2 = Picamera2()
config = picam2.create_preview_configuration(main={"size": (640, 480), "format": "RGB888"})
picam2.configure(config)
picam2.start()
time.sleep(1)

frame = cv2.cvtColor(picam2.capture_array(), cv2.COLOR_RGB2BGR)
h, w = frame.shape[:2]
detector = cv2.FaceDetectorYN.create(str(YUNET), "", (w, h), 0.8, 0.3, 5000)
recognizer = cv2.FaceRecognizerSF.create(str(SFACE), "", 0, 0)

samples = []
last_capture = 0.0

try:
    while len(samples) < 8:
        frame = cv2.cvtColor(picam2.capture_array(), cv2.COLOR_RGB2BGR)
        detector.setInputSize((frame.shape[1], frame.shape[0]))
        _, faces = detector.detect(frame)

        if faces is not None and len(faces) == 1:
            face = faces[0]
            x, y, fw, fh = map(int, face[:4])
            cv2.rectangle(frame, (x, y), (x + fw, y + fh), (0, 255, 0), 2)
            cv2.putText(frame, f"Samples {len(samples)}/8 - move slightly", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
            if time.time() - last_capture > 0.6:
                aligned = recognizer.alignCrop(frame, face)
                feature = recognizer.feature(aligned)
                samples.append(feature.flatten().tolist())
                last_capture = time.time()
        else:
            cv2.putText(frame, "Show exactly one face", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)

        cv2.imshow("FollowerBot - Enroll Face", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            raise SystemExit("Enrollment cancelled")
finally:
    picam2.stop()
    cv2.destroyAllWindows()

DB.parent.mkdir(parents=True, exist_ok=True)
if DB.exists():
    database = json.loads(DB.read_text())
else:
    database = {}

database[args.name] = {"features": samples}
DB.write_text(json.dumps(database))
print(f"Saved {len(samples)} samples for {args.name} -> {DB}")
