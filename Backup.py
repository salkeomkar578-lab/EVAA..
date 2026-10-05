import time
import random
import cv2

from camera import start_camera, get_frame
from servo_controller import FollowerServos


MODEL_PATH = "models/face_detection_yunet_2023mar.onnx"

FRAME_WIDTH = 640
FRAME_HEIGHT = 480

CENTER_X = FRAME_WIDTH // 2
CENTER_Y = FRAME_HEIGHT // 2


# ============================================================
# EYE TRACKING
# ============================================================

EYE_DEADZONE_X = 25
EYE_DEADZONE_Y = 25

EYE_KP_X = 0.022
EYE_KP_Y = 0.022

MAX_EYE_STEP = 2.5


# ============================================================
# NECK TRACKING
# ============================================================

NECK_DEADZONE_X = 20
NECK_DEADZONE_Y = 20

NECK_DELAY = 0.8

NECK_SPEED_X = 50.0
NECK_SPEED_Y = 42.0

BASE_X_GAIN = 1.0

# Direct face-Y tracking for BaseY
BASE_Y_KP = 0.16

BASE_X_FILTER = 0.10
BASE_Y_FILTER = 0.08

MAX_BASE_X_STEP = 1.6
MAX_BASE_Y_STEP = 1.3


# ============================================================
# FACE FILTER
# ============================================================

FACE_FILTER = 0.18


# ============================================================
# DIRECTIONS
# ============================================================

# LR eye direction
LR_DIRECTION = -1

# Base horizontal direction
BASE_X_DIRECTION = -1

# Base vertical direction
BASE_Y_DIRECTION = 1


# ============================================================
# BLINK
# ============================================================

# Random interval between blinks
BLINK_MIN_INTERVAL = 5.0
BLINK_MAX_INTERVAL = 30.0

# Fast blink
BLINK_CLOSE_TIME = 0.07
BLINK_HOLD_TIME = 0.025
BLINK_OPEN_TIME = 0.09

BLINK_TL_OPEN = 90
BLINK_TR_OPEN = 90

BLINK_TL_CLOSED = 160
BLINK_TR_CLOSED = 20


servos = FollowerServos()


# ============================================================
# GLOBAL BLINK STATE
# ============================================================

blink_active = False
blink_phase = 0

blink_phase_start = 0.0

next_blink_time = 0.0


# ============================================================
# HELPERS
# ============================================================

def clamp(value, low, high):
    return max(low, min(high, value))


def smooth(current, target, factor):
    return current + (target - current) * factor


def move_toward(current, target, speed, dt):

    distance = target - current

    step = speed * dt

    if abs(distance) <= step:
        return target

    if distance > 0:
        return current + step

    return current - step


def set_servo(name, angle):

    angle = servos.limit_angle(
        name,
        angle
    )

    current = servos.positions[name]

    if abs(angle - current) >= 0.12:

        servos.positions[name] = angle
        servos.motors[name].angle = angle


# ============================================================
# BLINK
# ============================================================

def schedule_next_blink(now):

    return (
        now
        +
        random.uniform(
            BLINK_MIN_INTERVAL,
            BLINK_MAX_INTERVAL
        )
    )


def start_blink(now):

    global blink_active
    global blink_phase
    global blink_phase_start

    if blink_active:
        return

    blink_active = True
    blink_phase = 1
    blink_phase_start = now


