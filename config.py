"""
config.py

Global configuration for the Pico Agent
Cyberdeck Project
"""

# ==========================================================
# SERVO GPIO PINS
# ==========================================================

HEAD_A_PAN_PIN = 4
HEAD_A_TILT_PIN = 5

HEAD_B_PAN_PIN = 14
HEAD_B_TILT_PIN = 15

# ==========================================================
# PWM
# ==========================================================

PWM_FREQUENCY = 50

SERVO_MIN_US = 500
SERVO_CENTER_US = 1500
SERVO_MAX_US = 2500

# Degrees

PAN_MIN = 0
PAN_MAX = 180

TILT_MIN = 20
TILT_MAX = 160

HOME_PAN = 90
HOME_TILT = 90

# ==========================================================
# MOTION
# ==========================================================

UPDATE_RATE_HZ = 50

MAX_SPEED = 3.0
MAX_ACCEL = 0.15

MICROSACCADE_INTERVAL = (2500,7000)

BLINK_INTERVAL = (3000,9000)

SCAN_SPEED = 0.45

# ==========================================================
# SERIAL
# ==========================================================

UART_BAUD = 115200

COMMAND_BUFFER = 128

HEARTBEAT_TIMEOUT = 5.0

# ==========================================================
# MODES
# ==========================================================

MODE_IDLE = "IDLE"
MODE_SCAN = "SCAN"
MODE_TRACK = "TRACK"
MODE_SLEEP = "SLEEP"
MODE_HOME = "HOME"
MODE_CALIBRATE = "CAL"

# ==========================================================
# EXPRESSIONS
# ==========================================================

FACE_NEUTRAL = "NEUTRAL"
FACE_HAPPY = "HAPPY"
FACE_THINK = "THINK"
FACE_LOCK = "LOCK"
FACE_ERROR = "ERROR"
FACE_SLEEP = "SLEEP"

DEFAULT_FACE = FACE_NEUTRAL
