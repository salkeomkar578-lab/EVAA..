#!/bin/bash
python3 -m pip install --break-system-packages \
  adafruit-blinka \
  adafruit-circuitpython-pca9685 \
  adafruit-circuitpython-motor
echo "Done. Enable I2C with: sudo raspi-config"
