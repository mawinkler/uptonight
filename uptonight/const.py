ALTITUDE_CONSTRAINT_MIN = 30  # in deg above horizon
ALTITUDE_CONSTRAINT_MAX = 80  # in deg above horizon
AIRMASS_CONSTRAINT = 2  # 30° to 90°
SIZE_CONSTRAINT_MIN = 10  # in arc minutes
SIZE_CONSTRAINT_MAX = 300  # in arc minutes
MOON_SEPARATION_MIN = 45  # in degrees

# object needs to be within the constraints for at least 80% of darkness
FRACTION_OF_TIME_OBSERVABLE_THRESHOLD = 0.80

# True : meaning that azimuth is shown increasing counter-clockwise (CCW), or with North
#        at top, East at left, etc.
# False: Show azimuth increasing clockwise (CW).
NORTH_TO_EAST_CCW = False

# Default target list to use
DEFAULT_TARGETS = "targets/GaryImm"

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
