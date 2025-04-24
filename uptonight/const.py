#
# Config
#
FEATURE_OBJECTS = "objects"
FEATURE_BODIES = "bodies"
FEATURE_COMETS = "comets"
FEATURE_HORIZON = "horizon"

# LAYOUT = "layout"
LAYOUT_LANDSCAPE = "landscape"
LAYOUT_PORTRAIT = "portrait"

#
# Constraints
#
DEFAULT_ALTITUDE_CONSTRAINT_MIN = 30  # in deg above horizon
DEFAULT_ALTITUDE_CONSTRAINT_MAX = 80  # in deg above horizon
DEFAULT_AIRMASS_CONSTRAINT = 2  # 30° to 90°
DEFAULT_SIZE_CONSTRAINT_MIN = 10  # in arc minutes
DEFAULT_SIZE_CONSTRAINT_MAX = 300  # in arc minutes

DEFAULT_MOON_SEPARATION_MIN = 45  # in degrees
DEFAULT_MOON_SEPARATION_USE_ILLUMINATION = True

# Object needs to be within the constraints for at least 50% of darkness
DEFAULT_FRACTION_OF_TIME_OBSERVABLE_THRESHOLD = 0.5

# Maximum number of targets to calculate
DEFAULT_MAX_NUMBER_WITHIN_THRESHOLD = 60

# True : meaning that azimuth is shown increasing counter-clockwise (CCW), or with North
#        at top, East at left, etc.
# False: Show azimuth increasing clockwise (CW).
DEFAULT_NORTH_TO_EAST_CCW = False

# Default target list to use
DEFAULT_TARGETS = "targets/GaryImm"

# Default magnitude limit (comets)
DEFAULT_MAGNITUDE_LIMIT = 12

# Default Live Mode Interval
DEFAULT_LIVE_MODE_INTERVAL = 900

#
# Solar System
#
BODIES = [
    ("Sun", "sun", "gold", 250, 10),
    ("Moon", "moon", "lightgrey", 150, 301),
    ("Mercury", "mercury", "pink", 20, 199),
    ("Venus", "venus", "rosybrown", 30, 299),
    ("Mars", "mars", "red", 30, 499),
    ("Jupiter", "jupiter", "chocolate", 50, 599),
    ("Saturn", "saturn", "khaki", 45, 699),
    ("Uranus", "uranus", "lightsteelblue", 20, 799),
    ("Neptune", "neptune", "royalblue", 15, 899),
]

#
# MQTT
#
MANUFACTURER = "UpTonight"

DEVICE_TYPE_UPTONIGHT = "uptonight"
DEVICE_TYPE_UPTONIGHT_ICON = "mdi:telescope"
DEVICE_TYPE_CAMERA = "camera"
DEVICE_TYPE_CAMERA_ICON = "mdi:camera"

SENSOR_TYPE = 0
SENSOR_NAME = 1
SENSOR_UNIT = 2
SENSOR_ICON = 3
SENSOR_DEVICE_CLASS = 4
SENSOR_STATE_CLASS = 5

STATE_ON = "on"
STATE_OFF = "off"

TYPE_SENSOR = "sensor"

UNIT_OF_MEASUREMENT_NONE = None
UNIT_OF_MEASUREMENT_DEGREE = "°"
UNIT_OF_MEASUREMENT_PERCENTAGE = "%"
UNIT_OF_MEASUREMENT_ARCMIN = "'"
UNIT_OF_MEASUREMENT_METER = "m"

DEVICE_CLASS_NONE = None
DEVICE_CLASS_TEMPERATURE = "temperature"
DEVICE_CLASS_TIMESTAMP = "timestamp"
DEVICE_CLASS_DISTANCE = "distance"

STATE_CLASS_NONE = None
STATE_CLASS_MEASUREMENT = "measurement"

FUNCTIONS = {
    DEVICE_TYPE_UPTONIGHT: (
        [
            TYPE_SENSOR,
            "Count",
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_UPTONIGHT_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
    ),
    DEVICE_TYPE_CAMERA: (
        [
            TYPE_SENSOR,
            "Plot",
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_CAMERA_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
    ),
}
