import time
from servo_controller import FollowerServos

servos = FollowerServos()

try:
    print("FIRST TEST: remove servo horns/linkages.")
    for name in ["LR", "UD", "TL", "TR", "BaseX", "BaseY"]:
        print("Testing", name)
        for angle in [90, 80, 90, 100, 90]:
            servos.set(name, angle)
            time.sleep(1)
finally:
    servos.center_all()
    time.sleep(1)
    servos.close()
