#!/usr/bin/env python3
import os
import logging
import sys
import time
from time import sleep

from uptonight.uptonight import calc

_LOGGER = logging.getLogger(__name__)
logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s (%(threadName)s) [%(funcName)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

longitude = os.getenv("LONGITUDE")
latitude = os.getenv("LATITUDE")
elevation = int(os.getenv("ELEVATION"))
timezone = os.getenv("TIMEZONE")
pressure = float(os.getenv("PRESSURE", 0))
relative_humidity = float(os.getenv("RELATIVE_HUMIDITY", 0))
temperature = float(os.getenv("TEMPERATURE", 0))
observation_date = os.getenv("OBSERVATION_DATE", None)
target_list = os.getenv("TARGET_LIST", None)
type_filter = os.getenv("TYPE_FILTER", "")
output_dir = os.getenv("OUTPUT_DIR", "out")
mode = os.getenv("MODE", "otc")


def main():
    if mode == "live":
        _LOGGER.info("UpTonight live mode")
        while True:
            calc(
                longitude,
                latitude,
                elevation,
                timezone,
                pressure,
                relative_humidity,
                temperature,
                observation_date,
                target_list,
                type_filter,
                output_dir,
                True,
            )
            sleep(300)
    else:
        _LOGGER.info("UpTonight one-time calculation mode")
        calc(
            longitude,
            latitude,
            elevation,
            timezone,
            pressure,
            relative_humidity,
            temperature,
            observation_date,
            target_list,
            type_filter,
            output_dir,
            False,
        )


if __name__ == "__main__":
    main()
