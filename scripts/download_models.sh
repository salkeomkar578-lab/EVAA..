#!/bin/bash
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/models"
cd "$ROOT/models"

YUNET_URL="https://github.com/opencv/opencv_zoo/raw/refs/heads/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
SFACE_URL="https://github.com/opencv/opencv_zoo/raw/refs/heads/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"

if [ ! -f face_detection_yunet_2023mar.onnx ]; then
  wget -O face_detection_yunet_2023mar.onnx "$YUNET_URL"
fi

if [ ! -f face_recognition_sface_2021dec.onnx ]; then
  wget -O face_recognition_sface_2021dec.onnx "$SFACE_URL"
fi

ls -lh *.onnx
