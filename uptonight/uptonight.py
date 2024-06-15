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


def calc(
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

    # Our observer
    observer_location = EarthLocation.from_geodetic(
        location["longitude"], location["latitude"], location["elevation"] * u.m
    )

    observer = Observer(
        name="Backyard",
        location=observer_location,
        pressure=environment["pressure"] * u.bar,
        relative_humidity=environment["relative_humidity"],
        temperature=environment["temperature"] * u.deg_C,
        timezone=timezone(location["timezone"]),
        description="My beloved Backyard Telescope",
    )

    # Define oberserving time range
    utcoffset = (
        datetime.now(pytz.timezone(location["timezone"])).utcoffset().total_seconds()
        / 3600
    )
    sun_moon = SunMoon(observer, observation_date, utcoffset)
    observing_start_time = None
    observing_end_time = None
    if live:
        observing_start_time = Time(
            datetime.utcnow(),
            scale="utc",
            location=observer.location,
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

    _LOGGER.info(
        "Observing start time: {0}".format(
            observing_start_time.strftime("%m/%d/%Y %H:%M:%S")
        )
    )
    current_day = observer.astropy_time_to_datetime(observing_start_time).strftime(
        "%Y%m%d"
    )

    filter_ext = ""
    if type_filter != "":
        filter_ext = f"-{type_filter}"

    # Create the targets table and targets list containing the targets of the csv file plus user defined
    # custom targets. We will iterate over the targets list and use the input_targets table for lookup
    # values while calculating the results
    _LOGGER.debug("Building targets lists")
    targets = Targets(target_list=target_list)
    # Table with targets to calculate
    input_targets = targets.input_targets()
    print(input_targets)
    # List of fixed targets to calculate the fraction of time observable with
    fixed_targets = targets.fixed_targets()

    # Create the observability table which weights the targets based on the given constraints to
    # calculate the fraction of time observable tonight
    _LOGGER.debug("Setting constraints")
    moon_separation = 0
    if not live:
        if constraints["moon_separation_use_illumination"]:
            moon_separation = sun_moon.moon_illumination()
        else:
            moon_separation = constraints["moon_separation_min"]
    observability_constraints = [
        AltitudeConstraint(
            constraints["altitude_constraint_min"] * u.deg,
            constraints["altitude_constraint_max"] * u.deg,
        ),
        AirmassConstraint(constraints["airmass_constraint"]),
        MoonSeparationConstraint(min=moon_separation * u.deg),
    ]

    _LOGGER.info("Creating observability table")
    time_range = Time([observing_start_time, observing_end_time], scale="utc")
    observability_targets = observability_table(
        observability_constraints, observer, fixed_targets, time_range=time_range
    )
    observability_targets["fraction of time observable"].info.format = ".3f"
    fixed_targets = None  # We don't need this list anymore

    # Merge fraction of time observable with input_targets and reverse sort the table
    input_targets["fraction of time observable"] = observability_targets[
        "fraction of time observable"
    ]
    input_targets.sort("fraction of time observable")
    input_targets.reverse()
    observability_targets = None  # We don't need this table anymore

    # This will be our result table
    uptonight_targets = targets.targets_table()

    # Count targets within constraints
    within_threshold = 0
    for index, target in enumerate(input_targets):
        fraction_of_time_observable = input_targets[index][
            "fraction of time observable"
        ]
        size = input_targets[index]["size"]
        if (
            fraction_of_time_observable
            >= constraints["fraction_of_time_observable_threshold"]
            and size >= constraints["size_constraint_min"]
            and size <= constraints["size_constraint_max"]
        ):
            within_threshold = within_threshold + 1

    _LOGGER.info(f"Number of targets within constraints: {within_threshold}")
    if within_threshold > constraints["max_number_within_threshold"]:
        within_threshold = constraints["max_number_within_threshold"]

    # Configure the plot
    # Color maps: https://matplotlib.org/stable/tutorials/colors/colormaps.html
    plot = Plot(output_dir, current_day, filter_ext, live)
    cmap = cm.hsv

    # Create grid of times from start_time to end_time
    # with resolution time_resolution
    time_resolution = 15 * u.minute
    time_grid = time_grid_from_range(
        [observing_start_time, observing_end_time], time_resolution=time_resolution
    )

    # Creating plot and table of targets
    _LOGGER.info("Creating plot and table of targets")
    target_no = 0
    ax = None
    for index, target_row in enumerate(input_targets):
        fraction_of_time_observable = target_row["fraction of time observable"]
        if (
            fraction_of_time_observable
            >= constraints["fraction_of_time_observable_threshold"]
            and target_no < constraints["max_number_within_threshold"]
            or target_row["name"] in bucket_list
        ):
            if str(target_row["description"]) == "--":
                target_row["description"] = target_row["name"]
                target_row["name"] = "--"
            target = FixedTarget(
                coord=SkyCoord(
                    f"{target_row['ra']} {target_row['dec']}", unit=(u.hourangle, u.deg)
                ),
                name=str(target_row["description"])
                + str(
                    f" ({target_row['name']}, {target_row['size']}', {target_row['mag']})"
                ),
            )

            azimuth = observer.altaz(observing_start_time, target).az
            altitude = observer.altaz(observing_start_time, target).alt

            # If an object type is set we filter out everything else
            if (
                type_filter != ""
                and type_filter.lower() not in input_targets[index]["type"].lower()
            ):
                continue

            # Choose marker
            # Square
            marker = "s"
            if "galaxy" in input_targets[index]["type"].lower():
                # Circle
                marker = "o"
            if "nebula" in input_targets[index]["type"].lower():
                # Diamond
                marker = "D"

            size = input_targets[index]["size"]
            if (
                size >= constraints["size_constraint_min"]
                and size <= constraints["size_constraint_max"]
                and target_row["name"] not in done_list
                or target_row["name"] in bucket_list
            ):
                # Calculate meridian transit and antitransit
                meridian_transit_time = observer.target_meridian_transit_time(
                    observing_start_time, target, which="next"
                )
                if meridian_transit_time < observing_end_time:
                    meridian_transit = str(
                        observer.astropy_time_to_datetime(
                            meridian_transit_time
                        ).strftime("%m/%d/%Y %H:%M:%S")
                    )
                else:
                    meridian_transit = ""

                meridian_antitransit_time = observer.target_meridian_antitransit_time(
                    observing_start_time, target, which="next"
                )
                if meridian_antitransit_time < observing_end_time:
                    meridian_antitransit = str(
                        observer.astropy_time_to_datetime(
                            meridian_antitransit_time
                        ).strftime("%m/%d/%Y %H:%M:%S")
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
                        input_targets[index]["type"],
                        input_targets[index]["constellation"],
                        input_targets[index]["size"],
                        input_targets[index]["mag"],
                        fraction_of_time_observable,
                    )
                )

                # Plot target
                ax = plot_sky(
                    target,
                    observer,
                    time_grid,
                    style_kwargs=dict(
                        color=cmap(target_no / within_threshold * 0.75),
                        label="_Hidden",
                        marker=marker,
                        s=3,
                    ),
                    north_to_east_ccw=constraints["north_to_east_ccw"],
                )
                ax = plot_sky(
                    target,
                    observer,
                    observing_start_time,
                    style_kwargs=dict(
                        color=cmap(target_no / within_threshold * 0.75),
                        label=target.name,
                        marker=marker,
                        s=30,
                    ),
                    north_to_east_ccw=constraints["north_to_east_ccw"],
                )
                target_no = target_no + 1

        if target_row["name"] == "Polaris" or target_row["name"] in CUSTOM_TARGETS:
            target = FixedTarget(
                coord=SkyCoord(
                    f"{target_row['ra']} {target_row['dec']}", unit=(u.hourangle, u.deg)
                ),
                name=target_row["description"]
                + f" ({target_row['name']}, {target_row['size']}', {target_row['mag']})",
            )
            ax = plot_sky(
                target,
                observer,
                time_grid,
                style_kwargs=dict(color="w", label=target.name, marker="*"),
                north_to_east_ccw=constraints["north_to_east_ccw"],
            )

    # Bodies
    object_frame = AltAz(obstime=time_grid, location=observer.location)

    for name, planet_label, color, size in BODIES:
        if planet_label != "sun":
            if planet_label != "moon":
                # No altitude constraints for the planets
                observability_constraints = [
                    AltitudeConstraint(0 * u.deg, 90 * u.deg),
                    MoonSeparationConstraint(min=moon_separation * u.deg),
                ]
            else:
                # No constraints for the moon
                observability_constraints = [
                    AltitudeConstraint(0 * u.deg, 90 * u.deg),
                ]
            observable = is_observable(
                observability_constraints,
                observer,
                get_body(planet_label, time_range),
                time_range=time_range,
            )
            if True in observable:
                _LOGGER.debug(f"%s is observable", planet_label.capitalize())
                object_body = get_body(planet_label, time_grid)
                object_altaz = object_body.transform_to(object_frame)
                ax = plot_sky(
                    object_altaz,
                    observer,
                    time_grid,
                    style_kwargs=dict(
                        color=color, label=name, linewidth=3, alpha=0.5, s=size
                    ),
                    north_to_east_ccw=constraints["north_to_east_ccw"],
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
            north_to_east_ccw=constraints["north_to_east_ccw"],
        )

    # Title, legend, and config
    astronight_from = observer.astropy_time_to_datetime(observing_start_time).strftime(
        "%m/%d %H:%M"
    )
    astronight_to = observer.astropy_time_to_datetime(observing_end_time).strftime(
        "%m/%d %H:%M"
    )
    duration = str(
        observer.astropy_time_to_datetime(observing_end_time)
        - observer.astropy_time_to_datetime(observing_start_time)
    ).split(":")
    if ax is not None:
        ax.legend(loc="upper right", bbox_to_anchor=(1.4, 1))
        if not live:
            ax.set_title(
                f"{sun_moon.darkness().capitalize()} night: {astronight_from} to {astronight_to} (duration {duration[0]}:{duration[1]}hs)"
            )
        else:
            ax.set_title(f"{astronight_from}")
        plt.figtext(
            0.02,
            0.915,
            "Sunset/rise: {} / {}".format(
                sun_moon.sun_next_setting_civil(), sun_moon.sun_next_rising_civil()
            ),
            size=12,
        )
        plt.figtext(
            0.02,
            0.895,
            "Moonrise/set: {} / {}".format(
                sun_moon.moon_next_rising(), sun_moon.moon_next_setting()
            ),
            size=12,
        )
        plt.figtext(
            0.02,
            0.875,
            "Moon illumination: {:.0f}%".format(sun_moon.moon_illumination()),
            size=12,
        )
        plt.figtext(
            0.02,
            0.855,
            "Alt constraint min/max: {}° / {}°".format(
                constraints["altitude_constraint_min"],
                constraints["altitude_constraint_max"],
            ),
            size=12,
        )
        plt.figtext(
            0.02,
            0.835,
            "Airmass constraint: {}".format(constraints["airmass_constraint"]),
            size=12,
        )
        plt.figtext(
            0.02,
            0.815,
            "Size constraint min/max: {}' / {}'".format(
                constraints["size_constraint_min"], constraints["size_constraint_max"]
            ),
            size=12,
        )
        plt.figtext(
            0.02,
            0.795,
            "Fraction of time: {:.0f}%".format(
                constraints["fraction_of_time_observable_threshold"] * 100
            ),
            size=12,
        )
        plt.figtext(
            0.02, 0.775, "Moon separation: {:.0f}°".format(moon_separation), size=12
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

    if not live:
        # Save reports
        _LOGGER.debug("Saving reports")
        report = Report(
            observer,
            uptonight_targets,
            astronight_from,
            astronight_to,
            sun_moon,
            output_dir,
            current_day,
            filter_ext,
            constraints,
        )
        report.save_txt()
        report.save_json()

    print(uptonight_targets)
