import time
import busio
from board import SCL, SDA
from adafruit_pca9685 import PCA9685
from adafruit_motor import servo

I2C_ADDRESS = 0x40
CHANNEL = 5

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

def return_rest():
    move(REST)
    time.sleep(0.8)

try:
    print()
    print("BASE Y SERVO TEST")
    print("=================")
    print("Rest position: 90 degrees")
    print()
    print("1 = Rotate UP")
    print("2 = Rotate DOWN")
    print("q = Quit")
    print()

    return_rest()

    choice = input("Select direction: ").strip().lower()

    if choice == "1":

        print()
        print("BASE Y ROTATING UP")
        print("Press Ctrl+C immediately when the physical limit is reached.")
        print()

        angle = REST

        while angle > 0:
            angle -= 0.5
            move(angle)
            print(f"\rAngle: {angle:6.1f}°", end="")
            time.sleep(0.04)

    elif choice == "2":

        print()
        print("BASE Y ROTATING DOWN")
        print("Press Ctrl+C immediately when the physical limit is reached.")
        print()

        angle = REST

        while angle < 180:
            angle += 0.5
            move(angle)
            print(f"\rAngle: {angle:6.1f}°", end="")
            time.sleep(0.04)

    else:
        print("Cancelled.")

except KeyboardInterrupt:

    print()
    print()
    print("Physical limit reached / test stopped.")

finally:

    print("Returning BaseY to rest position...")
    return_rest()

    time.sleep(0.5)

    pca.deinit()

    print("BaseY is at rest position.")