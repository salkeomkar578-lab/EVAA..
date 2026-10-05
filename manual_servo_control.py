import os
import sys
import json
import time
import signal
import select
import termios
import tty

from servo_controller import FollowerServos, LIMITS


CAL_FILE = "servo_calibration.json"

CENTER = {
    "LR": 90,
    "UD": 90,
    "TL": 90,
    "BaseX": 90,
    "TR": 90,
    "BaseY": 90
}

DEFAULT_SPEEDS = {
    "LR": 80.0,
    "UD": 80.0,
    "TL": 60.0,
    "BaseX": 100.0,
    "TR": 60.0,
    "BaseY": 100.0
}

GAME_STEP_TIME = 0.05

GAME_MAP = {
    "a": ("BaseX", -1),
    "d": ("BaseX", 1),

    "w": ("BaseY", 1),
    "s": ("BaseY", -1),

    "j": ("LR", -1),
    "l": ("LR", 1),

    "i": ("UD", 1),
    "k": ("UD", -1),

    "y": ("TL", 1),
    "h": ("TL", -1),

    "u": ("TR", 1),
    "o": ("TR", -1)
}

stop_requested = False


def stop_handler(signum, frame):
    global stop_requested
    stop_requested = True


def clamp(name, value):

    low, high = sorted(
        LIMITS[name]
    )

    return max(
        low,
        min(high, float(value))
    )


def move_toward(
    current,
    target,
    speed,
    dt
):

    difference = target - current
    step = speed * dt

    if abs(difference) <= step:
        return target

    if difference > 0:
        return current + step

    return current - step


def move_servo(
    servos,
    name,
    target,
    speed
):

    target = clamp(
        name,
        target
    )

    speed = abs(
        float(speed)
    )

    if speed <= 0:
        print("Speed must be greater than 0.")
        return

    print(
        f"{name}: "
        f"{servos.positions[name]:.1f}°"
        f" -> "
        f"{target:.1f}° "
        f"@ {speed:.1f}°/s"
    )

    last = time.monotonic()

    while not stop_requested:

        now = time.monotonic()

        dt = now - last
        last = now

        dt = max(
            0.005,
            min(dt, 0.05)
        )

        current = (
            servos.positions[name]
        )

        new_position = move_toward(
            current,
            target,
            speed,
            dt
        )

        servos.set(
            name,
            new_position
        )

        if abs(
            new_position - target
        ) < 0.3:

            servos.set(
                name,
                target,
                force=True
            )

            break

        time.sleep(0.01)

    print(
        f"{name} = "
        f"{servos.positions[name]:.1f}°"
    )


def move_all(
    servos,
    target,
    speed
):

    target = float(target)
    speed = abs(float(speed))

    start = time.monotonic()

    print(
        f"ALL SERVOS -> {target:.1f}° "
        f"@ {speed:.1f}°/s"
    )

    while not stop_requested:

        now = time.monotonic()

        dt = now - start
        start = now

        dt = max(
            0.005,
            min(dt, 0.05)
        )

        finished = True

        for name in CENTER:

            current = (
                servos.positions[name]
            )

            new_position = move_toward(
                current,
                clamp(name, target),
                speed,
                dt
            )

            servos.set(
                name,
                new_position
            )

            if abs(
                new_position -
                clamp(name, target)
            ) > 0.3:

                finished = False

        if finished:
            break

        time.sleep(0.01)


def center_all(servos):

    print("Centering all servos...")

    for name in CENTER:

        move_servo(
            servos,
            name,
            CENTER[name],
            DEFAULT_SPEEDS[name]
        )

    print("All servos centered.")


def release_all(servos):

    print(
        "Releasing servo PWM..."
    )

    for name in CENTER:

        try:
            servos.release(name)
        except Exception:
            pass


def status(servos):

    print()
    print(
        "========== SERVO STATUS =========="
    )

    for name in CENTER:

        print(
            f"{name:6} "
            f"Position: "
            f"{servos.positions[name]:7.1f}°   "
            f"Limit: "
            f"{LIMITS[name][0]} - "
            f"{LIMITS[name][1]}°   "
            f"Speed: "
            f"{DEFAULT_SPEEDS[name]:.1f}°/s"
        )

    print(
        "=================================="
    )
    print()


def set_speed(
    name,
    speed
):

    DEFAULT_SPEEDS[name] = abs(
        float(speed)
    )

    print(
        f"{name} speed = "
        f"{DEFAULT_SPEEDS[name]:.1f}°/s"
    )


def set_limit(
    name,
    side,
    value
):

    value = float(value)

    low, high = sorted(
        LIMITS[name]
    )

    if side == "min":

        low = value

    elif side == "max":

        high = value

    else:

        print(
            "Use min or max."
        )

        return

    if low >= high:

        print(
            "Invalid limit."
        )

        print(
            "Minimum must be lower "
            "than maximum."
        )

        return

    LIMITS[name] = (
        low,
        high
    )

    print(
        f"{name} limits = "
        f"{low:.1f} - "
        f"{high:.1f}°"
    )


