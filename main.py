#!/usr/bin/env python3
import os

from uptonight.uptonight import calc

longitude = os.getenv("LONGITUDE")
latitude = os.getenv("LATITUDE")
elevation = int(os.getenv("ELEVATION"))
timezone = os.getenv("TIMEZONE")
pressure = float(os.getenv("PRESSURE", 0))
relative_humidity = float(os.getenv("RELATIVE_HUMIDITY", 0))
temperature = float(os.getenv("TEMPERATURE", 0))


def main():
    calc(longitude, latitude, elevation, timezone, pressure, relative_humidity, temperature)


if __name__ == "__main__":
    main()
