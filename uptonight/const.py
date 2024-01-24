ALTITUDE_CONSTRAINT_MIN = 30  # in deg above horizon
ALTITUDE_CONSTRAINT_MAX = 80  # in deg above horizon
AIRMASS_CONSTRAINT = 2  # 30° to 90°
SIZE_CONSTRAINT_MIN = 10  # in arc minutes
SIZE_CONSTRAINT_MAX = 300  # in arc minutes
MOON_SEPARATION_MIN = 45  # in degrees

# Object needs to be within the constraints for at least 50% of darkness
FRACTION_OF_TIME_OBSERVABLE_THRESHOLD = 0.5

# Maximum number of targets to calculate
MAX_NUMBER_WITHIN_THRESHOLD = 60

# True : meaning that azimuth is shown increasing counter-clockwise (CCW), or with North
#        at top, East at left, etc.
# False: Show azimuth increasing clockwise (CW).
NORTH_TO_EAST_CCW = False

# Default target list to use
DEFAULT_TARGETS = "targets/GaryImm"

# Solar System
BODIES = [
    ("Sun", "sun", "gold", 250),
    ("Moon", "moon", "lightgrey", 150),
    ("Mercury", "mercury", "pink", 20),
    ("Venus", "venus", "rosybrown", 30),
    ("Mars", "mars", "red", 30),
    ("Jupiter", "jupiter", "chocolate", 50),
    ("Saturn", "saturn", "khaki", 45),
    ("Uranus", "uranus", "lightsteelblue", 20),
    ("Neptune", "neptune", "royalblue", 15),
]

# Any custom target you want to include in the calculations
CUSTOM_TARGETS = [
    {
        "name": "NGC 4395",
        "description": "NGC 4395",
        "type": "Galaxy",
        "constellation": "Canes Venatici",
        "size": 13,
        "ra": "12 25 48",
        "dec": "+33 32 48",
    },
    {
        "name": "NGC 3227",
        "description": "Galaxy duo NGC 3226",
        "type": "Galaxy",
        "constellation": "Leo",
        "size": 4,
        "ra": "10 23 30",
        "dec": "+19 51 54",
    },
]