def save_calibration(
    servos,
    marks
):

    data = {
        "center": CENTER,
        "limits": {
            name: [
                LIMITS[name][0],
                LIMITS[name][1]
            ]
            for name in CENTER
        },
        "speeds_deg_per_sec":
            DEFAULT_SPEEDS,
        "positions": {
            name: servos.positions[name]
            for name in CENTER
        },
        "marks": marks
    }

    with open(
        CAL_FILE,
        "w"
    ) as file:

        json.dump(
            data,
            file,
            indent=4
        )

    print()
    print(
        f"Saved calibration to "
        f"{CAL_FILE}"
    )
    print()


def load_calibration():

    if not os.path.exists(
        CAL_FILE
    ):

        return None

    try:

        with open(
            CAL_FILE,
            "r"
        ) as file:

            return json.load(file)

    except Exception as e:

        print(
            "Calibration load error:",
            e
        )

        return None


def apply_calibration(
    data
):

    if not data:
        return

    limits = data.get(
        "limits",
        {}
    )

    for name in CENTER:

        if name in limits:

            low, high = limits[name]

            LIMITS[name] = (
                float(low),
                float(high)
            )

    speeds = data.get(
        "speeds_deg_per_sec",
        {}
    )

    for name in CENTER:

        if name in speeds:

            DEFAULT_SPEEDS[name] = abs(
                float(speeds[name])
            )


def print_help():

    print()
    print(
        "================ MANUAL CONTROL ================"
    )
    print(
        "MOVE COMMANDS"
    )
    print(
        "  move LR 120 80"
    )
    print(
        "  move UD 70 60"
    )
    print(
        "  move BaseX 130 100"
    )
    print(
        "  move BaseY 110 100"
    )
    print(
        "  move TL 140 50"
    )
    print(
        "  move TR 40 50"
    )
    print()
    print(
        "  moveall 90 80"
    )
    print()
    print(
        "SPEED"
    )
    print(
        "  speed LR 80"
    )
    print(
        "  speed BaseX 120"
    )
    print()
    print(
        "LIMIT CALIBRATION"
    )
    print(
        "  limit LR min"
    )
    print(
        "  limit LR max"
    )
    print(
        "  limit BaseX min"
    )
    print(
        "  limit BaseX max"
    )
    print()
    print(
        "MARK POSITIONS"
    )
    print(
        "  mark center_lr"
    )
    print(
        "  mark eye_left"
    )
    print(
        "  mark eye_right"
    )
    print(
        "  mark neck_left"
    )
    print(
        "  mark neck_right"
    )
    print()
    print(
        "OTHER"
    )
    print(
        "  status"
    )
    print(
        "  center"
    )
    print(
        "  game"
    )
    print(
        "  save"
    )
    print(
        "  release"
    )
    print(
        "  help"
    )
    print(
        "  quit"
    )
    print()
    print(
        "GAME MODE"
    )
    print(
        "  A/D = BaseX"
    )
    print(
        "  W/S = BaseY"
    )
    print(
        "  J/L = LR eye"
    )
    print(
        "  I/K = UD eye"
    )
    print(
        "  Y/H = left eyelid"
    )
    print(
        "  U/O = right eyelid"
    )
    print(
        "  C   = center"
    )
    print(
        "  X   = release"
    )
    print(
        "  Q   = exit"
    )
    print(
        "==============================================="
    )
    print()


def game_mode(
    servos
):

    print()
    print(
        "========== GAME MODE =========="
    )
    print(
        "A/D BaseX"
    )
    print(
        "W/S BaseY"
    )
    print(
        "J/L LR"
    )
    print(
        "I/K UD"
    )
    print(
        "Y/H Left Lid"
    )
    print(
        "U/O Right Lid"
    )
    print(
        "C Center"
    )
    print(
        "X Release"
    )
    print(
        "Q Exit"
    )
    print(
        "==============================="
    )

    old_settings = None

    try:

        old_settings = termios.tcgetattr(
            sys.stdin
        )

        tty.setcbreak(
            sys.stdin.fileno()
        )

        running = True

        while running and not stop_requested:

            ready, _, _ = select.select(
                [sys.stdin],
                [],
                [],
                0.05
            )

            if not ready:
                continue

            key = (
                sys.stdin.read(1)
                .lower()
            )

            if key == "q":

                running = False

            elif key == "c":

                center_all(servos)

            elif key == "x":

                release_all(servos)

            elif key in GAME_MAP:

                name, direction = (
                    GAME_MAP[key]
                )

                speed = (
                    DEFAULT_SPEEDS[name]
                )

                amount = (
                    speed *
                    GAME_STEP_TIME
                )

                new_position = (
                    servos.positions[name] +
                    direction *
                    amount
                )

                new_position = clamp(
                    name,
                    new_position
                )

                servos.set(
                    name,
                    new_position
                )

    finally:

        if old_settings is not None:

            termios.tcsetattr(
                sys.stdin,
                termios.TCSADRAIN,
                old_settings
            )

    print(
        "Exited game mode."
    )