def update_blink(now):

    global blink_active
    global blink_phase
    global blink_phase_start
    global next_blink_time

    if not blink_active:
        return

    elapsed = now - blink_phase_start

    # ========================================================
    # PHASE 1: CLOSE
    # ========================================================

    if blink_phase == 1:

        t = clamp(
            elapsed / BLINK_CLOSE_TIME,
            0.0,
            1.0
        )

        tl = (
            BLINK_TL_OPEN
            +
            (
                BLINK_TL_CLOSED
                -
                BLINK_TL_OPEN
            )
            * t
        )

        tr = (
            BLINK_TR_OPEN
            +
            (
                BLINK_TR_CLOSED
                -
                BLINK_TR_OPEN
            )
            * t
        )

        set_servo("TL", tl)
        set_servo("TR", tr)

        if t >= 1.0:

            blink_phase = 2
            blink_phase_start = now

        return

    # ========================================================
    # PHASE 2: HOLD CLOSED
    # ========================================================

    if blink_phase == 2:

        set_servo(
            "TL",
            BLINK_TL_CLOSED
        )

        set_servo(
            "TR",
            BLINK_TR_CLOSED
        )

        if elapsed >= BLINK_HOLD_TIME:

            blink_phase = 3
            blink_phase_start = now

        return

    # ========================================================
    # PHASE 3: OPEN
    # ========================================================

    if blink_phase == 3:

        t = clamp(
            elapsed / BLINK_OPEN_TIME,
            0.0,
            1.0
        )

        tl = (
            BLINK_TL_CLOSED
            +
            (
                BLINK_TL_OPEN
                -
                BLINK_TL_CLOSED
            )
            * t
        )

        tr = (
            BLINK_TR_CLOSED
            +
            (
                BLINK_TR_OPEN
                -
                BLINK_TR_CLOSED
            )
            * t
        )

        set_servo("TL", tl)
        set_servo("TR", tr)

        if t >= 1.0:

            set_servo(
                "TL",
                BLINK_TL_OPEN
            )

            set_servo(
                "TR",
                BLINK_TR_OPEN
            )

            blink_active = False
            blink_phase = 0

            next_blink_time = schedule_next_blink(
                now
            )


# ============================================================
# FACE BOX
# ============================================================

def square_box(x, y, w, h):

    size = max(w, h)

    center_x = x + w // 2
    center_y = y + h // 2

    x1 = center_x - size // 2
    y1 = center_y - size // 2

    x2 = center_x + size // 2
    y2 = center_y + size // 2

    x1 = max(0, x1)
    y1 = max(0, y1)

    x2 = min(
        FRAME_WIDTH - 1,
        x2
    )

    y2 = min(
        FRAME_HEIGHT - 1,
        y2
    )

    return x1, y1, x2, y2


# ============================================================
# MAIN
# ============================================================

