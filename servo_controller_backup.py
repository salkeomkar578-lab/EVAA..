from adafruit_pca9685 import PCA9685
from board import SCL, SDA
import busio
from adafruit_motor import servo

I2C_ADDRESS = 0x40
PWM_FREQ = 50

CHANNELS = {
    "LR": 0,
    "UD": 1,
    "TL": 2,
    "BaseX": 3,
    "TR": 4,
    "BaseY": 5,
}

LIMITS = {
    "LR": (40, 140),
    "UD": (40, 140),
    "TL": (90, 170),
    "TR": (10, 90),
    "BaseX": (10, 170),
    "BaseY": (40, 140),
}

CENTER = {
    "LR": 90, "UD": 90, "TL": 90,
    "TR": 90, "BaseX": 90, "BaseY": 90,
}

class FollowerServos:
    def __init__(self):
        i2c = busio.I2C(SCL, SDA)
        self.pca = PCA9685(i2c, address=I2C_ADDRESS)
        self.pca.frequency = PWM_FREQ
        self.motors = {}
        for name, channel in CHANNELS.items():
            self.motors[name] = servo.Servo(
                self.pca.channels[channel],
                min_pulse=500,
                max_pulse=2500
            )
        self.positions = CENTER.copy()

    def clamp(self, name, angle):
        lo, hi = LIMITS[name]
        return max(lo, min(hi, angle))

    def set(self, name, angle):
        angle = self.clamp(name, angle)
        self.positions[name] = float(angle)
        self.motors[name].angle = angle

    def center_all(self):
        for name in CHANNELS:
            self.set(name, CENTER[name])

    def close(self):
        self.pca.deinit()
