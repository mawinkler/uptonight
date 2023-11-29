"""Uptonight - calculate the best objects for tonight"""
import sys
import warnings
import logging

import numpy as np

import matplotlib.pyplot as plt
from matplotlib import cm

from pytz import timezone
from datetime import datetime

from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.coordinates import AltAz
from astropy.coordinates import EarthLocation
from astropy.coordinates import get_body
from astropy.table import Table
from astropy.time import Time

from astroplan import FixedTarget
from astroplan import Observer
from astroplan import download_IERS_A
from astroplan import AltitudeConstraint, AirmassConstraint, MoonSeparationConstraint
from astroplan import observability_table
from astroplan import time_grid_from_range
from astroplan.exceptions import TargetAlwaysUpWarning, TargetNeverUpWarning
from astroplan.plots import plot_sky

from .const import (
    ALTITUDE_CONSTRAINT_MIN,
    ALTITUDE_CONSTRAINT_MAX,
    AIRMASS_CONSTRAINT,
    SIZE_CONSTRAINT_MIN,
    SIZE_CONSTRAINT_MAX,
    MOON_SEPARATION_MIN,
    FRACTION_OF_TIME_OBSERVABLE_THRESHOLD,
    NORTH_TO_EAST_CCW,
    DEFAULT_TARGETS,
    CUSTOM_TARGETS,
    BODIES,
)

download_IERS_A()

# CDS Name Resolver:
# https://cds.unistra.fr/cgi-bin/Sesame

# Add date to filenames
OUTPUT_DATESTAMP = True

_LOGGER = logging.getLogger(__name__)
logging.getLogger("matplotlib").setLevel(logging.INFO)


class Targets:
    """UpTonight Target Generation"""

    def __init__(
        self,
        target_list,
    ):
        self._input_targets, self._fixed_targets = self._create_target_list(target_list)
        self._targets_table = self._create_uptonight_targets_table()

        return None

    def input_targets(self):
        if self._input_targets is not None:
            return self._input_targets
        return None

    def fixed_targets(self):
        if self._fixed_targets is not None:
            return self._fixed_targets
        return None

    def targets_table(self):
        if self._targets_table is not None:
            return self._targets_table
        return None

    def _create_target_list(self, target_list):
        """
        Creates a table and list of targets in scope for the calculations.

        The method reads the provided csv file containing the Gary Imm objects and adds custom
        targets defined in the const.py file. The table is used as a lookup table to populate the
        result table. Iteration is done via the FixedTarget list.
        For visibility, Polaris is appended lastly.

        Parameters
        ----------
        target_list

        Returns
        -------
        astropy.Table, [astroplan.FixedTarget]
            Lookup table, list of targets to calculate
        """

        input_targets = Table.read(f"{target_list}.csv", format="ascii.csv")

        # Create astroplan.FixedTarget objects for each one in the table
        fixed_targets = [
            FixedTarget(
                coord=SkyCoord(f"{ra} {dec}", unit=(u.hourangle, u.deg)),
                name=common_name + f" ({name}, {size}')",
            )
            for name, common_name, type, constellation, size, ra, dec in input_targets
        ]

        # Add custom targets
        for custom_target in CUSTOM_TARGETS:
            name = custom_target.get("name")
            desc = custom_target.get("description")
            ra = custom_target.get("ra")
            dec = custom_target.get("dec")
            size = custom_target.get("size")
            input_targets.add_row(
                [
                    name,
                    desc,
                    custom_target.get("type"),
                    custom_target.get("constellation"),
                    size,
                    ra,
                    dec,
                ]
            )
            fixed_targets.append(
                FixedTarget(coord=SkyCoord(f"{ra} {dec}", unit=(u.hourangle, u.deg)), name=desc + f" ({name}, {size}')"),
            )

        # Lastly we add Polaris
        fixed_targets.append(FixedTarget.from_name("Polaris"))

        return input_targets, fixed_targets

    def _create_uptonight_targets_table(self):
        """
        Creates the result table.

        Rows will be added while objects are calculated

        Parameters
        ----------
        none

        Returns
        -------
        astropy.Table
            Result table
        """

        uptonight_targets = Table(
            names=(
                "target name",
                "hmsdms",
                "right ascension",
                "declination",
                "altitude",
                "azimuth",
                "meridian transit",
                "antimeridian transit",
                "type",
                "constellation",
                "size",
                "foto",
            ),
            dtype=(
                str,
                str,
                np.float16,
                np.float16,
                np.float16,
                np.float16,
                str,
                str,
                str,
                str,
                np.float16,
                np.float16,
            ),
        )
        uptonight_targets["right ascension"].info.format = ".1f"
        uptonight_targets["declination"].info.format = ".1f"
        uptonight_targets["altitude"].info.format = ".1f"
        uptonight_targets["azimuth"].info.format = ".1f"
        uptonight_targets["foto"].info.format = ".1f"

        return uptonight_targets


