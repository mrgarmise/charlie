import time
from hardware.system import cpu, memory

def clear():
    print("\033[2J\033[H", end="")  # terminal clear

def draw():
    print("=========================")
    print("|    CYBERDECK CORE     |")
    print("=========================")
    print(f"| CPU:  {cpu():5.1f}%         |")
    print(f"| MEM:  {memory():5.1f}%         |")
    print(f"| TIME: {time.strftime('%H:%M:%S')}        |")
    print("=========================")
    print("| VISION:  STANDBY     |")
    print("| CAMERA:  NOT READY   |")
    print("| MOTION:  OFFLINE     |")
    print("=========================")

def main():
    while True:
        clear()
        draw()
        time.sleep(1)

if __name__ == "__main__":
    main()
