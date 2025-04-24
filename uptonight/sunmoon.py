import logging
import warnings
from datetime import UTC, datetime

from astroplan.exceptions import TargetAlwaysUpWarning, TargetNeverUpWarning
from astropy import units as u
from astropy.time import Time

_LOGGER = logging.getLogger(__name__)


class SunMoon:
    """UpTonight Target Generation"""

    def __init__(
        self,
        observer,
        observation_date=None,
        utcoffset=0,
    ):
        self._observer = observer
        self._darkness = None
        self._sun_next_setting = None
        self._sun_next_rising = None
        self._sun_next_setting_civil = None
        self._sun_next_setting_civil_short = None
        self._sun_next_rising_civil = None
        self._sun_next_rising_civil_short = None
        self._moon_illumination = None
        self._moon_next_setting_short = None
        self._moon_next_rising_short = None

        # Calculate tonights night unless a date is given
        if observation_date is None:
            time = (
                Time(
                    datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0),
                    scale="utc",
                    location=self._observer.location,
                )
                + 12 * u.hour
                - utcoffset * u.hour
            )
        else:
            time = (
                Time(
                    datetime.strptime(observation_date, "%m/%d/%y").replace(hour=0, minute=0, second=0, microsecond=0),
                    scale="utc",
                    location=self._observer.location,
                )
                + 12 * u.hour
                - utcoffset * u.hour
            )
        _LOGGER.info("Calculating for: {0}".format(time.strftime("%m/%d/%Y %H:%M:%S")))
        _LOGGER.info("UTC offset: {0}".format(utcoffset))

        self._sun(time)
        self._moon(time, self._sun_next_setting)

        _LOGGER.info("Sun set {0}: {1}".format(self._darkness, self._sun_next_setting.strftime("%m/%d/%Y %H:%M:%S")))
        _LOGGER.info("Sun rise {0}: {1}".format(self._darkness, self._sun_next_rising.strftime("%m/%d/%Y %H:%M:%S")))
        _LOGGER.info("Moon illumination: {:.0f}%".format(self._moon_illumination))

        return None

    def darkness(self) -> str:
        if self._darkness is not None:
            return self._darkness
        return None

    def sun_next_setting(self) -> Time:
        if self._sun_next_setting is not None:
            return self._sun_next_setting
        return None

    def sun_next_rising(self) -> Time:
        if self._sun_next_rising is not None:
            return self._sun_next_rising
        return None

    def sun_next_setting_civil(self) -> Time:
        if self._sun_next_setting_civil is not None:
            return self._sun_next_setting_civil
        return None

    def sun_next_setting_civil_short(self) -> Time:
        if self._sun_next_setting_civil_short is not None:
            return self._sun_next_setting_civil_short
        return None

    def sun_next_rising_civil(self) -> Time:
        if self._sun_next_rising_civil is not None:
            return self._sun_next_rising_civil
        return None

    def sun_next_rising_civil_short(self) -> Time:
        if self._sun_next_rising_civil_short is not None:
            return self._sun_next_rising_civil_short
        return None

    def sun_altitude(self) -> float:
        altitude = self._observer.sun_altaz(datetime.now(UTC)).alt.degree
        _LOGGER.debug("Sun altitude: {0}".format(altitude))
        return altitude

    def moon_illumination(self) -> int:
        if self._moon_illumination is not None:
            return self._moon_illumination
        return None

    def moon_next_setting_short(self) -> Time:
        if self._moon_next_setting_short is not None:
            return self._moon_next_setting_short
        return None

    def moon_next_rising_short(self) -> Time:
        if self._moon_next_rising_short is not None:
            return self._moon_next_rising_short
        return None

    def _sun(self, time):
        """Calculate the Sun rise, set, and the type of darkness to expect.

        Args:
            time (Time): Calculation time
        """

        darkness = ""
        with warnings.catch_warnings(record=True) as w:
            sun_next_setting = self._observer.sun_set_time(time, which="next", horizon=-18 * u.deg)
            if len(w):
                if issubclass(w[-1].category, TargetAlwaysUpWarning):
                    _LOGGER.warning("Sun is not setting astronomically")
                    w.clear()
                    sun_next_setting = self._observer.sun_set_time(time, which="next", horizon=-12 * u.deg)
                    if len(w):
                        if issubclass(w[-1].category, TargetAlwaysUpWarning):
                            _LOGGER.warning("Sun is not setting nautically")
                            w.clear()
                            sun_next_setting = self._observer.sun_set_time(time, which="next", horizon=-6 * u.deg)
                            if len(w):
                                if issubclass(w[-1].category, TargetAlwaysUpWarning):
                                    _LOGGER.warning("Sun is not setting civically")
                                    sun_next_rising = time + 1 * u.day
                                    sun_next_setting = time
                            else:
                                darkness = "civil"
                                sun_next_setting, sun_next_rising = self._observer.tonight(
                                    time=time, horizon=-6 * u.deg
                                )
                    else:
                        darkness = "nautical"
                        sun_next_setting, sun_next_rising = self._observer.tonight(time=time, horizon=-12 * u.deg)
            else:
                darkness = "astronomical"
                sun_next_setting, sun_next_rising = self._observer.tonight(time=time, horizon=-18 * u.deg)
            # TODO: Proper handling for sun never up
            if len(w):
                if issubclass(w[-1].category, TargetNeverUpWarning):
                    _LOGGER.warning("Sun is not rising astronomically")
                    sun_next_rising = time + 1 * u.day
                    sun_next_setting = time
                w.clear()

        sun_next_setting_civil, sun_next_rising_civil = self._observer.tonight(time=time, horizon=-6 * u.deg)
        sun_next_setting_civil_short = self._observer.astropy_time_to_datetime(
            self._observer.sun_set_time(time, which="next", horizon=-6 * u.deg)
        ).strftime("%m/%d %H:%M")
        sun_next_rising_civil_short = self._observer.astropy_time_to_datetime(
            self._observer.sun_rise_time(time, which="next", horizon=-6 * u.deg)
        ).strftime("%m/%d %H:%M")

        # with warnings.catch_warnings(record=True) as w:
        #     sun_next_setting_civil = self._observer.sun_set_time(time, which="next", horizon=-6 * u.deg)

        #     if len(w):
        #         if issubclass(w[-1].category, TargetAlwaysUpWarning):
        #             _LOGGER.warning("Sun is not setting civically")
        #             sun_next_rising_civil = time + 1 * u.day
        #             sun_next_setting_civil = time
        #             sun_next_rising_civil_short = self._observer.astropy_time_to_datetime(sun_next_rising_civil).strftime("%m/%d %H:%M")
        #             sun_next_setting_civil_short = self._observer.astropy_time_to_datetime(sun_next_setting_civil).strftime("%m/%d %H:%M")
        #     else:
        #         sun_next_setting_civil, sun_next_rising_civil = self._observer.tonight(time=time, horizon=-6 * u.deg)
        #         sun_next_setting_civil_short = self._observer.astropy_time_to_datetime(
        #             self._observer.sun_set_time(time, which="next", horizon=-6 * u.deg)
        #         ).strftime("%m/%d %H:%M")
        #         sun_next_rising_civil_short = self._observer.astropy_time_to_datetime(
        #             self._observer.sun_rise_time(time, which="next", horizon=-6 * u.deg)
        #         ).strftime("%m/%d %H:%M")

        self._darkness = darkness
        self._sun_next_setting = sun_next_setting
        self._sun_next_rising = sun_next_rising
        self._sun_next_setting_civil = sun_next_setting_civil
        self._sun_next_setting_civil_short = sun_next_setting_civil_short
        self._sun_next_rising_civil = sun_next_rising_civil
        self._sun_next_rising_civil_short = sun_next_rising_civil_short

        return None

    def _moon(self, time, sun_next_setting):
        """Calculate the Moon rise, set, and illumination.

        Args:
            time (Time): Calculation time
            sun_next_setting (Time): Next sun set
        """

        moon_next_setting_short = None
        moon_next_rising_short = None

        calctime = time
        with warnings.catch_warnings(record=True) as w:
            for i in range(0, 2):
                moon_set_time = self._observer.moon_set_time(calctime, which="next", horizon=0 * u.deg)
                if len(w):
                    if issubclass(w[-1].category, TargetNeverUpWarning):
                        _LOGGER.warning("Moon does not cross horizon=0.0 deg within 24 hours")
                        calctime = calctime + 1 * u.day
                    w.clear()
                else:
                    moon_next_setting_short = self._observer.astropy_time_to_datetime(moon_set_time).strftime(
                        "%m/%d %H:%M"
                    )
                    break

        calctime = time
        with warnings.catch_warnings(record=True) as w:
            for i in range(0, 2):
                moon_rise_time = self._observer.moon_rise_time(calctime, which="next", horizon=0 * u.deg)
                if len(w):
                    if issubclass(w[-1].category, TargetAlwaysUpWarning):
                        _LOGGER.warning("Moon does not cross horizon=0.0 deg within 24 hours")
                        calctime = calctime + 1 * u.day
                    w.clear()
                else:
                    moon_next_rising_short = self._observer.astropy_time_to_datetime(moon_rise_time).strftime(
                        "%m/%d %H:%M"
                    )
                    break

        # # Define location on Earth (longitude, latitude, and height)
        # location = EarthLocation(lat=37.7749*u.deg, lon=-122.4194*u.deg, height=10*u.m)  # Example: San Francisco

        # # Define time (UTC)
        # time = Time.now()  # Use current time

        # # Get the Moon's position from the given location and time
        # moon = get_moon(time, location)

        # # Calculate the Moon's distance from Earth (in kilometers)
        # moon_distance = moon.distance.to(u.km)

        # # The average distance of the Moon from Earth (in kilometers)
        # average_moon_distance = 384400 * u.km

        # # Calculate the relative size of the Moon compared to its average size
        # relative_size = average_moon_distance / moon_distance

        # # Output results
        # print(f"Moon's current distance: {moon_distance:.2f}")
        # print(f"Relative size of the Moon compared to average: {relative_size:.2f}")

        moon_illumination = self._observer.moon_illumination(sun_next_setting) * 100

        self._moon_illumination = moon_illumination
        self._moon_next_setting_short = moon_next_setting_short
        self._moon_next_rising_short = moon_next_rising_short

        return None
