import os
import time
import signal
import cv2

from camera import start_camera, get_frame
from servo_controller import FollowerServos, LIMITS

MODEL = "models/face_detection_yunet_2023mar.onnx"

FRAME_W = 640
FRAME_H = 480

FACE_SCORE = 0.60
MIN_FACE_WIDTH = 55

EYE_DEADZONE = 12
BASE_DEADZONE = 40

EYE_GAIN_X = 0.14
EYE_GAIN_Y = 0.14

EYE_SPEED = 320.0
BASE_X_SPEED = 45.0
BASE_Y_SPEED = 32.0
REST_SPEED = 170.0

NO_FACE_DELAY = 0.30
FACE_LOST_LIMIT = 0.80

CENTER = 90.0

BASE_X_REVERSED = True

BLINK_CLOSE_TIME = 0.14
BLINK_COOLDOWN = 0.45

stop_requested = False


def stop_handler(signum, frame):
    global stop_requested
    stop_requested = True


def clamp(name, value):
    lo, hi = sorted(LIMITS[name])
    return max(lo, min(hi, value))


def move_toward(current, target, speed, dt):
    step = speed * dt
    diff = target - current

    if abs(diff) <= step:
        return float(target)

    if diff > 0:
        return float(current + step)

    return float(current - step)


def load_eye_detector():
    paths = [
        "/usr/share/opencv4/haarcascades/haarcascade_eye.xml",
        "/usr/share/opencv/haarcascades/haarcascade_eye.xml",
        "/usr/local/share/opencv4/haarcascades/haarcascade_eye.xml",
        "models/haarcascade_eye.xml"
    ]

    for path in paths:
        if os.path.exists(path):
            detector = cv2.CascadeClassifier(path)

            if not detector.empty():
                print("Eye detector:", path)
                return detector

    print("WARNING: haarcascade_eye.xml not found")
    print("Blink detection disabled")
    return None


def detect_face(detector, frame):
    detector.setInputSize(
        (frame.shape[1], frame.shape[0])
    )

    _, faces = detector.detect(frame)

    if faces is None:
        return None

    faces = [
        f for f in faces
        if float(f[14]) >= FACE_SCORE
    ]

    if not faces:
        return None

    return max(
        faces,
        key=lambda x: float(x[2] * x[3])
    )


def detect_eyes(eye_detector, frame, face):
    if eye_detector is None:
        return 2

    x, y, w, h = [
        int(v) for v in face[:4]
    ]

    x = max(0, x)
    y = max(0, y)

    x2 = min(
        frame.shape[1],
        x + w
    )

    y2 = min(
        frame.shape[0],
        y + h
    )

    roi = frame[y:y2, x:x2]

    if roi.size == 0:
        return 0

    gray = cv2.cvtColor(
        roi,
        cv2.COLOR_BGR2GRAY
    )

    gray = cv2.equalizeHist(gray)

    upper = gray[
        :int(gray.shape[0] * 0.65),
        :
    ]

    eyes = eye_detector.detectMultiScale(
        upper,
        scaleFactor=1.08,
        minNeighbors=5,
        minSize=(18, 18)
    )

    valid = []

    for ex, ey, ew, eh in eyes:
        if ey < upper.shape[0] * 0.70:
            valid.append(
                (ex, ey, ew, eh)
            )

    return len(valid)


def set_open_lids(servos):
    ud = servos.positions["UD"]

    offset = (
        (CENTER - ud) * 0.28
    )

    left_lid = 120.0 + offset
    right_lid = 60.0 - offset

    left_lid = clamp(
        "TL",
        left_lid
    )

    right_lid = clamp(
        "TR",
        right_lid
    )

    servos.set(
        "TL",
        left_lid
    )

    servos.set(
        "TR",
        right_lid
    )


def set_closed_lids(servos):
    servos.set("TL", 90)
    servos.set("TR", 90)


