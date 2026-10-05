import cv2
from picamera2 import Picamera2

print('OpenCV:', cv2.__version__)
print('FaceDetectorYN:', hasattr(cv2, 'FaceDetectorYN'))
print('FaceRecognizerSF:', hasattr(cv2, 'FaceRecognizerSF'))
picam2 = Picamera2()
print('Picamera2: OK')
picam2.close()
