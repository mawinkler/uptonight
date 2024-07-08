"""Uptonight - calculate the best objects for tonight"""

import logging
from datetime import datetime

import matplotlib.pyplot as plt
import pytz
from astroplan import (
    AirmassConstraint,
    AltitudeConstraint,
    FixedTarget,
    MoonSeparationConstraint,
    Observer,
    download_IERS_A,
    is_observable,
    observability_table,
    time_grid_from_range,
)
from astroplan.plots import plot_sky
from astropy import units as u
from astropy.coordinates import AltAz, EarthLocation, SkyCoord, get_body
from astropy.time import Time
from matplotlib import cm
from pytz import timezone

from uptonight.const import (
    BODIES,
    CUSTOM_TARGETS,
)
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
        Both generated files are identical.
    """

    def __init__(
        self,
        location,
        environment={},
        constraints={},
        target_list=None,
        bucket_list=[],
        done_list=[],
        observation_date=None,
        type_filter="",
        output_dir=".",
        live=False,
    ):
        """Init function for UpTonight

        Args:
            location (_type_): _description_
            environment (dict, optional): _description_. Defaults to {}.
            constraints (dict, optional): _description_. Defaults to {}.
            target_list (_type_, optional): _description_. Defaults to None.
            bucket_list (list, optional): _description_. Defaults to [].
            done_list (list, optional): _description_. Defaults to [].
            observation_date (_type_, optional): _description_. Defaults to None.
            type_filter (str, optional): _description_. Defaults to "".
            output_dir (str, optional): _description_. Defaults to ".".
            live (bool, optional): _description_. Defaults to False.

        Returns:
            None: None
        """
        self._location = location
        self._environment = environment
        self._constraints = constraints
        self._target_list = target_list
        self._bucket_list = bucket_list
        self._done_list = done_list
        self._observation_date = observation_date
        self._type_filter = type_filter
        self._output_dir = output_dir
        self._live = live

        self._observer = self._get_observer()
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

        # Create the targets table and targets list containing the targets of the csv file plus user defined
        # custom targets. We will iterate over the targets list and use the input_targets table for lookup
        # values while calculating the results
        _LOGGER.info("Building targets lists")
        self._targets = Targets(target_list=target_list)
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

        return None

    def _get_observer(self) -> Observer:
        """Create an observer on the planet with given environmental conditions

        Returns:
            astroplan.Observer: A container class for information about an observer’s location and environment.
        """

        observer_location = EarthLocation.from_geodetic(
            self._location["longitude"],
            self._location["latitude"],
            self._location["elevation"] * u.m,
        )

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

        _LOGGER.debug(f"Sun and Moon helper created")

        return sun_moon

    def _get_observation_timeframe(self) -> dict:
        """Define oberserving time range.

        Returns:
            dict: { "observing_start_time": observing_start_time,
                    "observing_end_time": observing_end_time,
                    "time_range": Time()
                    "current_day": current_day, }
        """
        # 

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
        else:
            observing_start_time = self._sun_moon.sun_next_setting()
            observing_end_time = self._sun_moon.sun_next_rising()

        _LOGGER.debug("Observing start time: {0}".format(observing_start_time.strftime("%m/%d/%Y %H:%M:%S")))

        current_day = self._observer.astropy_time_to_datetime(observing_start_time).strftime("%Y%m%d")

        observation_timeframe = {
            "observing_start_time": observing_start_time,
            "observing_end_time": observing_end_time,
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
    ):
        """Do the math.

        Args:
            bucket_list (list, optional): _description_. Defaults to [].
            done_list (list, optional): _description_. Defaults to [].
            type_filter (str, optional): _description_. Defaults to "".
        """

        # This will be our result table
        uptonight_targets = self._targets.targets_table()

        # Count targets within constraints
        within_threshold = 0
        for index, target in enumerate(self._input_targets):
            fraction_of_time_observable = self._input_targets[index]["fraction of time observable"]
            size = self._input_targets[index]["size"]
            if (
                fraction_of_time_observable >= self._constraints["fraction_of_time_observable_threshold"]
                and size >= self._constraints["size_constraint_min"]
                and size <= self._constraints["size_constraint_max"]
            ):
                within_threshold = within_threshold + 1

        _LOGGER.info(f"Number of targets within constraints: {within_threshold}")
        if within_threshold > self._constraints["max_number_within_threshold"]:
            within_threshold = self._constraints["max_number_within_threshold"]

        # Create grid of times from start_time to end_time
        # with resolution time_resolution
        time_resolution = 15 * u.minute
        time_grid = time_grid_from_range(
            [
                self._observation_timeframe["observing_start_time"],
                self._observation_timeframe["observing_end_time"],
            ],
            time_resolution=time_resolution,
        )

        # Configure the plot
        # Color maps: https://matplotlib.org/stable/tutorials/colors/colormaps.html
        plot = Plot(
            self._output_dir,
            self._observation_timeframe["current_day"],
            self._filter_ext,
            self._live,
        )
        cmap = cm.hsv

        # Creating plot and table of targets
        _LOGGER.info("Creating plot and table of targets")
        target_no = 0
        ax = None
        for index, target_row in enumerate(self._input_targets):
            fraction_of_time_observable = target_row["fraction of time observable"]

            # Filter #1:
            #   - Max number of targets and fraction of time observability threshold
            #   - Object on bucket list
            if (
                fraction_of_time_observable >= self._constraints["fraction_of_time_observable_threshold"]
                and target_no < self._constraints["max_number_within_threshold"]
                or target_row["name"] in bucket_list
            ):
                # Filter #2:
                #   - Object type (if set)
                if type_filter != "" and type_filter.lower() not in self._input_targets[index]["type"].lower():
                    continue

                # Filter #3:
                #   - Object size
                #   - Object on bucket list
                #   - Object not on done list
                size = self._input_targets[index]["size"]
                if (
                    size >= self._constraints["size_constraint_min"]
                    and size <= self._constraints["size_constraint_max"]
                    and target_row["name"] not in done_list
                    or target_row["name"] in bucket_list
                ):
                    if str(target_row["description"]) == "--":
                        target_row["description"] = target_row["name"]
                        target_row["name"] = "--"

                    target = FixedTarget(
                        coord=SkyCoord(
                            f"{target_row['ra']} {target_row['dec']}",
                            unit=(u.hourangle, u.deg),
                        ),
                        name=str(target_row["description"])
                        + str(f" ({target_row['name']}, {target_row['size']}', {target_row['mag']})"),
                    )

                    # Object start azimuth and altitude
                    azimuth = self._observer.altaz(self._observation_timeframe["observing_start_time"], target).az
                    altitude = self._observer.altaz(self._observation_timeframe["observing_start_time"], target).alt

                    # Choose marker
                    # Default: Square
                    marker = "s"
                    if "galaxy" in self._input_targets[index]["type"].lower():
                        # Galaxy: Circle
                        marker = "o"
                    if "nebula" in self._input_targets[index]["type"].lower():
                        # Nebula: Diamond
                        marker = "D"

                    # Calculate meridian transit and antitransit
                    meridian_transit_time = self._observer.target_meridian_transit_time(
                        self._observation_timeframe["observing_start_time"],
                        target,
                        which="next",
                    )
                    if meridian_transit_time < self._observation_timeframe["observing_end_time"]:
                        meridian_transit = str(
                            self._observer.astropy_time_to_datetime(meridian_transit_time).strftime("%m/%d/%Y %H:%M:%S")
                        )
                    else:
                        meridian_transit = ""

                    meridian_antitransit_time = self._observer.target_meridian_antitransit_time(
                        self._observation_timeframe["observing_start_time"],
                        target,
                        which="next",
                    )
                    if meridian_antitransit_time < self._observation_timeframe["observing_end_time"]:
                        meridian_antitransit = str(
                            self._observer.astropy_time_to_datetime(meridian_antitransit_time).strftime(
                                "%m/%d/%Y %H:%M:%S"
                            )
                        )
                    else:
                        meridian_antitransit = ""

                    # Add target to results table
                    uptonight_targets.add_row(
                        (
                            target.name,
                            target.coord.to_string("hmsdms"),
                            target.ra,
                            target.dec,
                            altitude,
                            azimuth,
                            meridian_transit,
                            meridian_antitransit,
                            self._input_targets[index]["type"],
                            self._input_targets[index]["constellation"],
                            self._input_targets[index]["size"],
                            self._input_targets[index]["mag"],
                            fraction_of_time_observable,
                        )
                    )

                    # Plot target
                    ax = plot_sky(
                        target,
                        self._observer,
                        time_grid,
                        style_kwargs=dict(
                            color=cmap(target_no / within_threshold * 0.75),
                            label="_Hidden",
                            marker=marker,
                            s=3,
                        ),
                        north_to_east_ccw=self._constraints["north_to_east_ccw"],
                    )
                    ax = plot_sky(
                        target,
                        self._observer,
                        self._observation_timeframe["observing_start_time"],
                        style_kwargs=dict(
                            color=cmap(target_no / within_threshold * 0.75),
                            label=target.name,
                            marker=marker,
                            s=30,
                        ),
                        north_to_east_ccw=self._constraints["north_to_east_ccw"],
                    )
                    target_no = target_no + 1

            # Always add Polaris
            if target_row["name"] == "Polaris" or target_row["name"] in CUSTOM_TARGETS:
                target = FixedTarget(
                    coord=SkyCoord(
                        f"{target_row['ra']} {target_row['dec']}",
                        unit=(u.hourangle, u.deg),
                    ),
                    name=target_row["description"]
                    + f" ({target_row['name']}, {target_row['size']}', {target_row['mag']})",
                )
                ax = plot_sky(
                    target,
                    self._observer,
                    time_grid,
                    style_kwargs=dict(color="w", label=target.name, marker="*"),
                    north_to_east_ccw=self._constraints["north_to_east_ccw"],
                )

        # Bodies
        object_frame = AltAz(obstime=time_grid, location=self._observer.location)

        for name, planet_label, color, size in BODIES:
            if planet_label != "sun":
                if planet_label != "moon":
                    # No altitude constraints for the planets
                    observability_constraints = [
                        AltitudeConstraint(0 * u.deg, 90 * u.deg),
                        MoonSeparationConstraint(min=self._moon_separation * u.deg),
                    ]
                else:
                    # No constraints for the moon
                    observability_constraints = [
                        AltitudeConstraint(0 * u.deg, 90 * u.deg),
                    ]
                observable = is_observable(
                    observability_constraints,
                    self._observer,
                    get_body(planet_label, self._observation_timeframe["time_range"]),
                    time_range=self._observation_timeframe["time_range"],
                )
                if True in observable:
                    _LOGGER.info(f"%s is observable", planet_label.capitalize())
                    object_body = get_body(planet_label, time_grid)
                    object_altaz = object_body.transform_to(object_frame)
                    ax = plot_sky(
                        object_altaz,
                        self._observer,
                        time_grid,
                        style_kwargs=dict(color=color, label=name, linewidth=3, alpha=0.5, s=size),
                        north_to_east_ccw=self._constraints["north_to_east_ccw"],
                    )

        # Sun
        if self._live and self._sun_moon.sun_altitude() > 0:
            name, planet_label, color, size = BODIES[0]
            object_body = get_body(planet_label, time_grid)
            object_altaz = object_body.transform_to(object_frame)
            ax = plot_sky(
                object_altaz,
                self._observer,
                time_grid,
                style_kwargs=dict(color=color, label=name, linewidth=3, alpha=0.5, s=size),
                north_to_east_ccw=self._constraints["north_to_east_ccw"],
            )

        # Title, legend, and config
        astronight_from = self._observer.astropy_time_to_datetime(
            self._observation_timeframe["observing_start_time"]
        ).strftime("%m/%d %H:%M")
        astronight_to = self._observer.astropy_time_to_datetime(
            self._observation_timeframe["observing_end_time"]
        ).strftime("%m/%d %H:%M")
        duration = str(
            self._observer.astropy_time_to_datetime(self._observation_timeframe["observing_end_time"])
            - self._observer.astropy_time_to_datetime(self._observation_timeframe["observing_start_time"])
        ).split(":")
        if ax is not None:
            ax.legend(loc="upper right", bbox_to_anchor=(1.4, 1))
            if not self._live:
                ax.set_title(
                    f"{self._sun_moon.darkness().capitalize()} night: {astronight_from} to {astronight_to} (duration {duration[0]}:{duration[1]}hs)"
                )
            else:
                ax.set_title(f"{astronight_from}")
            plt.figtext(
                0.02,
                0.915,
                "Sunset/rise: {} / {}".format(
                    self._sun_moon.sun_next_setting_civil(),
                    self._sun_moon.sun_next_rising_civil(),
                ),
                size=12,
            )
            plt.figtext(
                0.02,
                0.895,
                "Moonrise/set: {} / {}".format(
                    self._sun_moon.moon_next_rising(),
                    self._sun_moon.moon_next_setting(),
                ),
                size=12,
            )
            plt.figtext(
                0.02,
                0.875,
                "Moon illumination: {:.0f}%".format(self._sun_moon.moon_illumination()),
                size=12,
            )
            plt.figtext(
                0.02,
                0.855,
                "Alt constraint min/max: {}° / {}°".format(
                    self._constraints["altitude_constraint_min"],
                    self._constraints["altitude_constraint_max"],
                ),
                size=12,
            )
            plt.figtext(
                0.02,
                0.835,
                "Airmass constraint: {}".format(self._constraints["airmass_constraint"]),
                size=12,
            )
            plt.figtext(
                0.02,
                0.815,
                "Size constraint min/max: {}' / {}'".format(
                    self._constraints["size_constraint_min"],
                    self._constraints["size_constraint_max"],
                ),
                size=12,
            )
            plt.figtext(
                0.02,
                0.795,
                "Fraction of time: {:.0f}%".format(self._constraints["fraction_of_time_observable_threshold"] * 100),
                size=12,
            )
            plt.figtext(
                0.02,
                0.775,
                "Moon separation: {:.0f}°".format(self._moon_separation),
                size=12,
            )

            plt.figtext(0.02, 0.750, "Solar System: Big circle", size=8)
            plt.figtext(0.02, 0.735, "Nebula: Diamond", size=8)
            plt.figtext(0.02, 0.720, "Galaxy: Circle", size=8)
            plt.figtext(0.02, 0.705, "Rest: Square", size=8)

            plt.tight_layout()

        # Save plot
        _LOGGER.debug("Saving plot")
        plot.save_png(plt)

        # Clear plot
        plt.clf()

        if not self._live:
            # Save reports
            _LOGGER.debug("Saving reports")
            report = Report(
                self._observer,
                uptonight_targets,
                astronight_from,
                astronight_to,
                self._sun_moon,
                self._output_dir,
                self._observation_timeframe["current_day"],
                self._filter_ext,
                self._constraints,
            )
            report.save_txt()
            report.save_json()

        print(uptonight_targets)