def main():

    global stop_requested

    signal.signal(
        signal.SIGINT,
        stop_handler
    )

    signal.signal(
        signal.SIGTERM,
        stop_handler
    )

    data = load_calibration()

    apply_calibration(
        data
    )

    servos = FollowerServos()

    marks = {}

    if data:

        marks.update(
            data.get(
                "marks",
                {}
            )
        )

        print(
            "Loaded existing calibration."
        )

    servos.center_all()

    print()

    print(
        "FOLLOWERBOT MANUAL SERVO CONTROL"
    )

    print(
        "PCA9685 address: 0x40"
    )

    print(
        "All six servos initialized."
    )

    print_help()

    try:

        while not stop_requested:

            command = input(
                "servo> "
            ).strip()

            if not command:
                continue

            parts = command.split()

            cmd = parts[0].lower()

            try:

                if cmd in (
                    "quit",
                    "exit",
                    "q"
                ):

                    break

                elif cmd in (
                    "help",
                    "h"
                ):

                    print_help()

                elif cmd == "status":

                    status(
                        servos
                    )

                elif cmd == "center":

                    center_all(
                        servos
                    )

                elif cmd == "release":

                    release_all(
                        servos
                    )

                elif cmd == "save":

                    save_calibration(
                        servos,
                        marks
                    )

                elif cmd == "game":

                    game_mode(
                        servos
                    )

                elif cmd == "move":

                    if len(parts) != 4:

                        print(
                            "Example:"
                        )

                        print(
                            "move BaseX 120 100"
                        )

                        continue

                    name = parts[1]

                    if name not in CENTER:

                        print(
                            "Unknown servo."
                        )

                        print(
                            list(CENTER)
                        )

                        continue

                    target = float(
                        parts[2]
                    )

                    speed = float(
                        parts[3]
                    )

                    move_servo(
                        servos,
                        name,
                        target,
                        speed
                    )

                elif cmd == "moveall":

                    if len(parts) != 3:

                        print(
                            "Example:"
                        )

                        print(
                            "moveall 90 80"
                        )

                        continue

                    target = float(
                        parts[1]
                    )

                    speed = float(
                        parts[2]
                    )

                    move_all(
                        servos,
                        target,
                        speed
                    )

                elif cmd == "speed":

                    if len(parts) != 3:

                        print(
                            "Example:"
                        )

                        print(
                            "speed BaseX 120"
                        )

                        continue

                    name = parts[1]

                    if name not in CENTER:

                        print(
                            "Unknown servo."
                        )

                        continue

                    set_speed(
                        name,
                        float(parts[2])
                    )

                elif cmd == "limit":

                    if len(parts) != 3:

                        print(
                            "Example:"
                        )

                        print(
                            "limit BaseX min"
                        )

                        continue

                    name = parts[1]

                    side = parts[2].lower()

                    if name not in CENTER:

                        print(
                            "Unknown servo."
                        )

                        continue

                    if side == "min":

                        set_limit(
                            name,
                            "min",
                            servos.positions[name]
                        )

                    elif side == "max":

                        set_limit(
                            name,
                            "max",
                            servos.positions[name]
                        )

                    else:

                        print(
                            "Use min or max."
                        )

                elif cmd == "mark":

                    if len(parts) != 2:

                        print(
                            "Example:"
                        )

                        print(
                            "mark eye_left"
                        )

                        continue

                    label = parts[1]

                    marks[label] = {
                        name:
                        servos.positions[name]
                        for name in CENTER
                    }

                    print(
                        f"Marked position: "
                        f"{label}"
                    )

                elif cmd == "marks":

                    print()

                    if not marks:

                        print(
                            "No marks saved."
                        )

                    else:

                        for label, values in marks.items():

                            print(
                                label,
                                values
                            )

                    print()

                else:

                    print(
                        "Unknown command."
                    )

                    print(
                        "Type: help"
                    )

            except ValueError:

                print(
                    "Invalid number."
                )

            except KeyboardInterrupt:

                print()

                break

    finally:

        print()
        print(
            "Returning to center..."
        )

        try:

            center_all(
                servos
            )

        except Exception:
            pass

        time.sleep(0.2)

        try:

            release_all(
                servos
            )

        except Exception:
            pass

        try:

            servos.close()

        except Exception:
            pass

        print(
            "Servo controller closed."
        )


if __name__ == "__main__":
    main()
