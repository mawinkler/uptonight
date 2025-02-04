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

# Solar System
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

# Default Live Mode Interval
DEFAULT_LIVE_MODE_INTERVAL = 900