class SunMoon:
    """UpTonight Target Generation"""

    def __init__(
        self,
        observer,
        observation_date=None,
    ):
        self._observer = observer
        self._darkness = None
        self._sun_next_setting = None
        self._sun_next_rising = None
        self._sun_next_setting_civil = None
        self._sun_next_rising_civil = None
        self._moon_illumination = None
        self._moon_next_setting = None
        self._moon_next_rising = None

        # Calculate tonights night unless a date is given
        if observation_date is None:
            time = (
                Time(
                    datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0),
                    scale="utc",
                    location=self._observer.location,
                )
                + 12 * u.hour
            )
        else:
            time = (
                Time(
                    datetime.strptime(observation_date, "%m/%d/%y").replace(hour=0, minute=0, second=0, microsecond=0),
                    scale="utc",
                    location=self._observer.location,
                )
                + 12 * u.hour
            )
        _LOGGER.info("Calculating for: {0}".format(time.strftime("%m/%d/%Y")))

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

    def sun_next_rising_civil(self) -> Time:
        if self._sun_next_rising_civil is not None:
            return self._sun_next_rising_civil
        return None

    def sun_altitude(self) -> float:
        altitude = self._observer.sun_altaz(datetime.utcnow()).alt.degree
        _LOGGER.debug("Sun altitude: {0}".format(altitude))
        return altitude
    
    def moon_illumination(self) -> int:
        if self._moon_illumination is not None:
            return self._moon_illumination
        return None

    def moon_next_setting(self) -> Time:
        if self._moon_next_setting is not None:
            return self._moon_next_setting
        return None

    def moon_next_rising(self) -> Time:
        if self._moon_next_rising is not None:
            return self._moon_next_rising
        return None

    def _sun(self, time):
        """
        Calculate the Sun rise, set, and the type of darkness to expect.

        Parameters
        ----------
        time

        Returns
        -------
        None
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
                                sun_next_setting, sun_next_rising = self._observer.tonight(time=time, horizon=-6 * u.deg)
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

        sun_next_setting_civil = self._observer.astropy_time_to_datetime(self._observer.sun_set_time(time, which="next", horizon=-6 * u.deg)).strftime(
            "%m/%d %H:%M"
        )
        sun_next_rising_civil = self._observer.astropy_time_to_datetime(self._observer.sun_rise_time(time, which="next", horizon=-6 * u.deg)).strftime(
            "%m/%d %H:%M"
        )

        self._darkness = darkness
        self._sun_next_setting = sun_next_setting
        self._sun_next_rising = sun_next_rising
        self._sun_next_setting_civil = sun_next_setting_civil
        self._sun_next_rising_civil = sun_next_rising_civil

        return None

    def _moon(self, time, sun_next_setting):
        """
        Calculate the Moon rise, set, and illumination.

        Parameters
        ----------
        time
        sun_next_setting

        Returns
        -------
        None
        """

        moon_next_setting = self._observer.astropy_time_to_datetime(self._observer.moon_set_time(time, which="next", horizon=0 * u.deg)).strftime("%m/%d %H:%M")
        moon_next_rising = self._observer.astropy_time_to_datetime(self._observer.moon_rise_time(time, which="next", horizon=0 * u.deg)).strftime("%m/%d %H:%M")

        moon_illumination = self._observer.moon_illumination(sun_next_setting) * 100
        # moon_phase = self._observer.moon_phase(sun_next_setting)
        # _LOGGER.info("Moon illumination: {0}, Moon phase: {1}".format(moon_illumination, moon_phase))

        self._moon_illumination = moon_illumination
        self._moon_next_setting = moon_next_setting
        self._moon_next_rising = moon_next_rising

        return None


class Plot:
    """UpTonight Plot"""

    def __init__(
        self,
        output_dir,
        current_day,
        filter_ext,
        live,
    ):
        self._output_dir = output_dir
        self._current_day = current_day
        self._filter_ext = filter_ext
        self._live = live

        self._style_plot()

        return None

    def save_png(self, plt):
        if not self._live:
            if OUTPUT_DATESTAMP:
                plt.savefig(f"{self._output_dir}/uptonight-plot-{self._current_day}{self._filter_ext}.png")
            plt.savefig(f"{self._output_dir}/uptonight-plot{self._filter_ext}.png")
        else:
            plt.savefig(f"{self._output_dir}/uptonight-liveplot{self._filter_ext}.png")

    def _style_plot(self):
        """
        Style modifications for the plot

        Parameters
        ----------
        none

        Returns
        -------
        none
        """

        # Font
        plt.rcParams["font.size"] = 14

        # Lines
        plt.rcParams["lines.linewidth"] = 2
        plt.rcParams["lines.markersize"] = 4

        plt.rcParams["xtick.labelsize"] = 13
        plt.rcParams["ytick.labelsize"] = 13
        plt.rcParams["xtick.color"] = "#F2F2F2"
        plt.rcParams["ytick.color"] = "#F2F2F2"

        # Axes
        plt.rcParams["axes.titlesize"] = 14
        plt.rcParams["axes.labelcolor"] = "w"
        plt.rcParams["axes.facecolor"] = "#262626"
        plt.rcParams["axes.edgecolor"] = "#F2F2F2"

        # Legend
        plt.rcParams["legend.facecolor"] = "#262626"
        plt.rcParams["legend.edgecolor"] = "#262626"
        plt.rcParams["legend.fontsize"] = 7
        # plt.rcParams["legend.framealpha"] = 0.2

        # Figure
        plt.rcParams["figure.facecolor"] = "#1C1C1C"
        plt.rcParams["figure.edgecolor"] = "#1C1C1C"
        plt.rcParams["figure.figsize"] = (15, 10)
        plt.rcParams["figure.dpi"] = 300

        # Other
        plt.rcParams["grid.color"] = "w"
        plt.rcParams["text.color"] = "w"


class Report:
    """UpTonight Reports"""

    def __init__(
        self,
        observer,
        uptonight_targets,
        astronight_from,
        astronight_to,
        sun_moon,
        output_dir,
        current_day,
        filter_ext,
    ):
        self._observer = observer
        self._uptonight_targets = uptonight_targets
        self._astronight_from = astronight_from
        self._astronight_to = astronight_to
        self._sun_moon = sun_moon
        self._output_dir = output_dir
        self._current_day = current_day
        self._filter_ext = filter_ext

        return None

    def save_txt(self):
        """
        Save report as txt

        Parameters
        ----------
        contents

        Returns
        -------
        contents
        """

        _LOGGER.debug("Saving report")

        self._uptonight_targets.write(
            f"{self._output_dir}/uptonight-report{self._filter_ext}.txt",
            overwrite=True,
            format="ascii.fixed_width_two_line",
        )

        with open(f"{self._output_dir}/uptonight-report{self._filter_ext}.txt", "r") as report:
            contents = report.readlines()

        contents = self._report_add_info(contents)

        if OUTPUT_DATESTAMP:
            with open(f"{self._output_dir}/uptonight-report-{self._current_day}{self._filter_ext}.txt", "w") as report:
                report.write(contents)
        with open(f"{self._output_dir}/uptonight-report{self._filter_ext}.txt", "w") as report:
            report.write(contents)

    def save_json(self):
        """
        Write JSON for Home Assistant

        Parameters
        ----------
        contents

        Returns
        -------
        contents
        """

        if OUTPUT_DATESTAMP:
            self._uptonight_targets.write(f"{self._output_dir}/uptonight-report-{self._current_day}.json", overwrite=True, format="pandas.json")
        self._uptonight_targets.write(f"{self._output_dir}/uptonight-report.json", overwrite=True, format="pandas.json")

    def _report_add_info(self, contents):
        """
        Add observatory information to report

        Parameters
        ----------
        contents

        Returns
        -------
        contents
        """

        contents.insert(0, "-" * 163)
        contents.insert(1, "\n")
        contents.insert(2, "UpTonight")
        contents.insert(3, "\n")
        contents.insert(4, "-" * 163)
        contents.insert(5, "\n")
        contents.insert(6, "\n")
        contents.insert(7, f"Observatory: {self._observer.name}\n")
        contents.insert(
            8,
            f" - Location: {self._observer.location.lon:.2f}, {self._observer.location.lat:.2f}, {self._observer.location.height:.2f}\n",
        )
        contents.insert(9, "\n")
        contents.insert(
            10,
            f"Observation timespan: {self._astronight_from} to {self._astronight_to} in {self._sun_moon.darkness()} darkness",
        )
        contents.insert(11, "\n")
        contents.insert(12, "Moon illumination: {:.0f}%".format(self._sun_moon.moon_illumination()))
        contents.insert(13, "\n")
        contents.insert(
            14,
            f"Contraints: Altitude constraint minimum: {ALTITUDE_CONSTRAINT_MIN}°, maximum: {ALTITUDE_CONSTRAINT_MAX}°, "
            + f"Airmass constraint: {AIRMASS_CONSTRAINT}, Moon separation constraint: {MOON_SEPARATION_MIN}°, "
            + f"Size constraint minimum: {SIZE_CONSTRAINT_MIN}', maximum: {SIZE_CONSTRAINT_MAX}'",
        )
        contents.insert(15, "\n")
        contents.insert(16, f"Altitude and Azimuth calculated for {self._astronight_from}")
        contents.insert(17, "\n")
        contents.insert(18, "\n")

        contents = "".join(contents)

        return contents


def calc(
    longitude,
    latitude,
    elevation,
    tz,
    pressure=0,
    relative_humidity=0,
    temperature=0,
    observation_date=None,
    target_list=None,
    type_filter="",
    output_dir=".",
    live=False,
):
    """
    Calculates the deep sky objects for tonights sky and a given earth location.

    Observing constraints are defined in const.py.
    Default values are:
        ALTITUDE_CONSTRAINT_MIN = 20     # in deg above horizon
        ALTITUDE_CONSTRAINT_MAX = 80     # in deg above horizon
        AIRMASS_CONSTRAINT = 2           # 30° to 90°
        SIZE_CONSTRAINT_MIN = 10         # in minutes
        SIZE_CONSTRAINT_MAX = 180        # in minutes
        MOON_SEPARATION_MIN = 90         # in degrees

        # Object needs to be within the constraints for at least 80% of astronomical darkness
        FRACTION_OF_TIME_OBSERVABLE_THRESHOLD = 0.80

        # True : meaning that azimuth is shown increasing counter-clockwise (CCW), or with North
        #        at top, East at left, etc.
        # False: Show azimuth increasing clockwise (CW).
        NORTH_TO_EAST_CCW = False

    Parameters
    ----------
    longitude        : str
        Longitude of the location in dms
    latitude         : str
        Latitude of the location in dms
    elevation        : int
        Elevation of the location as int in meter
    timezone         : str
        Timezone in tz format (e.g. Europe/Berlin)
    pressure         : float (optional)
        This is necessary for performing refraction corrections.
        Setting this to 0 (the default) will disable refraction calculations.
    relative_humidity: float (optional)
        This is necessary for performing refraction corrections.
        Setting this to 0 (the default) will disable refraction calculations.
    temperature      : float (optional)
        This is necessary for performing refraction corrections.
        Setting this to 0 (the default) will disable refraction calculations.
    observation_date : string (optional)
        Perform calculations for the day specified in the format %m/%d/%y.
        If the value is omitted, the current date is used.
    target_list      : string (optional)
        The target list to use. Defaults to Gary_Imm_Best_Astrophotography_Objects
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

    # Our observer
    location = EarthLocation.from_geodetic(longitude, latitude, elevation * u.m)

    observer = Observer(
        name="Backyard",
        location=location,
        pressure=pressure * u.bar,
        relative_humidity=relative_humidity,
        temperature=temperature * u.deg_C,
        timezone=timezone(tz),
        description="My beloved Backyard Telescope",
    )

    # Define oberserving time range
    sun_moon = SunMoon(observer, observation_date)
    observing_start_time = None
    observing_end_time = None
    if live:
        observing_start_time = (
            Time(
                datetime.utcnow(),
                scale="utc",
                location=observer.location,
            )
        )
        observing_end_time = (
            Time(
                datetime.utcnow(),
                scale="utc",
                location=observer.location,
            )
            + 1 * u.minute
        )
    else:
        observing_start_time = sun_moon.sun_next_setting()
        observing_end_time = sun_moon.sun_next_rising()

    _LOGGER.info("Observing start time: {0}".format(observing_start_time.strftime("%m/%d/%Y %H:%M:%S")))
    current_day = observer.astropy_time_to_datetime(observing_start_time).strftime("%Y%m%d")

    filter_ext = ""
    if type_filter != "":
        filter_ext = f"-{type_filter}"

    # Create the targets table and targets list containing the targets of the csv file plus user defined
    # custom targets. We will iterate over the targets list and use the input_targets table for lookup
    # values while calculating the results
    _LOGGER.debug("Building targets list")
    if target_list is None:
        target_list = DEFAULT_TARGETS

    targets = Targets(target_list)
    # input_targets, targets = create_target_list(target_list)
    input_targets = targets.input_targets()
    fixed_targets = targets.fixed_targets()

    # Create the observability table which weights the targets based on the given constraints to
    # calculate the fraction of time observable tonight
    _LOGGER.debug("Setting constraints")
    constraints = [
        AltitudeConstraint(ALTITUDE_CONSTRAINT_MIN * u.deg, ALTITUDE_CONSTRAINT_MAX * u.deg),
        AirmassConstraint(AIRMASS_CONSTRAINT),
        MoonSeparationConstraint(min=MOON_SEPARATION_MIN * u.deg),
    ]

    _LOGGER.info("Creating observability table")
    time_range = Time([observing_start_time, observing_end_time], scale="utc")
    observability_targets = observability_table(constraints, observer, fixed_targets, time_range=time_range)
    observability_targets["fraction of time observable"].info.format = ".3f"

    # This will be our result table
    uptonight_targets = targets.targets_table()

    # Count targets within constraints
    within_threshold = 0
    for i, target in enumerate(fixed_targets):
        fraction_of_time_observable = observability_targets[i]["fraction of time observable"]
        if fraction_of_time_observable >= FRACTION_OF_TIME_OBSERVABLE_THRESHOLD:
            within_threshold = within_threshold + 1

    # Configure the plot
    # Color maps: https://matplotlib.org/stable/tutorials/colors/colormaps.html
    plot = Plot(output_dir, current_day, filter_ext, live)
    cmap = cm.hsv

    # Create grid of times from start_time to end_time
    # with resolution time_resolution
    time_resolution = 15 * u.minute
    time_grid = time_grid_from_range([observing_start_time, observing_end_time], time_resolution=time_resolution)

    # Creating plot and table of targets
    _LOGGER.info("Creating plot and table of targets")
    target_no = 0
    ax = None

    for i, target in enumerate(fixed_targets):
        fraction_of_time_observable = observability_targets[i]["fraction of time observable"]
        if fraction_of_time_observable >= FRACTION_OF_TIME_OBSERVABLE_THRESHOLD:
            azimuth = observer.altaz(observing_start_time, target).az
            altitude = observer.altaz(observing_start_time, target).alt

            # Add target to final table, leave out Polaris
            if i < (len(fixed_targets) - 1):
                # If an object type is set we filter out everything else
                if type_filter != "" and type_filter.lower() not in input_targets[i]["type"].lower():
                    continue

                # Choose marker
                marker = "s"
                if "galaxy" in input_targets[i]["type"].lower():
                    marker = "o"
                if "nebula" in input_targets[i]["type"].lower():
                    marker = "D"

                size = input_targets[i]["size"]
                if size >= SIZE_CONSTRAINT_MIN and size <= SIZE_CONSTRAINT_MAX:
                    meridian_transit_time = observer.target_meridian_transit_time(observing_start_time, target, which="next")
                    if meridian_transit_time < observing_end_time:
                        meridian_transit = str(observer.astropy_time_to_datetime(meridian_transit_time).strftime("%m/%d/%Y %H:%M:%S"))
                    else:
                        meridian_transit = ""

                    meridian_antitransit_time = observer.target_meridian_antitransit_time(observing_start_time, target, which="next")
                    if meridian_antitransit_time < observing_end_time:
                        meridian_antitransit = str(observer.astropy_time_to_datetime(meridian_antitransit_time).strftime("%m/%d/%Y %H:%M:%S"))
                    else:
                        meridian_antitransit = ""

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
                            input_targets[i]["type"],
                            input_targets[i]["constellation"],
                            input_targets[i]["size"],
                            fraction_of_time_observable,
                        )
                    )

                    ax = plot_sky(
                        target,
                        observer,
                        time_grid,
                        style_kwargs=dict(color=cmap(target_no / within_threshold), label=target.name, marker=marker, s=5),
                        north_to_east_ccw=NORTH_TO_EAST_CCW,
                    )

            if target.name == "Polaris" or target.name in CUSTOM_TARGETS:
                ax = plot_sky(
                    target,
                    observer,
                    time_grid,
                    style_kwargs=dict(color="w", label=target.name, marker="*"),
                    north_to_east_ccw=NORTH_TO_EAST_CCW,
                )
            target_no = target_no + 1

    # Bodies
    object_frame = AltAz(obstime=time_grid, location=observer.location)
    if live:
        for name, planet_label, color, size in BODIES:
            if planet_label != 'sun':
                fixed_target = FixedTarget.from_name(planet_label)
                if observer.target_is_up(observing_start_time, fixed_target):
                    object_body = get_body(planet_label, time_grid)
                    object_altaz = object_body.transform_to(object_frame)
                    ax = plot_sky(
                        object_altaz,
                        observer,
                        time_grid,
                        style_kwargs=dict(color=color, label=name, linewidth=3, alpha=0.5, s=size),
                        north_to_east_ccw=NORTH_TO_EAST_CCW,
                    )
    else:
        # TODO: exclude bodies which are not up during the night
        for name, planet_label, color, size in BODIES:
            if planet_label != 'sun':
                object_body = get_body(planet_label, time_grid)
                object_altaz = object_body.transform_to(object_frame)
                ax = plot_sky(
                    object_altaz,
                    observer,
                    time_grid,
                    style_kwargs=dict(color=color, label=name, linewidth=3, alpha=0.5, s=size),
                    north_to_east_ccw=NORTH_TO_EAST_CCW,
                )
        
    # Sun
    if live and sun_moon.sun_altitude() > 0:
        name, planet_label, color, size = BODIES[0]
        object_body = get_body(planet_label, time_grid)
        object_altaz = object_body.transform_to(object_frame)
        ax = plot_sky(
            object_altaz,
            observer,
            time_grid,
            style_kwargs=dict(color=color, label=name, linewidth=3, alpha=0.5, s=size),
            north_to_east_ccw=NORTH_TO_EAST_CCW,
        )

    # Title, legend, and config
    astronight_from = observer.astropy_time_to_datetime(observing_start_time).strftime("%m/%d %H:%M")
    astronight_to = observer.astropy_time_to_datetime(observing_end_time).strftime("%m/%d %H:%M")
    if ax is not None:
        ax.legend(loc="upper right", bbox_to_anchor=(1.4, 1))
        if not live:
            ax.set_title(f"{sun_moon.darkness().capitalize()} night: {astronight_from} to {astronight_to}")
        else:
            ax.set_title(f"{astronight_from}")
        plt.figtext(
            0.02,
            0.915,
            "Sunset/rise: {} / {}".format(sun_moon.sun_next_setting_civil(), sun_moon.sun_next_rising_civil()),
            size=12,
        )
        plt.figtext(
            0.02,
            0.895,
            "Moonrise/set: {} / {}".format(sun_moon.moon_next_rising(), sun_moon.moon_next_setting()),
            size=12,
        )
        plt.figtext(0.02, 0.875, "Moon illumination: {:.0f}%".format(sun_moon.moon_illumination()), size=12)
        plt.figtext(
            0.02,
            0.855,
            "Alt constraint min/max: {}° / {}°".format(ALTITUDE_CONSTRAINT_MIN, ALTITUDE_CONSTRAINT_MAX),
            size=12,
        )
        plt.figtext(0.02, 0.835, "Airmass constraint: {}".format(AIRMASS_CONSTRAINT), size=12)
        plt.figtext(0.02, 0.815, "Size constraint min/max: {}' / {}'".format(SIZE_CONSTRAINT_MIN, SIZE_CONSTRAINT_MAX), size=12)
        plt.figtext(0.02, 0.795, "Fraction of time: {:.0f}%".format(FRACTION_OF_TIME_OBSERVABLE_THRESHOLD * 100), size=12)
        plt.figtext(0.02, 0.775, "Moon separation: {}°".format(MOON_SEPARATION_MIN), size=12)
        plt.tight_layout()

    # Save plot
    _LOGGER.debug("Saving plot")
    plot.save_png(plt)

    # Clear plot
    plt.clf()
    
    if not live:
        # Sort available targets by fraction of time observable
        _LOGGER.debug("Sorting targets")
        uptonight_targets.sort("foto")

        # Save reports
        _LOGGER.debug("Saving reports")
        report = Report(observer, uptonight_targets, astronight_from, astronight_to, sun_moon, output_dir, current_day, filter_ext)
        report.save_txt()
        report.save_json()

    print(uptonight_targets)