def draw_text(frame, text, y, color=(255, 255, 255)):
    cv2.putText(
        frame,
        text,
        (12, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        color,
        2,
        cv2.LINE_AA
    )


def return_to_rest(servos):
    for _ in range(100):

        servos.set(
            "LR",
            move_toward(
                servos.positions["LR"],
                CENTER,
                REST_SPEED,
                0.025
            )
        )

        servos.set(
            "UD",
            move_toward(
                servos.positions["UD"],
                CENTER,
                REST_SPEED,
                0.025
            )
        )

        servos.set(
            "BaseX",
            move_toward(
                servos.positions["BaseX"],
                CENTER,
                REST_SPEED,
                0.025
            )
        )

        servos.set(
            "BaseY",
            move_toward(
                servos.positions["BaseY"],
                CENTER,
                REST_SPEED,
                0.025
            )
        )

        servos.set("TL", 90)
        servos.set("TR", 90)

        time.sleep(0.025)

        if (
            abs(servos.positions["LR"] - CENTER) < 0.5
            and
            abs(servos.positions["UD"] - CENTER) < 0.5
            and
            abs(servos.positions["BaseX"] - CENTER) < 0.5
            and
            abs(servos.positions["BaseY"] - CENTER) < 0.5
        ):
            break

    servos.center_all()


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

    if not os.path.exists(MODEL):
        print("ERROR: Face model not found:")
        print(MODEL)
        return

    detector = cv2.FaceDetectorYN.create(
        MODEL,
        "",
        (FRAME_W, FRAME_H),
        FACE_SCORE,
        0.30,
        5000
    )

    eye_detector = load_eye_detector()

    servos = FollowerServos()

    camera = start_camera(
        FRAME_W,
        FRAME_H
    )

    servos.center_all()

    time.sleep(0.5)

    last_time = time.monotonic()
    last_face_time = last_time

    base_x_target = CENTER
    base_y_target = CENTER

    blink_until = 0.0
    last_blink = -10.0

    eye_open_frames = 0
    eye_closed_frames = 0
    blink_ready = False

    fps_time = last_time
    fps_frames = 0
    fps = 0.0

    status = "SYSTEM READY"

    print()
    print("====================================")
    print("   FOLLOWERBOT ADVANCED TRACKING")
    print("====================================")
    print("Q / ESC : Stop")
    print("Ctrl+C  : Safe shutdown")
    print()
    print("Starting camera and servos...")

    try:

        while not stop_requested:

            frame = get_frame(camera)

            now = time.monotonic()

            dt = now - last_time
            last_time = now

            if dt <= 0:
                dt = 0.01

            if dt > 0.05:
                dt = 0.05

            face = detect_face(
                detector,
                frame
            )

            frame_cx = FRAME_W // 2
            frame_cy = FRAME_H // 2

            face_found = False
            face_out = False

            if face is not None:

                x, y, w, h = [
                    int(v)
                    for v in face[:4]
                ]

                fx = int(
                    x + w / 2
                )

                fy = int(
                    y + h / 2
                )

                dx = fx - frame_cx
                dy = fy - frame_cy

                last_face_time = now
                face_found = True

                if w < MIN_FACE_WIDTH:

                    status = "FACE TOO FAR - MOVE CLOSER"

                else:

                    status = "FACE TRACKING"

                eye_target_x = (
                    CENTER +
                    dx * EYE_GAIN_X
                )

                eye_target_y = (
                    CENTER -
                    dy * EYE_GAIN_Y
                )

                eye_target_x = clamp(
                    "LR",
                    eye_target_x
                )

                eye_target_y = clamp(
                    "UD",
                    eye_target_y
                )

                if abs(dx) > EYE_DEADZONE:

                    new_lr = move_toward(
                        servos.positions["LR"],
                        eye_target_x,
                        EYE_SPEED,
                        dt
                    )

                    servos.set(
                        "LR",
                        new_lr
                    )

                if abs(dy) > EYE_DEADZONE:

                    new_ud = move_toward(
                        servos.positions["UD"],
                        eye_target_y,
                        EYE_SPEED,
                        dt
                    )

                    servos.set(
                        "UD",
                        new_ud
                    )

                if abs(dx) > BASE_DEADZONE:

                    direction = -1 if BASE_X_REVERSED else 1

                    base_x_target += (
                        direction *
                        dx *
                        BASE_X_SPEED *
                        dt
                        / 100.0
                    )

                if abs(dy) > BASE_DEADZONE:

                    base_y_target -= (
                        dy *
                        BASE_Y_SPEED *
                        dt
                        / 100.0
                    )

                base_x_target = clamp(
                    "BaseX",
                    base_x_target
                )

                base_y_target = clamp(
                    "BaseY",
                    base_y_target
                )

                bx_min, bx_max = sorted(
                    LIMITS["BaseX"]
                )

                by_min, by_max = sorted(
                    LIMITS["BaseY"]
                )

                x_at_limit = (
                    servos.positions["BaseX"] <= bx_min + 1
                    or
                    servos.positions["BaseX"] >= bx_max - 1
                )

                y_at_limit = (
                    servos.positions["BaseY"] <= by_min + 1
                    or
                    servos.positions["BaseY"] >= by_max - 1
                )

                pushing_x = abs(dx) > BASE_DEADZONE
                pushing_y = abs(dy) > BASE_DEADZONE

                if (
                    (x_at_limit and pushing_x)
                    or
                    (y_at_limit and pushing_y)
                ):
                    face_out = True
                    status = "FACE OUT OF RANGE - MOVE INTO VIEW"

                cv2.rectangle(
                    frame,
                    (x, y),
                    (x + w, y + h),
                    (0, 255, 0),
                    2
                )

                cv2.circle(
                    frame,
                    (fx, fy),
                    5,
                    (0, 0, 255),
                    -1
                )

                if (
                    eye_detector is not None
                    and
                    w >= 90
                    and
                    h >= 90
                ):

                    eye_count = detect_eyes(
                        eye_detector,
                        frame,
                        face
                    )

                    if eye_count >= 2:

                        eye_open_frames += 1
                        eye_closed_frames = 0

                        if eye_open_frames >= 2:
                            blink_ready = True

                    elif eye_count == 0:

                        eye_closed_frames += 1
                        eye_open_frames = 0

                        if (
                            blink_ready
                            and
                            eye_closed_frames >= 2
                            and
                            now - last_blink >= BLINK_COOLDOWN
                        ):

                            blink_until = (
                                now +
                                BLINK_CLOSE_TIME
                            )

                            last_blink = now
                            blink_ready = False
                            status = "HUMAN BLINK DETECTED"

                if now < blink_until:

                    set_closed_lids(
                        servos
                    )

                else:

                    set_open_lids(
                        servos
                    )

            else:

                time_without_face = (
                    now -
                    last_face_time
                )

                if (
                    time_without_face
                    >= NO_FACE_DELAY
                ):

                    base_x_target = CENTER
                    base_y_target = CENTER

                    servos.set(
                        "LR",
                        move_toward(
                            servos.positions["LR"],
                            CENTER,
                            REST_SPEED,
                            dt
                        )
                    )

                    servos.set(
                        "UD",
                        move_toward(
                            servos.positions["UD"],
                            CENTER,
                            REST_SPEED,
                            dt
                        )
                    )

                    status = "NO FACE - RETURNING TO REST"

                else:

                    status = "FACE LOST"

                set_open_lids(
                    servos
                )

                eye_open_frames = 0
                eye_closed_frames = 0
                blink_ready = False

            base_speed = (
                REST_SPEED
                if not face_found
                else BASE_X_SPEED
            )

            servos.set(
                "BaseX",
                move_toward(
                    servos.positions["BaseX"],
                    base_x_target,
                    base_speed,
                    dt
                )
            )

            servos.set(
                "BaseY",
                move_toward(
                    servos.positions["BaseY"],
                    base_y_target,
                    base_speed,
                    dt
                )
            )

            fps_frames += 1

            if now - fps_time >= 1.0:

                fps = (
                    fps_frames /
                    (now - fps_time)
                )

                fps_frames = 0
                fps_time = now

            cv2.drawMarker(
                frame,
                (frame_cx, frame_cy),
                (255, 255, 255),
                cv2.MARKER_CROSS,
                24,
                2
            )

            draw_text(
                frame,
                status,
                25,
                (0, 255, 255)
            )

            draw_text(
                frame,
                f"LR: {servos.positions['LR']:.0f}  "
                f"UD: {servos.positions['UD']:.0f}",
                50
            )

            draw_text(
                frame,
                f"BaseX: {servos.positions['BaseX']:.0f}  "
                f"BaseY: {servos.positions['BaseY']:.0f}",
                75
            )

            draw_text(
                frame,
                f"Left Lid: {servos.positions['TL']:.0f}  "
                f"Right Lid: {servos.positions['TR']:.0f}",
                100
            )

            draw_text(
                frame,
                f"FPS: {fps:.1f}",
                125
            )

            draw_text(
                frame,
                "Q / ESC = STOP + RETURN TO REST",
                FRAME_H - 12
            )

            cv2.imshow(
                "FollowerBot Face Tracking",
                frame
            )

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q") or key == 27:
                stop_requested = True

    except Exception as e:

        print()
        print("ERROR:", e)

    finally:

        print()
        print("Stopping FollowerBot...")
        print("Returning servos to rest position...")

        try:
            return_to_rest(servos)
        except Exception as e:
            print("Rest-position error:", e)

        try:
            camera.stop()
        except Exception:
            pass

        cv2.destroyAllWindows()

        try:
            servos.close()
        except Exception:
            pass

        print("FollowerBot stopped safely.")
        print("All servos returned to rest position.")


if __name__ == "__main__":
    main()
