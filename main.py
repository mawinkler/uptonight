#!/usr/bin/env python3
import logging
import os
import sys
import time
from time import sleep

import yaml

from uptonight.const import (
    DEFAULT_AIRMASS_CONSTRAINT,
    DEFAULT_ALTITUDE_CONSTRAINT_MAX,
    DEFAULT_ALTITUDE_CONSTRAINT_MIN,
    DEFAULT_FRACTION_OF_TIME_OBSERVABLE_THRESHOLD,
    DEFAULT_MAX_NUMBER_WITHIN_THRESHOLD,
    DEFAULT_MOON_SEPARATION_MIN,
    DEFAULT_MOON_SEPARATION_USE_ILLUMINATION,
    DEFAULT_NORTH_TO_EAST_CCW,
    DEFAULT_SIZE_CONSTRAINT_MAX,
    DEFAULT_SIZE_CONSTRAINT_MIN,
    DEFAULT_TARGETS,
)
from uptonight.uptonight import UpTonight

_LOGGER = logging.getLogger(__name__)
logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s (%(threadName)s) [%(funcName)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def main():
    
    # Defaults
    location = {"longitude": "", "latitude": "", "elevation": 0, "timezone": "UTC"}
    environment = {"pressure": 0, "temperature": 0, "relative_humidity": 0}
    constraints = {
        "altitude_constraint_min": DEFAULT_ALTITUDE_CONSTRAINT_MIN,
        "altitude_constraint_max": DEFAULT_ALTITUDE_CONSTRAINT_MAX,
        "airmass_constraint": DEFAULT_AIRMASS_CONSTRAINT,
        "size_constraint_min": DEFAULT_SIZE_CONSTRAINT_MIN,
        "size_constraint_max": DEFAULT_SIZE_CONSTRAINT_MAX,
        "moon_separation_min": DEFAULT_MOON_SEPARATION_MIN,
        "moon_separation_use_illumination": DEFAULT_MOON_SEPARATION_USE_ILLUMINATION,
        "fraction_of_time_observable_threshold": DEFAULT_FRACTION_OF_TIME_OBSERVABLE_THRESHOLD,
        "max_number_within_threshold": DEFAULT_MAX_NUMBER_WITHIN_THRESHOLD,
        "north_to_east_ccw": DEFAULT_NORTH_TO_EAST_CCW,
    }
    observation_date = None
    target_list = DEFAULT_TARGETS
    type_filter = ""
    output_dir = "out"
    live_mode = False
    bucket_list = []
    done_list = []

    # Read config.yaml
    if os.path.isfile("config.yaml"):
        with open("config.yaml", "r", encoding="utf-8") as ymlfile:
            cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)
    else:
        cfg = None

    if cfg is not None and "location" in cfg.keys():
        for item in cfg["location"].items():
            if item[1] is not None:
                location[item[0]] = item[1]

    if cfg is not None and "environment" in cfg.keys():
        for item in cfg["environment"].items():
            if item[1] is not None:
                environment[item[0]] = item[1]

    if cfg is not None and "constraints" in cfg.keys():
        for item in cfg["constraints"].items():
            if item[1] is not None:
                constraints[item[0]] = item[1]

    if cfg is not None and "observation_date" in cfg.keys() and cfg["observation_date"] is not None:
        observation_date = cfg["observation_date"]
    if cfg is not None and "target_list" in cfg.keys() and cfg["target_list"] is not None:
        target_list = cfg["target_list"]
    if cfg is not None and "type_filter" in cfg.keys() and cfg["type_filter"] is not None:
        type_filter = cfg["type_filter"]
    if cfg is not None and "output_dir" in cfg.keys() and cfg["output_dir"] is not None:
        output_dir = cfg["output_dir"]
    if cfg is not None and "live_mode" in cfg.keys() and cfg["live_mode"] is not None:
        live_mode = bool(cfg["live_mode"])
    if cfg is not None and "bucket_list" in cfg.keys() and cfg["bucket_list"] is not None:
        bucket_list = cfg["bucket_list"]
    if cfg is not None and "done_list" in cfg.keys() and cfg["done_list"] is not None:
        done_list = cfg["done_list"]

    if os.getenv("LONGITUDE") is not None:
        location["longitude"] = os.getenv("LONGITUDE")
    if os.getenv("LATITUDE") is not None:
        location["latitude"] = os.getenv("LATITUDE")
    if os.getenv("ELEVATION") is not None:
        location["elevation"] = int(os.getenv("ELEVATION"))
    if os.getenv("TIMEZONE") is not None:
        location["timezone"] = os.getenv("TIMEZONE")

    if os.getenv("PRESSURE") is not None:
        environment["pressure"] = float(os.getenv("PRESSURE"))
    if os.getenv("TEMPERATURE") is not None:
        environment["temperature"] = float(os.getenv("TEMPERATURE"))
    if os.getenv("RELATIVE_HUMIDITY") is not None:
        environment["relative_humidity"] = float(os.getenv("RELATIVE_HUMIDITY"))

    if os.getenv("OBSERVATION_DATE") is not None:
        observation_date = os.getenv("OBSERVATION_DATE")
    if os.getenv("TARGET_LIST") is not None:
        target_list = os.getenv("TARGET_LIST")
    if os.getenv("TYPE_FILTER") is not None:
        type_filter = os.getenv("TYPE_FILTER")
    if os.getenv("OUTPUT_DIR") is not None:
        output_dir = os.getenv("OUTPUT_DIR")
    if os.getenv("LIVE_MODE") is not None:
        if os.getenv("LIVE_MODE").lower() == "true":
            live_mode = True

    # We need at least a longitute and latitude, the rest is optional
    if location["longitude"] == "" or location["latitude"] == "":
        _LOGGER.error("Longitute and/or latitude not set")
        sys.exit(0)

    _LOGGER.debug(f"Location longitude: {location['longitude']}")
    _LOGGER.debug(f"Location latitude: {location['latitude']}")
    _LOGGER.debug(f"Location elevation: {location['elevation']}")
    _LOGGER.debug(f"Location timezone: {location['timezone']}")

    _LOGGER.debug(f"Environment pressure: {environment['pressure']}")
    _LOGGER.debug(f"Environment temperature: {environment['temperature']}")
    _LOGGER.debug(f"Environment relative_humidity: {environment['relative_humidity']}")

    _LOGGER.debug(f"Altitude constraint min: {constraints['altitude_constraint_min']}")
    _LOGGER.debug(f"Altitude constraint max: {constraints['altitude_constraint_max']}")
    _LOGGER.debug(f"Airmass constraint: {constraints['airmass_constraint']}")
    _LOGGER.debug(f"Size constraint min: {constraints['size_constraint_min']}")
    _LOGGER.debug(f"Size constraint max: {constraints['size_constraint_max']}")
    _LOGGER.debug(f"Moon separation min: {constraints['moon_separation_min']}")
    _LOGGER.debug(f"Moon separation use illumination: {constraints['moon_separation_use_illumination']}")
    _LOGGER.debug(f"Fraction of time observable threshold: {constraints['fraction_of_time_observable_threshold']}")
    _LOGGER.debug(f"Max number within threshold: {constraints['max_number_within_threshold']}")
    _LOGGER.debug(f"North to East ccw: {constraints['north_to_east_ccw']}")

    _LOGGER.debug(f"Observation date: {observation_date}")
    _LOGGER.debug(f"Target list: {target_list}")
    _LOGGER.debug(f"Type filter: {type_filter}")
    _LOGGER.debug(f"Output directory: {output_dir}")
    _LOGGER.debug(f"Mode: {live_mode}")

    start = time.time()
    
    # Initialize UpTonight
    uptonight = UpTonight(
        location=location,
        environment=environment,
        constraints=constraints,
        target_list=target_list,
        bucket_list=bucket_list,
        done_list=done_list,
        observation_date=observation_date,
        type_filter=type_filter,
        output_dir=output_dir,
        live=live_mode,
    )
    
    # Do the math
    if live_mode:
        _LOGGER.info("UpTonight live mode")
        while True:
            uptonight.calc(
                bucket_list=bucket_list,
                done_list=done_list,
                type_filter=type_filter,
            )
            sleep(300)
    else:
        _LOGGER.info("UpTonight one-time calculation mode")
        uptonight.calc(
            bucket_list=bucket_list,
            done_list=done_list,
            type_filter=type_filter,
        )
        
    end = time.time()
    _LOGGER.info(f"Execution time: %s seconds", end - start)


if __name__ == "__main__":
    main()
