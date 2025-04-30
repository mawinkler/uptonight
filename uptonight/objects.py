import logging

from astroplan import (
    FixedTarget,
    time_grid_from_range,
)
from astroplan.plots import plot_sky
from astropy import units as u
from astropy.coordinates import SkyCoord
from matplotlib import cm

_LOGGER = logging.getLogger(__name__)


class UpTonightObjects:
    """UpTonight Objects"""

    def __init__(
        self,
        observer,
        observation_timeframe,
        constraints,
        input_targets,
        custom_targets,
    ):
        """Init objects

        Args:
            observer (Observer): The astroplan opbserver
            observation_timeframe (dict): Oberserving time ranges
            constraints (dict): Observing contraints
            input_targets (Table): Deep sky objects to calculate
        """
        self._observer = observer
        self._observation_timeframe = observation_timeframe
        self._constraints = constraints
        self._input_targets = input_targets
        self._custom_targets = custom_targets

        _LOGGER.info(f"Deep Sky Objects loaded: {len(self._input_targets)}")

    def objects(
        self,
        uptonight_targets,
        ax,
        bucket_list=[],
        done_list=[],
        type_filter="",
    ):
        """Create plot and table of targets

        Args:
            uptonight_targets (Table): Result table for targets.
            bucket_list (list): List of targets on the bucket list.
            done_list (list): List of targets on the done list to ignore.
            type_filter (str): Filter

        Returns:
            uptonight_targets (Table): Result table for targets.
            ax (Axes): An Axes object (ax) with a map of the sky.
        """

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

        within_threshold = within_threshold + len(bucket_list)

        _LOGGER.info(f"Number of deep sky objects within constraints or on bucket list: {within_threshold}")
        if within_threshold > self._constraints["max_number_within_threshold"]:
            within_threshold = self._constraints["max_number_within_threshold"]

        # Create grid of times from start_time to end_time
        # with resolution time_resolution
        time_resolution = 1 * u.minute
        time_grid = time_grid_from_range(
            [
                self._observation_timeframe["observing_start_time"],
                self._observation_timeframe["observing_end_time"],
            ],
            time_resolution=time_resolution,
        )

        _LOGGER.info("Creating plot and table of deep sky objects")
        cmap = cm.hsv

        target_no = 0
        for index, target_row in enumerate(self._input_targets):
            fraction_of_time_observable = target_row["fraction of time observable"]

            if within_threshold > 0:
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

                        if str(target_row["description"]) != "":
                            name = str(target_row["description"]) + str(
                                f" ({target_row['name']}, size: {target_row['size']:.0f}', foto: {fraction_of_time_observable:.2f}"
                            )
                        else:
                            name = str(target_row["name"]) + str(
                                f" (size: {target_row['size']:.0f}', foto: {fraction_of_time_observable:.2f}"
                            )
                        if self._input_targets[index]["mag"] == 0:
                            name += ")"
                        else:
                            name += f", mag: {self._input_targets[index]['mag']:.1f})"

                        target = FixedTarget(
                            coord=SkyCoord(
                                f"{target_row['ra']} {target_row['dec']}",
                                unit=(u.hourangle, u.deg),
                            ),
                            name=name,
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
                        meridian_transit, meridian_antitransit = self._transits(target)

                        # Add target to results table
                        uptonight_targets.add_row(
                            (
                                target_row["name"],
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
                                marker=".",
                                s=0.1,
                            ),
                            north_to_east_ccw=self._constraints["north_to_east_ccw"],
                            ax=ax,
                        )
                        ax = plot_sky(
                            target,
                            self._observer,
                            self._observation_timeframe["observing_start_time"],
                            style_kwargs=dict(
                                color=cmap(target_no / within_threshold * 0.75),
                                label=f"{str(target_no + 1)}: {target.name}",
                                marker=marker,
                                s=30,
                            ),
                            north_to_east_ccw=self._constraints["north_to_east_ccw"],
                            ax=ax,
                        )

                        altaz = self._observer.altaz(self._observation_timeframe["observing_start_time"], target)
                        az = altaz.az.radian
                        alt = 90 - altaz.alt.degree  # Convert altitude to radial distance for polar plot

                        # Annotate the target with its number
                        ax.annotate(
                            str(target_no + 1),
                            (az, alt),
                            textcoords="offset points",
                            xytext=(5, 5),
                            ha="left",
                            fontsize=6,
                        )

                        target_no = target_no + 1

            # Always add Polaris
            if target_row["name"] == "Polaris" or target_row["name"] in self._custom_targets:
                target = FixedTarget(
                    coord=SkyCoord(
                        f"{target_row['ra']} {target_row['dec']}",
                        unit=(u.hourangle, u.deg),
                    ),
                    name="_"
                    + target_row["description"]
                    + f" ({target_row['name']}, {target_row['size']}', {str(int(round(self._input_targets[index]['mag'] * 10, 0)) / 10)})",
                )
                ax = plot_sky(
                    target,
                    self._observer,
                    time_grid,
                    style_kwargs=dict(color="w", label=target.name, marker="*"),
                    north_to_east_ccw=self._constraints["north_to_east_ccw"],
                )

        return uptonight_targets, ax

    def _transits(self, target):
        """Calculates meridian and antimeridian transit times for the target

        Args:
            target (FixedTarget): The fixed target

        Returns:
            tuple(str, str): meridian_transit, meridian_antitransit
        """
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
                self._observer.astropy_time_to_datetime(meridian_antitransit_time).strftime("%m/%d/%Y %H:%M:%S")
            )
        else:
            meridian_antitransit = ""

        return meridian_transit, meridian_antitransit
