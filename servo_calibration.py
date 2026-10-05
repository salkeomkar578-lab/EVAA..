import time
import json
import os
import curses
import busio

from board import SCL, SDA
from adafruit_pca9685 import PCA9685
from adafruit_motor import servo

I2C_ADDRESS = 0x40
PWM_FREQ = 50

CHANNELS = {
    "LR": 0,
    "UD": 1,
    "TL": 2,
    "BaseX": 3,
    "TR": 4,
    "BaseY": 5
}

SERVOS = [
    "LR",
    "UD",
    "TL",
    "BaseX",
    "TR",
    "BaseY"
]

positions = {
    "LR": 90,
    "UD": 90,
    "TL": 90,
    "BaseX": 90,
    "TR": 90,
    "BaseY": 90
}

calibration = {}

for name in SERVOS:
    calibration[name] = {
        "left": 90,
        "center": 90,
        "right": 90
    }

CAL_FILE = "servo_calibration.json"

i2c = busio.I2C(SCL, SDA)

pca = PCA9685(
    i2c,
    address=I2C_ADDRESS
)

pca.frequency = PWM_FREQ

motors = {}

for name in SERVOS:

    motors[name] = servo.Servo(
        pca.channels[CHANNELS[name]],
        min_pulse=500,
        max_pulse=2500
    )


def set_servo(name, angle):

    angle = max(0, min(180, angle))

    positions[name] = angle

    motors[name].angle = angle


def center_all():

    for name in SERVOS:
        set_servo(name, 90)


def save_calibration():

    with open(CAL_FILE, "w") as f:
        json.dump(calibration, f, indent=4)


def blink_test():

    tl_open = calibration["TL"]["left"]
    tl_closed = calibration["TL"]["right"]

    tr_open = calibration["TR"]["right"]
    tr_closed = calibration["TR"]["left"]

    steps = 30

    for i in range(steps + 1):

        t = i / steps

        tl = tl_open + (tl_closed - tl_open) * t
        tr = tr_open + (tr_closed - tr_open) * t

        set_servo("TL", tl)
        set_servo("TR", tr)

        time.sleep(0.02)

    time.sleep(0.25)

    for i in range(steps + 1):

        t = i / steps

        tl = tl_closed + (tl_open - tl_closed) * t
        tr = tr_closed + (tr_open - tr_closed) * t

        set_servo("TL", tl)
        set_servo("TR", tr)

        time.sleep(0.02)


def main(stdscr):

    curses.curs_set(0)

    stdscr.nodelay(True)

    selected = 0

    center_all()

    while True:

        key = stdscr.getch()

        if key == ord("q"):
            break

        if key == curses.KEY_RIGHT:
            selected += 1

            if selected >= len(SERVOS):
                selected = 0

        if key == curses.KEY_LEFT:
            selected -= 1

            if selected < 0:
                selected = len(SERVOS) - 1

        name = SERVOS[selected]

        if key == curses.KEY_UP:

            set_servo(
                name,
                positions[name] + 1
            )

        if key == curses.KEY_DOWN:

            set_servo(
                name,
                positions[name] - 1
            )

        if key == ord("a"):

            calibration[name]["left"] = positions[name]

        if key == ord("c"):

            calibration[name]["center"] = positions[name]

        if key == ord("d"):

            calibration[name]["right"] = positions[name]

        if key == ord("s"):

            save_calibration()

        if key == ord("b"):

            blink_test()

        if key == ord("x"):

            center_all()

        stdscr.erase()

        stdscr.addstr(
            0,
            0,
            "FOLLOWER ROBOT - MANUAL SERVO CALIBRATION"
        )

        stdscr.addstr(
            2,
            0,
            "Selected Servo: " + name
        )

        stdscr.addstr(
            3,
            0,
            "Angle: %.1f degrees" % positions[name]
        )

        stdscr.addstr(5, 0, "SERVOS")

        for i, servo_name in enumerate(SERVOS):

            marker = " <--" if i == selected else ""

            stdscr.addstr(
                6 + i,
                0,
                "%-6s %.1f%s"
                % (
                    servo_name,
                    positions[servo_name],
                    marker
                )
            )

        stdscr.addstr(
            14,
            0,
            "LEFT/RIGHT : Select servo"
        )

        stdscr.addstr(
            15,
            0,
            "UP/DOWN    : Move servo 1 degree"
        )

        stdscr.addstr(
            16,
            0,
            "A          : Save LEFT endpoint"
        )

        stdscr.addstr(
            17,
            0,
            "C          : Save CENTER"
        )

        stdscr.addstr(
            18,
            0,
            "D          : Save RIGHT endpoint"
        )

        stdscr.addstr(
            19,
            0,
            "S          : Save calibration file"
        )

        stdscr.addstr(
            20,
            0,
            "B          : Test complete blink"
        )

        stdscr.addstr(
            21,
            0,
            "X          : Center all"
        )

        stdscr.addstr(
            22,
            0,
            "Q          : Quit"
        )

        stdscr.addstr(
            24,
            0,
            "WARNING: Stop moving when the mechanism reaches its physical end."
        )

        stdscr.refresh()

        time.sleep(0.02)


try:

    curses.wrapper(main)

finally:

    center_all()

    time.sleep(0.5)

    pca.deinit()

print("Calibration finished.")
