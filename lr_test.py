import time
import busio
from board import SCL, SDA
from adafruit_pca9685 import PCA9685
from adafruit_motor import servo

I2C_ADDRESS = 0x40
CHANNEL = 0
REST = 90

i2c = busio.I2C(SCL, SDA)
pca = PCA9685(i2c, address=I2C_ADDRESS)
pca.frequency = 50

motor = servo.Servo(
    pca.channels[CHANNEL],
    min_pulse=500,
    max_pulse=2500
)

def move(angle):
    motor.angle = max(0, min(180, angle))

def rest():
    move(REST)
    time.sleep(0.8)

try:
    rest()

    print("LR SERVO TEST")
    print("1 = Left")
    print("2 = Right")
    print("q = Quit")

    choice = input("Select direction: ").strip().lower()

    if choice == "1":
        angle = REST
        print("Moving LEFT. Press Ctrl+C at physical limit.")

        while angle > 0:
            angle -= 0.5
            move(angle)
            print(f"\rAngle: {angle:6.1f}°", end="")
            time.sleep(0.04)

    elif choice == "2":
        angle = REST
        print("Moving RIGHT. Press Ctrl+C at physical limit.")

        while angle < 180:
            angle += 0.5
            move(angle)
            print(f"\rAngle: {angle:6.1f}°", end="")
            time.sleep(0.04)

finally:
    print("\nReturning LR to rest...")
    rest()
    pca.deinit()