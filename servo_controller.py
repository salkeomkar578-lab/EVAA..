import time
import errno
import busio

from board import SCL, SDA
from adafruit_pca9685 import PCA9685


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

CENTER = {
    "LR": 90.0,
    "UD": 90.0,
    "TL": 90.0,
    "BaseX": 90.0,
    "TR": 90.0,
    "BaseY": 90.0
}

PULSE_MIN = 500.0
PULSE_MAX = 2500.0
PERIOD_US = 20000.0

MIN_ANGLE_CHANGE = 0.4
MIN_WRITE_INTERVAL = 0.04

MAX_RETRIES = 3
RETRY_DELAY = 0.03


class DirectServo:

    def __init__(self, pwm_channel):
        self.channel = pwm_channel

    def angle_to_duty(self, angle):

        pulse_us = (
            PULSE_MIN
            + (angle / 180.0)
            * (PULSE_MAX - PULSE_MIN)
        )

        duty = int(
            (pulse_us / PERIOD_US)
            * 65535
        )

        return max(
            0,
            min(65535, duty)
        )

    def set_angle(self, angle):

        duty = self.angle_to_duty(angle)

        self.channel.duty_cycle = duty

    def release(self):

        try:
            self.channel.duty_cycle = 0
        except Exception:
            pass


class FollowerServos:

    def __init__(self):

        print("Initializing PCA9685...")

        self.i2c = busio.I2C(
            SCL,
            SDA
        )

        time.sleep(0.3)

        self.pca = PCA9685(
            self.i2c,
            address=I2C_ADDRESS
        )

        time.sleep(0.2)

        self.pca.frequency = PWM_FREQ

        time.sleep(0.2)

        self.motors = {}

        for name, channel in CHANNELS.items():

            self.motors[name] = DirectServo(
                self.pca.channels[channel]
            )

        self.positions = CENTER.copy()

        self.pending = set()

        self.last_write = {
            name: 0.0
            for name in CHANNELS
        }

        print("PCA9685 ready.")

    def limit_angle(self, name, angle):

        # No special BaseY limit.
        # All servos use 0-180 degrees.

        angle = float(angle)

        return max(
            0.0,
            min(180.0, angle)
        )

    def _write_one(self, name):

        now = time.monotonic()

        if (
            now - self.last_write[name]
            < MIN_WRITE_INTERVAL
        ):
            return True

        angle = self.positions[name]

        for attempt in range(MAX_RETRIES):

            try:

                self.motors[name].set_angle(
                    angle
                )

                self.last_write[name] = (
                    time.monotonic()
                )

                self.pending.discard(name)

                return True

            except OSError as error:

                error_code = getattr(
                    error,
                    "errno",
                    None
                )

                if error_code not in (
                    errno.EIO,
                    errno.EREMOTEIO,
                    5,
                    121
                ):
                    raise

                time.sleep(
                    RETRY_DELAY
                )

        print(
            f"I2C write failed for {name}"
        )

        return False

    def set(
        self,
        name,
        angle,
        force=False
    ):

        angle = self.limit_angle(
            name,
            angle
        )

        current = self.positions[name]

        if (
            not force
            and
            abs(angle - current)
            < MIN_ANGLE_CHANGE
        ):
            return True

        self.positions[name] = angle

        self.pending.add(name)

        if force:

            return self._write_one(
                name
            )

        return True

    def flush(self):

        if not self.pending:
            return True

        success = True

        # Maximum two channel writes per update.
        # This limits I2C traffic.

        count = 0

        for name in list(self.pending):

            if count >= 2:
                break

            if self._write_one(name):

                count += 1

            else:

                success = False

        return success

    def center_all(self):

        print("Centering servos...")

        for name in CHANNELS:

            self.positions[name] = (
                CENTER[name]
            )

            self.pending.add(name)

        for name in CHANNELS:

            self._write_one(name)

            time.sleep(0.20)

        self.pending.clear()

        print("All servos centered.")

    def release(self, name):

        try:
            self.motors[name].release()
        except Exception:
            pass

    def release_all(self):

        for name in CHANNELS:
            self.release(name)

    def close(self):

        try:
            self.pca.deinit()
        except Exception:
            pass

        try:
            self.i2c.deinit()
        except Exception:
            pass
