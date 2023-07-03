"""Uptonight - calculate the best objects for tonight"""
import warnings

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
)

# download_IERS_A()

# CDS Name Resolver:
# https://cds.unistra.fr/cgi-bin/Sesame


def create_target_list(target_list):
    """
    Creates a table and list of targets in scope for the calculations.

    The method reads the provided csv file containing the Gary Imm objects and adds custom
    targets defined in the const.py file. The table is used as a lookup table to populate the
    result table. Iteration is done via the FixedTarget list.
    For visibility, Polaris is appended lastly.

    Parameters
    ----------
    none

    Returns
    -------
    astropy.Table, [astroplan.FixedTarget]
        Lookup table, list of targets to calculate
    """

    input_targets = Table.read(f"{target_list}.csv", format="ascii.csv")
    # Create astroplan.FixedTarget objects for each one in the table
    targets = [
        FixedTarget(
            coord=SkyCoord(f"{ra} {dec}", unit=(u.hourangle, u.deg)),
            name=common_name + f" ({name}, {size}\')",
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
        targets.append(
            FixedTarget(coord=SkyCoord(f"{ra} {dec}", unit=(u.hourangle, u.deg)), name=desc + f" ({name}, {size}\')"),
        )

    # Lastly we add Polaris
    targets.append(FixedTarget.from_name("Polaris"))

    return input_targets, targets


def create_uptonight_targets_table():
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


def style_plot():
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
    plt.rcParams["axes.facecolor"] = "#000000"
    plt.rcParams["axes.edgecolor"] = "#F2F2F2"

    # Legend
    plt.rcParams["legend.fontsize"] = 8
    plt.rcParams["legend.framealpha"] = 0.2

    # Figure
    plt.rcParams["figure.facecolor"] = "k"
    plt.rcParams["figure.edgecolor"] = "k"
    plt.rcParams["figure.figsize"] = (15, 10)
    plt.rcParams["figure.dpi"] = 300

    # Other
    plt.rcParams["grid.color"] = "w"
    plt.rcParams["text.color"] = "w"


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
    output_dir="",
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

    Returns
    -------
    None

    Creates
    -------
    plot.png, plot-YYYYMMDD.png:
        Plot of tonights sky. Both generated files are identical.
    report.txt, report-YYYYMMDD.txt:
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

    # Calculate tonights night unless a date is given
    if observation_date is None:
        time = (
            Time(
                datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0),
                scale="utc",
                location=observer.location,
            )
            + 12 * u.hour
        )
    else:
        time = (
            Time(
                datetime.strptime(observation_date, "%m/%d/%y").replace(hour=0, minute=0, second=0, microsecond=0),
                scale="utc",
                location=observer.location,
            )
            + 12 * u.hour
        )
    print("Calculating for: {0}".format(time.strftime("%m/%d/%Y")))

    sun_next_setting = None
    sun_next_rising = None
    darkness = ""
    with warnings.catch_warnings(record=True) as w:
        sun_next_setting = observer.sun_set_time(time, which="next", horizon=-18 * u.deg)
        if len(w):
            if issubclass(w[-1].category, TargetAlwaysUpWarning):
                print("Sun is not setting astronomically")
                w.clear()
                sun_next_setting = observer.sun_set_time(time, which="next", horizon=-12 * u.deg)
                if len(w):
                    if issubclass(w[-1].category, TargetAlwaysUpWarning):
                        print("Sun is not setting nautically")
                        w.clear()
                        sun_next_setting = observer.sun_set_time(time, which="next", horizon=-6 * u.deg)
                        if len(w):
                            if issubclass(w[-1].category, TargetAlwaysUpWarning):
                                print("Sun is not setting civically")
                                sun_next_rising = time + 1 * u.day
                                sun_next_setting = time
                        else:
                            darkness = "civil"
                            sun_next_setting, sun_next_rising = observer.tonight(time=time, horizon=-6 * u.deg)
                else:
                    darkness = "nautical"
                    sun_next_setting, sun_next_rising = observer.tonight(time=time, horizon=-12 * u.deg)
        else:
            darkness = "astronomical"
            sun_next_setting, sun_next_rising = observer.tonight(time=time, horizon=-18 * u.deg)
        # TODO: Proper handling for sun never up
        if len(w):
            if issubclass(w[-1].category, TargetNeverUpWarning):
                print("Sun is not rising astronomically")
                sun_next_rising = time + 1 * u.day
                sun_next_setting = time
            w.clear()

    print("Sun set {0}: {1}".format(darkness, sun_next_setting.strftime("%m/%d/%Y %H:%M:%S")))
    print("Sun rise {0}: {1}".format(darkness, sun_next_rising.strftime("%m/%d/%Y %H:%M:%S")))

    moon_illumination = observer.moon_illumination(sun_next_setting) * 100
    # moon_phase = observer.moon_phase(sun_next_setting)
    # print("Moon illumination: {0}, Moon phase: {1}".format(moon_illumination, moon_phase))
    print("Moon illumination: {:.0f}%".format(moon_illumination))

    # Define oberserving time range
    observing_start_time = sun_next_setting
    observing_end_time = sun_next_rising

    # Create the targets table and targets list containing the targets of the csv file plus user defined
    # custom targets. We will iterate over the targets list and use the input_targets table for lookup
    # values while calculating the results
    print("Building targets list")
    if target_list is None:
        target_list = DEFAULT_TARGETS
    input_targets, targets = create_target_list(target_list)

    # Create the observability table which weights the targets based on the given constraints to
    # calculate the fraction of time observable tonight
    print("Setting constraints")
    constraints = [
        AltitudeConstraint(ALTITUDE_CONSTRAINT_MIN * u.deg, ALTITUDE_CONSTRAINT_MAX * u.deg),
        AirmassConstraint(AIRMASS_CONSTRAINT),
        MoonSeparationConstraint(min=MOON_SEPARATION_MIN * u.deg),
    ]

    print("Creating observability table")
    time_range = Time([observing_start_time, observing_end_time], scale="utc")
    observability_targets = observability_table(constraints, observer, targets, time_range=time_range)
    observability_targets["fraction of time observable"].info.format = ".3f"
    print(observability_targets)

    # This will be our result table
    uptonight_targets = create_uptonight_targets_table()

    # Count targets within constraints
    within_threshold = 0
    for i, target in enumerate(targets):
        fraction_of_time_observable = observability_targets[i]["fraction of time observable"]
        if fraction_of_time_observable >= FRACTION_OF_TIME_OBSERVABLE_THRESHOLD:
            within_threshold = within_threshold + 1

    # Configure the plot
    # Color maps: https://matplotlib.org/stable/tutorials/colors/colormaps.html
    style_plot()
    cmap = cm.hsv
    # Create grid of times from ``start_time`` to ``end_time``
    # with resolution ``time_resolution``
    time_resolution = 15 * u.minute
    time_grid = time_grid_from_range([observing_start_time, observing_end_time], time_resolution=time_resolution)

    print("Creating plot and table of targets for tonight")
    target_no = 0
    ax = None
    for i, target in enumerate(targets):

        fraction_of_time_observable = observability_targets[i]["fraction of time observable"]
        if fraction_of_time_observable >= FRACTION_OF_TIME_OBSERVABLE_THRESHOLD:

            azimuth = observer.altaz(observing_start_time, target).az
            altitude = observer.altaz(observing_start_time, target).alt

            # Add target to final table, leave out Polaris
            if i < (len(targets) - 1):

                # If an object type is set we filter out everything else
                if type_filter != "" and type_filter.lower() not in input_targets[i]["type"].lower():
                    continue

                # Choose marker
                marker = 's'
                if "galaxy" in input_targets[i]["type"].lower():
                    marker = 'o'
                if "nebula" in input_targets[i]["type"].lower():
                    marker = 'D'

                size = input_targets[i]["size"]
                if size >= SIZE_CONSTRAINT_MIN and size <= SIZE_CONSTRAINT_MAX:
                    meridian_transit_time = observer.target_meridian_transit_time(observing_start_time, target, which="next")
                    if meridian_transit_time < observing_end_time:
                        meridian_transit = str(observer.astropy_time_to_datetime(meridian_transit_time).strftime("%m/%d/%Y %H:%M:%S"))
                    else:
                        meridian_transit = ""

                    meridian_antitransit_time = observer.target_meridian_antitransit_time(observing_start_time, target, which="next")
                    if meridian_antitransit_time < observing_end_time:
                        meridian_antitransit = str(
                            observer.astropy_time_to_datetime(meridian_antitransit_time).strftime("%m/%d/%Y %H:%M:%S")
                        )
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
                        style_kwargs=dict(color=cmap(target_no / within_threshold), label=target.name, marker=marker),
                        north_to_east_ccw=NORTH_TO_EAST_CCW,
                    )

            if target.name == "Polaris" or target.name in CUSTOM_TARGETS:
                ax = plot_sky(
                    target,
                    observer,
                    time_grid,
                    style_kwargs=dict(color='w', label=target.name, marker='*'),
                    north_to_east_ccw=NORTH_TO_EAST_CCW,
                )
            target_no = target_no + 1

    moon_frame = AltAz(obstime=time_grid, location=observer.location)
    moon_body = get_body("moon", time_grid)
    moon_altaz = moon_body.transform_to(moon_frame)
    ax = plot_sky(
                    moon_altaz,
                    observer,
                    time_grid,
                    style_kwargs=dict(color='w', label="Moon", marker='X', s=100),
                    north_to_east_ccw=NORTH_TO_EAST_CCW,
                )
    
    astronight_from = observer.astropy_time_to_datetime(observing_start_time).strftime("%m/%d %H:%M")
    astronight_to = observer.astropy_time_to_datetime(observing_end_time).strftime("%m/%d %H:%M")
    sun_set = observer.astropy_time_to_datetime(observer.sun_set_time(time, which="next", horizon=-6 * u.deg)).strftime("%m/%d %H:%M")
    sun_rise = observer.astropy_time_to_datetime(observer.sun_rise_time(time, which="next", horizon=-6 * u.deg)).strftime("%m/%d %H:%M")
    moon_set = observer.astropy_time_to_datetime(observer.moon_set_time(time, which="next", horizon=0 * u.deg)).strftime("%m/%d %H:%M")
    moon_rise = observer.astropy_time_to_datetime(observer.moon_rise_time(time, which="next", horizon=0 * u.deg)).strftime("%m/%d %H:%M")
    # moon_illumination = observer.moon_illumination(time)

    if ax is not None:
        legend = ax.legend(loc="upper right", bbox_to_anchor=(1.4, 1))
        legend.get_frame().set_facecolor("w")
        ax.set_title(f"{darkness.capitalize()} night: {astronight_from} to {astronight_to}")
        plt.figtext(0.02, 0.915, "Sunset/rise: {} / {}".format(sun_set, sun_rise), size=12)
        plt.figtext(0.02, 0.895, "Moonrise/set: {} / {}".format(moon_rise, moon_set), size=12)
        plt.figtext(0.02, 0.875, "Moon illumination: {:.0f}%".format(moon_illumination), size=12)
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

    uptonight_targets.sort("foto")

    # Create output
    print()
    print("-" * 160)
    print("UpTonight")
    print("-" * 160)
    print()
    print(f"Observatory: {observer.name}")
    print(f" - Location: {observer.location.lon:.2f}, {observer.location.lat:.2f}, {observer.location.height:.2f}")
    print()
    print(f"Observation timespan: {astronight_from} to {astronight_to} in {darkness} darkness")
    print("Moon illumination: {:.0f}%".format(moon_illumination))
    print(
        f"Contraints: Altitude constraint minimum: {ALTITUDE_CONSTRAINT_MIN}°, maximum: {ALTITUDE_CONSTRAINT_MAX}°, "
        + f"Airmass constraint: {AIRMASS_CONSTRAINT}, Moon separation constraint: {MOON_SEPARATION_MIN}°, "
        + f"Size constraint minimum: {SIZE_CONSTRAINT_MIN}\', maximum: {SIZE_CONSTRAINT_MAX}\'"
    )
    print(f"Altitude and Azimuth calculated for {astronight_from}")
    print()
    print(uptonight_targets)

    # Save plot
    plt.tight_layout()
    current_day = observer.astropy_time_to_datetime(observing_start_time).strftime("%Y%m%d")
    filter_ext = ""
    if type_filter != "":
        filter_ext = f"-{type_filter}"
    plt.savefig(f"{output_dir}/plot-{current_day}{filter_ext}.png")
    plt.savefig(f"{output_dir}/plot{filter_ext}.png")

    # Create report
    uptonight_targets.write(f"{output_dir}/report-{current_day}{filter_ext}.txt", overwrite=True, format="ascii.fixed_width_two_line")

    with open(f"{output_dir}/report-{current_day}{filter_ext}.txt", "r") as report:
        contents = report.readlines()
    contents.insert(0, "-" * 163)
    contents.insert(1, "\n")
    contents.insert(2, "UpTonight")
    contents.insert(3, "\n")
    contents.insert(4, "-" * 163)
    contents.insert(5, "\n")
    contents.insert(6, "\n")
    contents.insert(7, f"Observatory: {observer.name}\n")
    contents.insert(8, f" - Location: {observer.location.lon:.2f}, {observer.location.lat:.2f}, {observer.location.height:.2f}\n")
    contents.insert(9, "\n")
    contents.insert(10, f"Observation timespan: {astronight_from} to {astronight_to} in {darkness} darkness")
    contents.insert(11, "\n")
    contents.insert(12, "Moon illumination: {:.0f}%".format(moon_illumination))
    contents.insert(13, "\n")
    contents.insert(
        14,
        f"Contraints: Altitude constraint minimum: {ALTITUDE_CONSTRAINT_MIN}°, maximum: {ALTITUDE_CONSTRAINT_MAX}°, "
        + f"Airmass constraint: {AIRMASS_CONSTRAINT}, Moon separation constraint: {MOON_SEPARATION_MIN}°, "
        + f"Size constraint minimum: {SIZE_CONSTRAINT_MIN}\', maximum: {SIZE_CONSTRAINT_MAX}\'",
    )
    contents.insert(15, "\n")
    contents.insert(16, f"Altitude and Azimuth calculated for {astronight_from}")
    contents.insert(17, "\n")
    contents.insert(18, "\n")

    with open(f"{output_dir}/report-{current_day}{filter_ext}.txt", "w") as report:
        contents = "".join(contents)
        report.write(contents)
    with open(f"{output_dir}/report{filter_ext}.txt", "w") as report:
        report.write(contents)
