import time
from servo_controller import FollowerServos


servos = FollowerServos()


def move(name, angle):
    print(f"{name}: {angle}°")
    servos.set(name, angle)
    servos.flush()
    time.sleep(1)


try:

    print()
    print("SERVO MOVEMENT TEST")
    print("===================")

    servos.center_all()

    print()
    print("Testing LR")
    move("LR", 120)
    move("LR", 60)
    move("LR", 90)

    print()
    print("Testing UD")
    move("UD", 120)
    move("UD", 60)
    move("UD", 90)

    print()
    print("Testing BaseX")
    move("BaseX", 120)
    move("BaseX", 60)
    move("BaseX", 90)

    print()
    print("Testing BaseY")
    move("BaseY", 130)
    move("BaseY", 40)
    move("BaseY", 90)

    print()
    print("Testing TL")
    move("TL", 130)
    move("TL", 90)

    print()
    print("Testing TR")
    move("TR", 50)
    move("TR", 90)

    print()
    print("ALL TESTS COMPLETE")

finally:

    servos.center_all()
    time.sleep(0.5)
    servos.close()
