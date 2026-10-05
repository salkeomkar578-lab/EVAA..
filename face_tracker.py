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

EYE_DEADZONE_X = 20
EYE_DEADZONE_Y = 20

EYE_KP_X = 0.026
EYE_KP_Y = 0.026

MAX_EYE_STEP = 3.0


# ============================================================
# NECK TRACKING
# ============================================================

NECK_DEADZONE_X = 18
NECK_DEADZONE_Y = 18

NECK_DELAY_X = 0.45
NECK_DELAY_Y = 0.35

NECK_SPEED_X = 65.0
NECK_SPEED_Y = 55.0

MAX_BASE_X_STEP = 2.2
MAX_BASE_Y_STEP = 1.8


# ============================================================
# BASE X
# ============================================================

BASE_X_DIRECTION = -1
BASE_X_GAIN = 1.0
BASE_X_FILTER = 0.12


# ============================================================
# BASE Y
# ============================================================

BASE_Y_DIRECTION = 1

BASE_Y_FACE_GAIN = 0.25
BASE_Y_UD_GAIN = 0.80

BASE_Y_FILTER = 0.10
VERTICAL_DEMAND_FILTER = 0.08


# ============================================================
# FACE FILTER
# ============================================================

FACE_FILTER = 0.24


# ============================================================
# BLINK
# ============================================================

BLINK_MIN_INTERVAL = 5.0
BLINK_MAX_INTERVAL = 30.0

BLINK_CLOSE_TIME = 0.055
BLINK_HOLD_TIME = 0.025
BLINK_OPEN_TIME = 0.075

BLINK_TL_OPEN = 90.0
BLINK_TR_OPEN = 90.0

BLINK_TL_CLOSED = 160.0
BLINK_TR_CLOSED = 20.0


servos = FollowerServos()


# ============================================================
# BLINK STATE
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

    servos.set(
        name,
        angle
    )


# ============================================================
# SYNCHRONIZED EYELID CONTROL
# ============================================================

def set_both_eyelids(tl_angle, tr_angle):

    tl_angle = servos.limit_angle(
        "TL",
        tl_angle
    )

    tr_angle = servos.limit_angle(
        "TR",
        tr_angle
    )

    # Both commands are prepared first.
    # There is deliberately NO flush between them.
    servos.set(
        "TL",
        tl_angle
    )

    servos.set(
        "TR",
        tr_angle
    )


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

    elapsed = (
        now
        -
        blink_phase_start
    )

    # ========================================================
    # CLOSE BOTH EYES TOGETHER
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

        set_both_eyelids(
            tl,
            tr
        )

        if t >= 1.0:

            blink_phase = 2
            blink_phase_start = now

        return

    # ========================================================
    # BOTH EYES CLOSED
    # ========================================================

    if blink_phase == 2:

        set_both_eyelids(
            BLINK_TL_CLOSED,
            BLINK_TR_CLOSED
        )

        if elapsed >= BLINK_HOLD_TIME:

            blink_phase = 3
            blink_phase_start = now

        return

    # ========================================================
    # OPEN BOTH EYES TOGETHER
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

        set_both_eyelids(
            tl,
            tr
        )

        if t >= 1.0:

            set_both_eyelids(
                BLINK_TL_OPEN,
                BLINK_TR_OPEN
            )

            blink_active = False
            blink_phase = 0
            blink_phase_start = 0.0

            next_blink_time = (
                schedule_next_blink(now)
            )


# ============================================================
# FACE BOX
# ============================================================

def square_box(
    x,
    y,
    w,
    h
):

    size = max(
        w,
        h
    )

    cx = x + w // 2
    cy = y + h // 2

    x1 = cx - size // 2
    y1 = cy - size // 2

    x2 = cx + size // 2
    y2 = cy + size // 2

    x1 = max(
        0,
        x1
    )

    y1 = max(
        0,
        y1
    )

    x2 = min(
        FRAME_WIDTH - 1,
        x2
    )

    y2 = min(
        FRAME_HEIGHT - 1,
        y2
    )

    return (
        x1,
        y1,
        x2,
        y2
    )


# ============================================================
# MAIN
# ============================================================

