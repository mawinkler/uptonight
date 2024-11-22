#!/usr/bin/env python3
import logging
import math
import os
import pathlib
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
    """Main"""
    # Determine if application is a script file or frozen exe
    if getattr(sys, "frozen", False):
        app_directory = "/app"
        _LOGGER.debug(f"UpTonight running frozen, app directory set to {app_directory}")
    elif __file__:
        app_directory = pathlib.Path(__file__).parent.resolve()
        _LOGGER.debug(f"UpTonight running as script file, app directory set to {app_directory}")

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
    target_list = f"{app_directory}/{DEFAULT_TARGETS}"
    type_filter = ""
    output_dir = f"{app_directory}/out"
    live = {}
    bucket_list = []
    done_list = []
    custom_targets = []
    horizon = None
    horizon_filled = None
    colors = {
        "ticks": "#9C9C9C",
        "grid": "#9C9C9C",
        "axes": "#262626",
        "figure": "#1C1C1C",
        "legend": "#262626",
        "alttime": "#CC6666",
        "meridian": "#66CC66",
        "text": "#FFFFFF",
    }
    features = {"horizon": False, "objects": True, "bodies": True, "comets": False, "alttime": False}
    output_datestamp = False

    # Read config.yaml
    if os.path.isfile(f"{app_directory}/config.yaml"):
        with open(f"{app_directory}/config.yaml", "r", encoding="utf-8") as ymlfile:
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

    if cfg is not None and "colors" in cfg.keys():
        for item in cfg["colors"].items():
            if item[1] is not None:
                colors[item[0]] = item[1]

    if cfg is not None and "live" in cfg.keys():
        for item in cfg["live"].items():
            if item[1] is not None:
                live[item[0]] = item[1]

    if cfg is not None and "observation_date" in cfg.keys() and cfg["observation_date"] is not None:
        observation_date = cfg["observation_date"]
    if cfg is not None and "target_list" in cfg.keys() and cfg["target_list"] is not None:
        target_list = cfg["target_list"]
    if cfg is not None and "type_filter" in cfg.keys() and cfg["type_filter"] is not None:
        type_filter = cfg["type_filter"]
    if cfg is not None and "output_dir" in cfg.keys() and cfg["output_dir"] is not None:
        output_dir = f"{app_directory}/{cfg['output_dir']}"
    if cfg is not None and "live_mode" in cfg.keys() and cfg["live_mode"] is not None:  # deprecated
        live = {"enabled": bool(cfg["live_mode"]), "interval": 300}
    if cfg is not None and "bucket_list" in cfg.keys() and cfg["bucket_list"] is not None:
        bucket_list = cfg["bucket_list"]
    if cfg is not None and "done_list" in cfg.keys() and cfg["done_list"] is not None:
        done_list = cfg["done_list"]
    if cfg is not None and "custom_targets" in cfg.keys() and cfg["custom_targets"] is not None:
        custom_targets = cfg["custom_targets"]
    if cfg is not None and "horizon" in cfg.keys() and cfg["horizon"] is not None:
        horizon = cfg["horizon"]
    if cfg is not None and "colors" in cfg.keys() and cfg["colors"] is not None:
        colors = cfg["colors"]
    if cfg is not None and "features" in cfg.keys() and cfg["features"] is not None:
        features = cfg["features"]
    if cfg is not None and "output_datestamp" in cfg.keys() and cfg["output_datestamp"] is not None:
        output_datestamp = cfg["output_datestamp"]

    if horizon is not None:
        # Fill space in between anchor points
        step_size = horizon.get("step_size", 4)
        anchor_points = horizon.get("anchor_points", [])

        horizon_filled = []
        for index, horizon_direction in enumerate(anchor_points):
            az_start = horizon_direction.get("az")
            alt_start = horizon_direction.get("alt")
            az_stop = anchor_points[index + 1].get("az")
            alt_stop = anchor_points[index + 1].get("alt")

            distance = math.sqrt((alt_stop - alt_start) ** 2 + (az_stop - az_start) ** 2)
            steps = round(distance / step_size, 0)
            if steps == 0:
                steps = 1
            inc_alt = (alt_stop - alt_start) / steps
            inc_az = (az_stop - az_start) / steps

            for step in range(0, int(steps)):
                horizon_filled.append({"alt": alt_start + inc_alt * step, "az": az_start + inc_az * step})

            if index == len(anchor_points) - 2:
                break

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
            live = {"enabled": True, "interval": 300}

    # We need at least a longitute and latitude, the rest is optional
    if location["longitude"] == "" or location["latitude"] == "":
        _LOGGER.error("Longitute and/or latitude not set")
        sys.exit(0)

    _LOGGER.debug(f"Location longitude: {location['longitude']}")
    _LOGGER.debug(f"Location latitude: {location['latitude']}")
    _LOGGER.debug(f"Location elevation: {location['elevation']}")
    _LOGGER.debug(f"Location timezone: {location['timezone']}")
    _LOGGER.debug(f"Observation date: {observation_date}")
    _LOGGER.debug(f"Colors: {colors}")
    _LOGGER.debug(f"Features: {features}")
    _LOGGER.debug(f"Output datestamp: {output_datestamp}")

    _LOGGER.debug(f"Environment pressure: {environment['pressure']}")
    _LOGGER.debug(f"Environment temperature: {environment['temperature']}")
    _LOGGER.debug(f"Environment relative_humidity: {environment['relative_humidity']}")

    _LOGGER.debug(f"DSO Altitude constraint min: {constraints['altitude_constraint_min']}")
    _LOGGER.debug(f"DSO Altitude constraint max: {constraints['altitude_constraint_max']}")
    _LOGGER.debug(f"DSO Airmass constraint: {constraints['airmass_constraint']}")
    _LOGGER.debug(f"DSO Size constraint min: {constraints['size_constraint_min']}")
    _LOGGER.debug(f"DSO Size constraint max: {constraints['size_constraint_max']}")
    _LOGGER.debug(f"DSO Fraction of time observable threshold: {constraints['fraction_of_time_observable_threshold']}")
    _LOGGER.debug(f"DSO Max number within threshold: {constraints['max_number_within_threshold']}")
    _LOGGER.debug(f"DSO Moon separation min: {constraints['moon_separation_min']}")
    _LOGGER.debug(f"DSO Moon separation use illumination: {constraints['moon_separation_use_illumination']}")
    _LOGGER.debug(f"DSO Target list: {target_list}")
    _LOGGER.debug(f"DSO Type filter: {type_filter}")

    _LOGGER.debug(f"North to East ccw: {constraints['north_to_east_ccw']}")
    _LOGGER.debug(f"Output directory: {output_dir}")
    _LOGGER.debug(f"Live mode: {live.get('enabled', False)}")
    _LOGGER.debug(f"Live mode interval: {live.get('interval', 300)}")

    start = time.time()

    # Do the math
    if live.get("enabled"):
        _LOGGER.info("UpTonight live mode")
        while True:
            # Initialize UpTonight
            uptonight = UpTonight(
                location=location,
                features=features,
                colors=colors,
                output_datestamp=output_datestamp,
                environment=environment,
                constraints=constraints,
                target_list=target_list,
                bucket_list=bucket_list,
                done_list=done_list,
                custom_targets=custom_targets,
                observation_date=observation_date,
                type_filter=type_filter,
                output_dir=output_dir,
                live=live.get("enabled"),
            )

            uptonight.calc(
                bucket_list=bucket_list,
                done_list=done_list,
                type_filter=type_filter,
                horizon=horizon_filled,
            )
            sleep(live.get("interval", 300))
    else:
        _LOGGER.info("UpTonight one-time calculation mode")

        # Initialize UpTonight
        uptonight = UpTonight(
            location=location,
            features=features,
            colors=colors,
            output_datestamp=output_datestamp,
            environment=environment,
            constraints=constraints,
            target_list=target_list,
            bucket_list=bucket_list,
            done_list=done_list,
            custom_targets=custom_targets,
            observation_date=observation_date,
            type_filter=type_filter,
            output_dir=output_dir,
            live=False,
        )

        uptonight.calc(
            bucket_list=bucket_list,
            done_list=done_list,
            type_filter=type_filter,
            horizon=horizon_filled,
        )

    end = time.time()
    _LOGGER.info(f"Execution time: %s seconds", end - start)


if __name__ == "__main__":
    main()
