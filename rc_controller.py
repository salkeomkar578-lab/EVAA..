import time
import errno
import busio

from board import SCL, SDA


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

BASEY_UP_LIMIT = 170.0

PULSE_MIN = 500.0
PULSE_MAX = 2500.0

PERIOD_US = 20000.0

MIN_WRITE_INTERVAL = 0.04
MIN_ANGLE_CHANGE = 0.4

MAX_RETRIES = 3
RETRY_DELAY = 0.03

MODE1 = 0x00
MODE2 = 0x01
PRE_SCALE = 0xFE
LED0_ON_L = 0x06

PRE_SCALE_VALUE = 121


class DirectServo:

    def __init__(self, controller, channel):
        self.controller = controller
        self.channel = channel

    def angle_to_duty(self, angle):

        pulse_us = (
            PULSE_MIN
            +
            (angle / 180.0)
            *
            (PULSE_MAX - PULSE_MIN)
        )

        duty = int(
            (pulse_us / PERIOD_US)
            * 4096
        )

        return max(
            0,
            min(4095, duty)
        )

    def set_angle(self, angle):

        self.controller.positions_dirty = True

        return self.angle_to_duty(angle)


class FollowerServos:

    def __init__(self):

        print("Initializing PCA9685...")

        self.i2c = busio.I2C(
            SCL,
            SDA
        )

        while not self.i2c.try_lock():
            time.sleep(0.001)

        try:

            self._write_bytes(
                [MODE1, 0x10]
            )

            time.sleep(0.01)

            self._write_bytes(
                [PRE_SCALE, PRE_SCALE_VALUE]
            )

            time.sleep(0.01)

            self._write_bytes(
                [MODE1, 0x20]
            )

            time.sleep(0.01)

            self._write_bytes(
                [MODE2, 0x04]
            )

        finally:

            self.i2c.unlock()

        self.motors = {}

        for name, channel in CHANNELS.items():

            self.motors[name] = DirectServo(
                self,
                channel
            )

        self.positions = CENTER.copy()

        self.positions_dirty = False

        self.last_flush = 0.0

        print("PCA9685 ready.")

    def _write_bytes(self, data):

        last_error = None

        for attempt in range(MAX_RETRIES):

            try:

                while not self.i2c.try_lock():
                    time.sleep(0.001)

                try:

                    self.i2c.writeto(
                        I2C_ADDRESS,
                        bytes(data)
                    )

                finally:

                    self.i2c.unlock()

                return True

            except OSError as error:

                last_error = error

                if getattr(
                    error,
                    "errno",
                    None
                ) not in (
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
            "I2C write failed:",
            last_error
        )

        return False

    def limit_angle(self, name, angle):

        angle = float(angle)

        angle = max(
            0.0,
            min(180.0, angle)
        )

        if name == "BaseY":

            if angle > BASEY_UP_LIMIT:
                angle = BASEY_UP_LIMIT

        return angle

    def set(self, name, angle, force=False):

        angle = self.limit_angle(
            name,
            angle
        )

        current = self.positions[name]

        if (
            not force
            and abs(angle - current)
            < MIN_ANGLE_CHANGE
        ):
            return True

        self.positions[name] = angle
        self.positions_dirty = True

        if force:

            return self.flush(
                force=True
            )

        return True

    def _build_pwm_packet(self):

        data = [LED0_ON_L]

        for name, channel in CHANNELS.items():

            angle = self.limit_angle(
                name,
                self.positions[name]
            )

            pulse_us = (
                PULSE_MIN
                +
                (angle / 180.0)
                *
                (PULSE_MAX - PULSE_MIN)
            )

            duty = int(
                (
                    pulse_us
                    /
                    PERIOD_US
                )
                *
                4096
            )

            duty = max(
                0,
                min(4095, duty)
            )

            on_low = 0
            on_high = 0

            off_low = duty & 0xFF
            off_high = (
                (duty >> 8)
                & 0x0F
            )

            data.extend(
                [
                    on_low,
                    on_high,
                    off_low,
                    off_high
                ]
            )

        return data

    def flush(self, force=False):

        if not self.positions_dirty:
            return True

        now = time.monotonic()

        if (
            not force
            and
            now - self.last_flush
            < MIN_WRITE_INTERVAL
        ):
            return True

        packet = self._build_pwm_packet()

        success = self._write_bytes(
            packet
        )

        if success:

            self.last_flush = now
            self.positions_dirty = False

        return success

    def center_all(self):

        print("Centering servos...")

        for name in CHANNELS:

            self.positions[name] = (
                CENTER[name]
            )

        self.positions_dirty = True

        self.flush(
            force=True
        )

        time.sleep(0.3)

        print("All servos centered.")

    def release(self, name):

        if name in self.positions:

            self.positions[name] = (
                self.positions[name]
            )

    def release_all(self):
        pass

    def close(self):

        try:

            self.flush(
                force=True
            )

        except Exception:

            pass

        try:

            self.i2c.deinit()

        except Exception:

            pass