def main():

    global next_blink_time

    print()
    print("==========================================")
    print("       FOLLOWERBOT STABLE TRACKING")
    print("==========================================")
    print("Fast eye tracking")
    print("Stable BaseX tracking")
    print("Direct face-position BaseY tracking")
    print("Random fast blinking: 5-30 seconds")
    print("==========================================")
    print()

    servos.center_all()

    time.sleep(0.5)

    detector = cv2.FaceDetectorYN.create(
        MODEL_PATH,
        "",
        (
            FRAME_WIDTH,
            FRAME_HEIGHT
        ),
        0.60,
        0.30,
        5000
    )

    camera = start_camera(
        FRAME_WIDTH,
        FRAME_HEIGHT
    )

    last_time = time.time()

    next_blink_time = schedule_next_blink(
        last_time
    )

    filtered_face_x = None
    filtered_face_y = None

    neck_start_time = None
    neck_active = False

    base_x_target = 90.0
    base_y_target = 90.0

    try:

        while True:

            frame = get_frame(camera)

            now = time.time()

            dt = now - last_time

            last_time = now

            if dt <= 0:
                dt = 0.01

            # ====================================================
            # DETECTOR
            # ====================================================

            detector.setInputSize(
                (
                    FRAME_WIDTH,
                    FRAME_HEIGHT
                )
            )

            _, detections = detector.detect(frame)

            face_found = False

            error_x = 0
            error_y = 0

            # ====================================================
            # FACE
            # ====================================================

            if (
                detections is not None
                and len(detections) > 0
            ):

                face = max(
                    detections,
                    key=lambda d: d[2] * d[3]
                )

                x = int(face[0])
                y = int(face[1])
                w = int(face[2])
                h = int(face[3])

                raw_face_x = x + w // 2
                raw_face_y = y + h // 2

                # =================================================
                # FILTER FACE POSITION
                # =================================================

                if filtered_face_x is None:

                    filtered_face_x = raw_face_x
                    filtered_face_y = raw_face_y

                else:

                    filtered_face_x = smooth(
                        filtered_face_x,
                        raw_face_x,
                        FACE_FILTER
                    )

                    filtered_face_y = smooth(
                        filtered_face_y,
                        raw_face_y,
                        FACE_FILTER
                    )

                face_x = int(
                    filtered_face_x
                )

                face_y = int(
                    filtered_face_y
                )

                error_x = (
                    CENTER_X -
                    face_x
                )

                error_y = (
                    CENTER_Y -
                    face_y
                )

                face_found = True

                # =================================================
                # EYE LR
                # =================================================

                if abs(error_x) > EYE_DEADZONE_X:

                    corrected_x = (
                        error_x
                        -
                        (
                            EYE_DEADZONE_X
                            if error_x > 0
                            else -EYE_DEADZONE_X
                        )
                    )

                    step_x = (
                        corrected_x
                        *
                        EYE_KP_X
                        *
                        LR_DIRECTION
                    )

                    step_x = clamp(
                        step_x,
                        -MAX_EYE_STEP,
                        MAX_EYE_STEP
                    )

                    target_lr = (
                        servos.positions["LR"]
                        +
                        step_x
                    )

                    set_servo(
                        "LR",
                        target_lr
                    )

                # =================================================
                # EYE UD
                # =================================================

                if abs(error_y) > EYE_DEADZONE_Y:

                    corrected_y = (
                        error_y
                        -
                        (
                            EYE_DEADZONE_Y
                            if error_y > 0
                            else -EYE_DEADZONE_Y
                        )
                    )

                    step_y = (
                        corrected_y
                        *
                        EYE_KP_Y
                    )

                    step_y = clamp(
                        step_y,
                        -MAX_EYE_STEP,
                        MAX_EYE_STEP
                    )

                    target_ud = (
                        servos.positions["UD"]
                        +
                        step_y
                    )

                    set_servo(
                        "UD",
                        target_ud
                    )

                # =================================================
                # NECK ACTIVATION
                # =================================================

                neck_needed = (
                    abs(error_x)
                    >
                    NECK_DEADZONE_X
                    or
                    abs(error_y)
                    >
                    NECK_DEADZONE_Y
                )

                if neck_needed:

                    if neck_start_time is None:

                        neck_start_time = now

                    elif (
                        now - neck_start_time
                        >= NECK_DELAY
                    ):

                        neck_active = True

                else:

                    neck_start_time = None
                    neck_active = False

                # =================================================
                # BASE TRACKING
                # =================================================

                if neck_active:

                    # ---------------------------------------------
                    # BASE X
                    # ---------------------------------------------

                    eye_lr_offset = (
                        servos.positions["LR"]
                        -
                        90
                    )

                    target_x = (
                        90
                        +
                        (
                            eye_lr_offset
                            *
                            BASE_X_GAIN
                            *
                            BASE_X_DIRECTION
                        )
                    )

                    target_x = servos.limit_angle(
                        "BaseX",
                        target_x
                    )

                    base_x_target = smooth(
                        base_x_target,
                        target_x,
                        BASE_X_FILTER
                    )

                    new_base_x = move_toward(
                        servos.positions["BaseX"],
                        base_x_target,
                        NECK_SPEED_X,
                        dt
                    )

                    delta_x = (
                        new_base_x
                        -
                        servos.positions["BaseX"]
                    )

                    delta_x = clamp(
                        delta_x,
                        -MAX_BASE_X_STEP,
                        MAX_BASE_X_STEP
                    )

                    new_base_x = (
                        servos.positions["BaseX"]
                        +
                        delta_x
                    )

                    # ---------------------------------------------
                    # BASE Y
                    # ---------------------------------------------
                    #
                    # IMPORTANT:
                    #
                    # BaseY now uses the FACE Y ERROR directly.
                    #
                    # This fixes the problem where the eyes could
                    # compensate vertically while BaseY stayed still.
                    #
                    # Face DOWN:
                    # error_y becomes negative
                    # BaseY moves down
                    #
                    # Face UP:
                    # error_y becomes positive
                    # BaseY moves up
                    #

                    target_y = (
                        90
                        +
                        (
                            error_y
                            *
                            BASE_Y_KP
                            *
                            BASE_Y_DIRECTION
                        )
                    )

                    target_y = servos.limit_angle(
                        "BaseY",
                        target_y
                    )

                    base_y_target = smooth(
                        base_y_target,
                        target_y,
                        BASE_Y_FILTER
                    )

                    new_base_y = move_toward(
                        servos.positions["BaseY"],
                        base_y_target,
                        NECK_SPEED_Y,
                        dt
                    )

                    delta_y = (
                        new_base_y
                        -
                        servos.positions["BaseY"]
                    )

                    delta_y = clamp(
                        delta_y,
                        -MAX_BASE_Y_STEP,
                        MAX_BASE_Y_STEP
                    )

                    new_base_y = (
                        servos.positions["BaseY"]
                        +
                        delta_y
                    )

                    set_servo(
                        "BaseX",
                        new_base_x
                    )

                    set_servo(
                        "BaseY",
                        new_base_y
                    )

                # =================================================
                # FACE BOX
                # =================================================

                bx1, by1, bx2, by2 = square_box(
                    x,
                    y,
                    w,
                    h
                )

                cv2.rectangle(
                    frame,
                    (
                        bx1,
                        by1
                    ),
                    (
                        bx2,
                        by2
                    ),
                    (0, 255, 0),
                    2
                )

                cv2.circle(
                    frame,
                    (
                        face_x,
                        face_y
                    ),
                    5,
                    (0, 0, 255),
                    -1
                )

                cv2.line(
                    frame,
                    (
                        face_x,
                        face_y
                    ),
                    (
                        CENTER_X,
                        CENTER_Y
                    ),
                    (255, 255, 0),
                    2
                )

            else:

                neck_start_time = None
                neck_active = False

            # ====================================================
            # CENTER TARGET
            # ====================================================

            target_size = 55

            cv2.rectangle(
                frame,
                (
                    CENTER_X - target_size,
                    CENTER_Y - target_size
                ),
                (
                    CENTER_X + target_size,
                    CENTER_Y + target_size
                ),
                (255, 255, 0),
                2
            )

            cv2.drawMarker(
                frame,
                (
                    CENTER_X,
                    CENTER_Y
                ),
                (255, 255, 255),
                cv2.MARKER_CROSS,
                30,
                2
            )

            # ====================================================
            # STATUS
            # ====================================================

            if face_found:

                cv2.putText(
                    frame,
                    "FACE LOCKED",
                    (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (0, 255, 0),
                    2
                )

            else:

                cv2.putText(
                    frame,
                    "SEARCHING...",
                    (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (0, 0, 255),
                    2
                )

            cv2.putText(
                frame,
                f"X ERROR: {error_x}",
                (10, 52),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                2
            )

            cv2.putText(
                frame,
                f"Y ERROR: {error_y}",
                (10, 77),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                2
            )

            cv2.putText(
                frame,
                f"LR: {servos.positions['LR']:.1f}",
                (10, 105),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.50,
                (255, 255, 255),
                2
            )

            cv2.putText(
                frame,
                f"UD: {servos.positions['UD']:.1f}",
                (10, 128),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.50,
                (255, 255, 255),
                2
            )

            cv2.putText(
                frame,
                f"BaseX: {servos.positions['BaseX']:.1f}",
                (10, 151),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.50,
                (255, 255, 255),
                2
            )

            cv2.putText(
                frame,
                f"BaseY: {servos.positions['BaseY']:.1f}",
                (10, 174),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.50,
                (255, 255, 255),
                2
            )

            if neck_active:

                cv2.putText(
                    frame,
                    "NECK TRACKING",
                    (10, 202),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.50,
                    (0, 255, 255),
                    2
                )

            # ====================================================
            # RANDOM FAST BLINK
            # ====================================================

            if (
                face_found
                and not blink_active
                and now >= next_blink_time
            ):

                start_blink(now)

            update_blink(now)

            # ====================================================
            # CAMERA
            # ====================================================

            cv2.imshow(
                "FollowerBot Face Tracking",
                frame
            )

            key = cv2.waitKey(1) & 0xFF

            if key == 27 or key == ord("q"):
                break

    except KeyboardInterrupt:

        pass

    finally:

        print()
        print("Returning robot to rest position...")

        try:

            servos.center_all()

            time.sleep(0.5)

        except Exception:

            pass

        try:

            camera.stop()

        except Exception:

            pass

        cv2.destroyAllWindows()

        servos.close()


if __name__ == "__main__":
    main()
