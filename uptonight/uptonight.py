"""Uptonight - calculate the best objects for tonight"""

import logging
from datetime import datetime

import matplotlib.pyplot as plt
import pytz
from astroplan import (
    AirmassConstraint,
    AltitudeConstraint,
    MoonSeparationConstraint,
    Observer,
    download_IERS_A,
)
from astropy import units as u
from astropy.coordinates import EarthLocation
from astropy.time import Time
from pytz import timezone

from uptonight.bodies import UpTonightBodies
from uptonight.comets import UpTonightComets
from uptonight.horizon import UpTonightHorizon
from uptonight.objects import UpTonightObjects
from uptonight.plot import Plot
from uptonight.report import Report
from uptonight.sunmoon import SunMoon
from uptonight.targets import Targets

download_IERS_A()

# CDS Name Resolver:
# https://cds.unistra.fr/cgi-bin/Sesame


_LOGGER = logging.getLogger(__name__)
logging.getLogger("matplotlib").setLevel(logging.INFO)


class UpTonight:
    """
    Calculates the deep sky objects for tonights sky and a given earth location.

    Observing constraints are defined in const.py.
    Default values are:
        DEFAULT_ALTITUDE_CONSTRAINT_MIN = 30  # in deg above horizon
        DEFAULT_ALTITUDE_CONSTRAINT_MAX = 80  # in deg above horizon
        DEFAULT_AIRMASS_CONSTRAINT = 2  # 30° to 90°
        DEFAULT_SIZE_CONSTRAINT_MIN = 10  # in arc minutes
        DEFAULT_SIZE_CONSTRAINT_MAX = 300  # in arc minutes
        DEFAULT_MOON_SEPARATION_MIN = 45  # in degrees

        # Object needs to be within the constraints for at least 50% of darkness
        DEFAULT_FRACTION_OF_TIME_OBSERVABLE_THRESHOLD = 0.5

        # Maximum number of targets to calculate
        DEFAULT_MAX_NUMBER_WITHIN_THRESHOLD = 60

        # True : meaning that azimuth is shown increasing counter-clockwise (CCW), or with North
        #        at top, East at left, etc.
        # False: Show azimuth increasing clockwise (CW).
        DEFAULT_NORTH_TO_EAST_CCW = False

    Parameters
    ----------
    contraints:
        longitude        : str
            Longitude of the location in dms
        latitude         : str
            Latitude of the location in dms
        elevation        : int
            Elevation of the location as int in meter
        timezone         : str
            Timezone in tz format (e.g. Europe/Berlin)
    environment:
        pressure         : float (optional)
            This is necessary for performing refraction corrections.
            Setting this to 0 (the default) will disable refraction calculations.
        relative_humidity: float (optional)
            This is necessary for performing refraction corrections.
            Setting this to 0 (the default) will disable refraction calculations.
        temperature      : float (optional)
            This is necessary for performing refraction corrections.
            Setting this to 0 (the default) will disable refraction calculations.
    contraints:
        altitude_constraint_min               : int
            In deg above horizon
        altitude_constraint_max               : int
            In deg above horizon
        airmass_constraint                    : float
            Airmass maximum
        size_constraint_min                   : int
            In arc minutes
        size_constraint_max                   : int
            In arc minutes
        moon_separation_min                   : int
            In degrees
        fraction_of_time_observable_threshold : float
            Minimum timespan of astronomical night within constraints
        max_number_within_threshold           : int
            Maximum number of calculated objects (up to 60)
        north_to_east_ccw                     : bool
            Orientation of the plot
    observation_date : string (optional)
        Perform calculations for the day specified in the format %m/%d/%y.
        If the value is omitted, the current date is used.
    target_list      : string (optional)
        The target list to use. Defaults to GaryImm
    type_filter      : string (optional)
        Filter on an object type. Examples: Nebula, Galaxy, Nova, ...
    output_dir       : string (optional)
        Output directory. Default current directory
    live             : bool (optional)
        When true function is called interval based to create a live view of the sky.
        Text report is not created.

    Returns
    -------
    None

    Creates
    -------
    uptonight-plot.png, uptonight-plot-YYYYMMDD.png:
        Plot of tonights sky. Both generated files are identical.
    uptonight-liveplot.png:
        Realtime plot in live mode.
    uptonight-report.txt, uptonight-report-YYYYMMDD.txt, uptonight-report.json:
        Report of todays objects for obeservation from your location within the defined constraints.
    uptonight-bodies-report.txt, uptonight-bodies-report-YYYYMMDD.txt, uptonight-bodies-report.json:
        Report of todays solar system bodies for obeservation from your location within
        the defined constraints.
    uptonight-comets-report.txt, uptonight-comets-report-YYYYMMDD.txt, uptonight-comets-report.json:
        Report of todays comets for obeservation from your location within the defined constraints.
    """

    def __init__(
        self,
        location,
        features,
        output_datestamp=False,
        environment={},
        constraints={},
        target_list=None,
        bucket_list=[],
        done_list=[],
        custom_targets=[],
        observation_date=None,
        type_filter="",
        output_dir=".",
        live=False,
    ):
        """Init function for UpTonight

        Args:
            location (dict): Location of the observer
            features (dict): Features enabled
            output_datestamp (bool): Add datestamp to plot and reports
            environment (dict, optional): Environmental conditions
            constraints (dict, optional): Constraints for targets
            target_list (str, optional): Name of the target list for deep sky objects
            bucket_list (list, optional): Bocket list
            done_list (list, optional): Done (exclude) list
            observation_date (str, optional): Day for calculation
            type_filter (str, optional): Filter on object types
            output_dir (str, optional): Output directory
            live (bool, optional): Live mode

        Returns:
            None
        """
        self._location = location
        self._features = features
        self._output_datestamp = output_datestamp
        self._environment = environment
        self._constraints = constraints
        self._target_list = target_list
        self._bucket_list = bucket_list
        self._done_list = done_list
        self._custom_targets = custom_targets
        self._observation_date = observation_date
        self._type_filter = type_filter
        self._output_dir = output_dir
        self._live = live

        self._observer_location = self._get_observer_location()
        self._observer = self._get_observer(self._observer_location)
        self._sun_moon = self._get_sun_moon()
        self._observation_timeframe = self._get_observation_timeframe()
        self._moon_separation = 0
        if not self._live:
            if self._constraints["moon_separation_use_illumination"]:
                self._moon_separation = self._sun_moon.moon_illumination()
            else:
                self._moon_separation = self._constraints["moon_separation_min"]

        self._observability_constraints = self._get_constraints()

        self._filter_ext = ""
        if self._type_filter != "":
            self._filter_ext = f"-{self._type_filter}"

        self._targets = Targets(target_list=target_list, custom_targets=custom_targets)
        # Table with targets to calculate
        self._input_targets = self._targets.input_targets()
        # List of fixed targets to calculate the fraction of time observable with
        self._fixed_targets = self._targets.fixed_targets()
        # Add fraction of time observable to input targets
        self._input_targets = self._targets.input_targets_add_foto(
            self._constraints,
            self._observability_constraints,
            self._observation_timeframe,
            self._observer,
            self._fixed_targets,
        )

        if self._features.get("horizon"):
            self._horizon = UpTonightHorizon(self._observer, self._observation_timeframe, self._constraints)

        if self._features.get("objects"):
            self._objects = UpTonightObjects(
                self._observer,
                self._observation_timeframe,
                self._constraints,
                self._input_targets,
                self._custom_targets,
            )

        if self._features.get("bodies"):
            self._bodies = UpTonightBodies(self._observer, self._observation_timeframe, self._constraints)

        if self._features.get("comets"):
            self._comets = UpTonightComets(self._observer, self._observation_timeframe, self._constraints)

        return None

    def _get_observer_location(self) -> EarthLocation:
        """Create an earth locaton with given longitude, latitude, and elevation

        Returns:
            astroplan.EarthLocation: A container class for information about an observer’s location.
        """

        observer_location = EarthLocation.from_geodetic(
            self._location["longitude"],
            self._location["latitude"],
            self._location["elevation"] * u.m,
        )

        return observer_location

    def _get_observer(self, observer_location) -> Observer:
        """Create an observer on the planet with given environmental conditions.

        Args:
            observer_location (EarthLocation): Location on earth.

        Returns:
            astroplan.Observer: A container class for information about an observer’s location and environment.
        """

        observer = Observer(
            name="Backyard",
            location=observer_location,
            pressure=self._environment["pressure"] * u.bar,
            relative_humidity=self._environment["relative_humidity"],
            temperature=self._environment["temperature"] * u.deg_C,
            timezone=timezone(self._location["timezone"]),
            description="My beloved Backyard Telescope",
        )

        _LOGGER.debug(f"Observer created")

        return observer

    def _get_sun_moon(self) -> SunMoon:
        """Create a helper instance for the Sun and the Moon.

        Returns:
            SunMoon: Helper instance
        """

        utcoffset = datetime.now(pytz.timezone(self._location["timezone"])).utcoffset().total_seconds() / 3600
        sun_moon = SunMoon(self._observer, self._observation_date, utcoffset)

        _LOGGER.debug("Sun and Moon helper created")

        return sun_moon

    def _get_observation_timeframe(self) -> dict:
        """Define oberserving time range.

        Returns:
            dict: { "observing_start_time": observing_start_time,
                    "observing_end_time": observing_end_time,
                    "observing_start_time_civil": observing_start_time_civil,
                    "observing_end_time_civil": observing_end_time_civil,
                    "time_range": Time()
                    "current_day": current_day, }
        """

        observing_start_time = None
        observing_end_time = None
        if self._live:
            observing_start_time = Time(
                datetime.utcnow(),
                scale="utc",
                location=self._observer.location,
            )
            observing_end_time = (
                Time(
                    datetime.utcnow(),
                    scale="utc",
                    location=self._observer.location,
                )
                + 1 * u.minute
            )
            observing_start_time_civil = observing_start_time
            observing_end_time_civil = observing_end_time
        else:
            observing_start_time = self._sun_moon.sun_next_setting()
            observing_end_time = self._sun_moon.sun_next_rising()
            observing_start_time_civil = self._sun_moon.sun_next_setting_civil()
            observing_end_time_civil = self._sun_moon.sun_next_rising_civil()

        _LOGGER.debug("Observing start time: {0}".format(observing_start_time.strftime("%m/%d/%Y %H:%M:%S")))

        current_day = self._observer.astropy_time_to_datetime(observing_start_time).strftime("%Y%m%d")

        observation_timeframe = {
            "observing_start_time": observing_start_time,
            "observing_end_time": observing_end_time,
            "observing_start_time_civil": observing_start_time_civil,
            "observing_end_time_civil": observing_end_time_civil,
            "time_range": Time(
                [
                    observing_start_time,
                    observing_end_time,
                ],
                scale="utc",
            ),
            "current_day": current_day,
        }

        return observation_timeframe

    def _get_constraints(self) -> list:
        """Create a constraints object as a filter for the astronomical objects.

        Returns:
            list: [ AltitudeConstraint,
                    AirmassConstraint,
                    MoonSeparationConstraint ]
        """

        observability_constraints = [
            AltitudeConstraint(
                self._constraints["altitude_constraint_min"] * u.deg,
                self._constraints["altitude_constraint_max"] * u.deg,
            ),
            AirmassConstraint(self._constraints["airmass_constraint"]),
            MoonSeparationConstraint(min=self._moon_separation * u.deg),
        ]

        _LOGGER.debug("Constraints applied")

        return observability_constraints

    def calc(
        self,
        bucket_list=[],
        done_list=[],
        type_filter="",
        horizon=None,
    ):
        """Do the math.

        Args:
            bucket_list (list, optional): _description_. Defaults to [].
            done_list (list, optional): _description_. Defaults to [].
            type_filter (str, optional): _description_. Defaults to "".
            horizon (list): List of alt/az pairs defining the horizon.
        """

        # This will be our result table(s)
        uptonight_targets = self._targets.targets_table()
        uptonight_bodies = self._targets.bodies_table()
        uptonight_comets = self._targets.comets_table()

        # Configure the plot
        # Color maps: https://matplotlib.org/stable/tutorials/colors/colormaps.html
        plot = Plot(
            self._observer,
            self._observation_timeframe,
            self._constraints,
            self._moon_separation,
            self._sun_moon,
            self._output_dir,
            self._observation_timeframe["current_day"],
            self._filter_ext,
            self._live,
        )
        ax = None

        # Creating plot of the horizon
        if self._features.get("horizon"):
            if horizon is not None:
                ax = self._horizon.horizon(horizon)

        # Purge old altitude time plots
        if not self._live and self._features.get("alttime"):
            plot.altitude_time_purge()

        # Creating plot and table of targets
        if self._features.get("objects"):
            uptonight_targets, ax = self._objects.objects(uptonight_targets, bucket_list, done_list, type_filter)
            if not self._live and self._features.get("alttime"):
                for target_row in uptonight_targets:
                    plot.altitude_time(
                        target_row,
                    )

        # Creating plot and table of bodies
        if self._features.get("bodies"):
            uptonight_bodies, ax = self._bodies.bodies(uptonight_bodies)
            if not self._live and self._features.get("alttime"):
                for target_row in uptonight_bodies:
                    plot.altitude_time(
                        target_row,
                    )

        if self._features.get("comets"):
            uptonight_comets, ax = self._comets.comets(uptonight_comets)
            if not self._live and self._features.get("alttime"):
                for target_row in uptonight_comets:
                    plot.altitude_time(
                        target_row,
                    )

        # Title, legend, and config
        astronight_from = self._observer.astropy_time_to_datetime(
            self._observation_timeframe["observing_start_time"]
        ).strftime("%m/%d %H:%M")
        astronight_to = self._observer.astropy_time_to_datetime(
            self._observation_timeframe["observing_end_time"]
        ).strftime("%m/%d %H:%M")

        plot.legend(ax, astronight_from, astronight_to)

        # Save plot
        _LOGGER.debug("Saving plot")
        plot.save_png(plt, self._output_datestamp)

        # Clear plot
        plt.clf()

        if not self._live:
            # Save reports
            _LOGGER.debug("Saving reports")
            report = Report(
                self._observer,
                astronight_from,
                astronight_to,
                self._sun_moon,
                self._output_dir,
                self._observation_timeframe["current_day"],
                self._filter_ext,
                self._constraints,
            )
            if self._features.get("objects"):
                report.save_txt(uptonight_targets, "", self._output_datestamp)
                report.save_json(uptonight_targets, "", self._output_datestamp)
            if self._features.get("bodies"):
                report.save_txt(uptonight_bodies, "-bodies", self._output_datestamp)
                report.save_json(uptonight_bodies, "-bodies", self._output_datestamp)
            if self._features.get("comets"):
                report.save_txt(uptonight_comets, "-comets", self._output_datestamp)
                report.save_json(uptonight_comets, "-comets", self._output_datestamp)

        if self._features.get("objects"):
            print(uptonight_targets)

        if self._features.get("bodies"):
            print(uptonight_bodies)

        if self._features.get("comets"):
            print(uptonight_comets)