def main():

    global next_blink_time

    print()
    print(
        "=========================================="
    )
    print(
        "       FOLLOWERBOT FACE TRACKING"
    )
    print(
        "=========================================="
    )
    print(
        "Fast eye tracking"
    )
    print(
        "Stable BaseX tracking"
    )
    print(
        "Cooperative UD + BaseY tracking"
    )
    print(
        "Synchronized two-eye blinking"
    )
    print(
        "Random blink interval: 5-30 seconds"
    )
    print(
        "=========================================="
    )
    print()

    servos.center_all()

    time.sleep(0.4)

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

    next_blink_time = (
        schedule_next_blink(
            last_time
        )
    )

    filtered_face_x = None
    filtered_face_y = None

    neck_x_start = None
    neck_y_start = None

    neck_x_active = False
    neck_y_active = False

    base_x_target = 90.0
    base_y_target = 90.0

    vertical_demand = 0.0

    try:

        while True:

            frame = get_frame(
                camera
            )

            now = time.time()

            dt = (
                now
                -
                last_time
            )

            last_time = now

            if dt <= 0:
                dt = 0.01

            detector.setInputSize(
                (
                    FRAME_WIDTH,
                    FRAME_HEIGHT
                )
            )

            _, detections = (
                detector.detect(frame)
            )

            face_found = False

            error_x = 0
            error_y = 0

            ud_offset = 0.0

            # ====================================================
            # FACE
            # ====================================================

            if (
                detections is not None
                and
                len(detections) > 0
            ):

                face = max(
                    detections,
                    key=lambda d:
                    d[2] * d[3]
                )

                x = int(face[0])
                y = int(face[1])
                w = int(face[2])
                h = int(face[3])

                raw_face_x = (
                    x
                    +
                    w // 2
                )

                raw_face_y = (
                    y
                    +
                    h // 2
                )

                if filtered_face_x is None:

                    filtered_face_x = (
                        raw_face_x
                    )

                    filtered_face_y = (
                        raw_face_y
                    )

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
                    CENTER_X
                    -
                    face_x
                )

                error_y = (
                    CENTER_Y
                    -
                    face_y
                )

                face_found = True

                # =================================================
                # VERTICAL MEMORY
                # =================================================

                vertical_demand = smooth(
                    vertical_demand,
                    error_y,
                    VERTICAL_DEMAND_FILTER
                )

                # =================================================
                # LR EYE
                # =================================================

                if abs(error_x) > EYE_DEADZONE_X:

                    corrected_x = (
                        error_x
                        -
                        (
                            EYE_DEADZONE_X
                            if error_x > 0
                            else
                            -EYE_DEADZONE_X
                        )
                    )

                    step_x = (
                        corrected_x
                        *
                        EYE_KP_X
                        *
                        -1
                    )

                    step_x = clamp(
                        step_x,
                        -MAX_EYE_STEP,
                        MAX_EYE_STEP
                    )

                    set_servo(
                        "LR",
                        servos.positions[
                            "LR"
                        ]
                        +
                        step_x
                    )

                # =================================================
                # UD EYE
                # =================================================

                if abs(error_y) > EYE_DEADZONE_Y:

                    corrected_y = (
                        error_y
                        -
                        (
                            EYE_DEADZONE_Y
                            if error_y > 0
                            else
                            -EYE_DEADZONE_Y
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

                    set_servo(
                        "UD",
                        servos.positions[
                            "UD"
                        ]
                        +
                        step_y
                    )

                # =================================================
                # CURRENT EYE OFFSETS
                # =================================================

                lr_offset = (
                    servos.positions[
                        "LR"
                    ]
                    -
                    90
                )

                ud_offset = (
                    servos.positions[
                        "UD"
                    ]
                    -
                    90
                )

                # =================================================
                # BASE X TRIGGER
                # =================================================

                if (
                    abs(error_x)
                    >
                    NECK_DEADZONE_X
                    or
                    abs(lr_offset)
                    >
                    NECK_DEADZONE_X
                ):

                    if neck_x_start is None:

                        neck_x_start = now

                    elif (
                        now
                        -
                        neck_x_start
                        >= NECK_DELAY_X
                    ):

                        neck_x_active = True

                else:

                    neck_x_start = None
                    neck_x_active = False

                # =================================================
                # BASE Y TRIGGER
                # =================================================

                if (
                    abs(error_y)
                    >
                    NECK_DEADZONE_Y
                    or
                    abs(ud_offset)
                    >
                    NECK_DEADZONE_Y
                    or
                    abs(vertical_demand)
                    >
                    NECK_DEADZONE_Y
                ):

                    if neck_y_start is None:

                        neck_y_start = now

                    elif (
                        now
                        -
                        neck_y_start
                        >= NECK_DELAY_Y
                    ):

                        neck_y_active = True

                else:

                    neck_y_start = None
                    neck_y_active = False

                # =================================================
                # BASE X
                # =================================================

                if neck_x_active:

                    target_base_x = (
                        90
                        +
                        (
                            lr_offset
                            *
                            BASE_X_GAIN
                            *
                            BASE_X_DIRECTION
                        )
                    )

                    target_base_x = (
                        servos.limit_angle(
                            "BaseX",
                            target_base_x
                        )
                    )

                    base_x_target = smooth(
                        base_x_target,
                        target_base_x,
                        BASE_X_FILTER
                    )

                    new_base_x = move_toward(
                        servos.positions[
                            "BaseX"
                        ],
                        base_x_target,
                        NECK_SPEED_X,
                        dt
                    )

                    dx = (
                        new_base_x
                        -
                        servos.positions[
                            "BaseX"
                        ]
                    )

                    dx = clamp(
                        dx,
                        -MAX_BASE_X_STEP,
                        MAX_BASE_X_STEP
                    )

                    set_servo(
                        "BaseX",
                        servos.positions[
                            "BaseX"
                        ]
                        +
                        dx
                    )

                # =================================================
                # BASE Y
                # =================================================

                if neck_y_active:

                    vertical_component = (
                        vertical_demand
                        *
                        BASE_Y_FACE_GAIN
                    )

                    ud_component = (
                        ud_offset
                        *
                        BASE_Y_UD_GAIN
                    )

                    target_base_y = (
                        90
                        +
                        (
                            vertical_component
                            +
                            ud_component
                        )
                        *
                        BASE_Y_DIRECTION
                    )

                    target_base_y = (
                        servos.limit_angle(
                            "BaseY",
                            target_base_y
                        )
                    )

                    base_y_target = smooth(
                        base_y_target,
                        target_base_y,
                        BASE_Y_FILTER
                    )

                    new_base_y = move_toward(
                        servos.positions[
                            "BaseY"
                        ],
                        base_y_target,
                        NECK_SPEED_Y,
                        dt
                    )

                    dy = (
                        new_base_y
                        -
                        servos.positions[
                            "BaseY"
                        ]
                    )

                    dy = clamp(
                        dy,
                        -MAX_BASE_Y_STEP,
                        MAX_BASE_Y_STEP
                    )

                    set_servo(
                        "BaseY",
                        servos.positions[
                            "BaseY"
                        ]
                        +
                        dy
                    )

                # =================================================
                # FACE BOX
                # =================================================

                bx1, by1, bx2, by2 = (
                    square_box(
                        x,
                        y,
                        w,
                        h
                    )
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

                neck_x_start = None
                neck_y_start = None

                neck_x_active = False
                neck_y_active = False

                vertical_demand = smooth(
                    vertical_demand,
                    0.0,
                    0.03
                )

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
                f"UD: {servos.positions['UD']:.1f}",
                (10, 102),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.50,
                (255, 255, 255),
                2
            )

            cv2.putText(
                frame,
                f"BaseY: {servos.positions['BaseY']:.1f}",
                (10, 125),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.50,
                (255, 255, 255),
                2
            )

            cv2.putText(
                frame,
                f"BaseX: {servos.positions['BaseX']:.1f}",
                (10, 148),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.50,
                (255, 255, 255),
                2
            )

            # ====================================================
            # BLINK
            # ====================================================

            if (
                face_found
                and
                not blink_active
                and
                now >= next_blink_time
            ):

                start_blink(
                    now
                )

            update_blink(
                now
            )

            # ====================================================
            # SERVO UPDATE
            # ====================================================

            # Both eyelids are already queued before this call.
            # One flush handles the complete blink phase.

            servos.flush()

            # ====================================================
            # DISPLAY
            # ====================================================

            cv2.imshow(
                "FollowerBot Face Tracking",
                frame
            )

            key = (
                cv2.waitKey(1)
                &
                0xFF
            )

            if (
                key == 27
                or
                key == ord("q")
            ):

                break

    except KeyboardInterrupt:

        pass

    finally:

        print()
        print(
            "Returning robot to rest position..."
        )

        try:

            servos.center_all()

            time.sleep(0.4)

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
