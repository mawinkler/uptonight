import logging
import os

import matplotlib.pyplot as plt
import numpy as np
from astroplan import (
    time_grid_from_range,
)
from astropy import units as u
from astropy.coordinates import AltAz, SkyCoord
from matplotlib.colors import LinearSegmentedColormap

from uptonight.const import (
    LAYOUT_PORTRAIT,
)

_LOGGER = logging.getLogger(__name__)
logging.getLogger("matplotlib").setLevel(logging.INFO)


class Plot:
    """UpTonight Plot"""

    def __init__(
        self,
        observer,
        observation_timeframe,
        constraints,
        moon_separation,
        sun_moon,
        output_dir,
        colors,
        current_day,
        filter_ext,
        live,
        layout,
        prefix,
    ):
        """Init plot

        Args:
            observer (Observer): The astroplan opbserver
            observation_timeframe (dict): Oberserving time ranges
            constraints (dict): Observing contraints
            moon_separation (int): Moon separation as degrees
            sun_moon (SunMoon): Sun and Moon helper
            output_dir (str): Output directory
            colors (dict): Color table
            current_day (Time): Day for calculation
            filter_ext (str): Object filter
            live (bool): Live mode
        """
        self._observer = observer
        self._observation_timeframe = observation_timeframe
        self._constraints = constraints
        self._moon_separation = moon_separation
        self._sun_moon = sun_moon
        self._output_dir = output_dir
        self._colors = colors
        self._current_day = current_day
        self._filter_ext = filter_ext
        self._live = live
        self._layout = layout
        self._prefix = prefix

        self._style_plot()

        return None

    def altitude_time_purge(self):
        """Purge old altitude over time plots in the output directory"""
        for filename in os.listdir(f"{self._output_dir}"):
            if filename.startswith(f"uptonight-{self._prefix}alttime") and filename.endswith(".png"):
                full_path = os.path.join(self._output_dir, filename)
                _LOGGER.debug(f"Purge diagram {full_path}")
                try:
                    os.remove(full_path)
                except OSError:
                    pass
            else:
                continue

    def altitude_time(self, target):
        """Create an altitude over time plot for an object

        Args:
            target (Table.row): The objects data
        """
        # Define the Deep Sky Object
        target_id = target.get("id", target.get("target name"))
        target_name = target["target name"]
        target_hmsdms = target["hmsdms"]
        dso = SkyCoord(target_hmsdms, frame="icrs")
        _LOGGER.debug(f"Create altitude plot for {target_id}")

        # Times
        start_time = self._observation_timeframe["observing_start_time"]
        end_time = self._observation_timeframe["observing_end_time"]
        start_time_civil = self._observation_timeframe["observing_start_time_civil"]
        end_time_civil = self._observation_timeframe["observing_end_time_civil"]
        diff_civil_astro = (
            self._observer.astropy_time_to_datetime(start_time)
            - self._observer.astropy_time_to_datetime(start_time_civil)
        ).seconds // 60
        diff_astro_civil = (
            self._observer.astropy_time_to_datetime(end_time_civil) - self._observer.astropy_time_to_datetime(end_time)
        ).seconds // 60

        # Calculate the target
        time_resolution = 1 * u.minute
        time_grid = time_grid_from_range(
            [
                start_time_civil,
                end_time_civil,
            ],
            time_resolution=time_resolution,
        )
        times_plot = np.linspace(
            self._observer.astropy_time_to_datetime(start_time_civil).hour,
            (
                self._observer.astropy_time_to_datetime(end_time_civil)
                - self._observer.astropy_time_to_datetime(start_time_civil)
            ).seconds
            / 3600
            + self._observer.astropy_time_to_datetime(start_time_civil).hour,
            num=len(time_grid),
        )

        # Convert to AltAz frame and extract altitude and azimuth
        altaz_frame = AltAz(obstime=time_grid, location=self._observer.location)
        altaz = dso.transform_to(altaz_frame)
        altitudes = altaz.alt.deg

        # Plotting
        plt.figure(figsize=(15, 10))
        plt.xticks([])
        plt.xlim(times_plot.min(), times_plot.max())
        plt.ylim(0, 90)
        plt.plot(times_plot, altitudes, color=self._colors["alttime"], label=target["target name"], lw=3)
        plt.fill_between(times_plot, 0, altitudes, where=(altitudes > 0), color=self._colors["figure"], alpha=0.8)

        # Labels and title
        plt.ylabel("Altitude [°]", fontsize=12)
        plt.title(f"Altitude of {target_name}")
        plt.grid(True)

        # Sunset and sunrise, fill with gradient
        cmap = LinearSegmentedColormap.from_list(
            "my_cmap", [self._colors["ticks"], self._colors["figure"], self._colors["figure"]]
        )
        norm = plt.Normalize(vmin=times_plot[0], vmax=times_plot[0] + diff_civil_astro)
        width = 2
        for i in range(diff_civil_astro):
            plt.fill_between(times_plot[i : i + width], altitudes[i : i + width], color=cmap(norm(i)), alpha=0.8)
            plt.fill_between(
                times_plot[len(times_plot) - i - 1 - width : len(times_plot) - i - 1],
                altitudes[len(times_plot) - i - 1 - width : len(times_plot) - i - 1],
                color=cmap(norm(i)),
                alpha=0.8,
            )

        # Highlight maximum altitude
        max_altitude = np.max(altitudes)
        max_time = times_plot[np.argmax(altitudes)]
        plt.scatter(
            max_time, max_altitude, color=self._colors["text"], edgecolor=self._colors["alttime"], zorder=5, s=30
        )
        plt.text(
            max_time,
            max_altitude,
            f"alt {max_altitude:.1f}°",
            color=self._colors["text"],
            ha="right",
            fontsize=12,
        )
        plt.axvline(max_time, color=self._colors["meridian"], linestyle="--", lw=1)

        min_altitude = np.min(altitudes)
        min_time = times_plot[np.argmin(altitudes)]
        plt.scatter(
            min_time, min_altitude, color=self._colors["text"], edgecolor=self._colors["alttime"], zorder=5, s=30
        )
        plt.text(
            min_time,
            min_altitude,
            f"alt {min_altitude:.1f}°",
            color=self._colors["text"],
            ha="right",
            fontsize=12,
        )
        plt.axvline(min_time, color=self._colors["meridian"], linestyle="--", lw=1)

        # Horizon
        plt.axhline(0, color=self._colors["meridian"], linestyle="--", lw=1)

        # Mark sunset (civil and astronomical)
        plt.axvline(times_plot[0], color=self._colors["ticks"], linestyle="--", lw=1)
        plt.axvline(times_plot[diff_civil_astro - 1], color=self._colors["ticks"], linestyle="--", lw=1)

        # Mark sunrise (civil and astronomical)
        plt.axvline(times_plot[-1], color=self._colors["ticks"], linestyle="--", lw=1)
        plt.axvline(
            times_plot[len(times_plot) - diff_astro_civil - 1], color=self._colors["ticks"], linestyle="--", lw=1
        )

        # Texts
        plt.text(
            times_plot[0],
            -4,
            self._observer.astropy_time_to_datetime(start_time_civil).strftime("%m/%d %H:%M"),
            fontsize=12,
            ha="center",
        )
        plt.text(
            times_plot[diff_civil_astro - 1],
            -4,
            self._observer.astropy_time_to_datetime(start_time).strftime("%m/%d %H:%M"),
            fontsize=12,
            ha="center",
        )
        plt.text(
            times_plot[-1],
            -4,
            self._observer.astropy_time_to_datetime(end_time_civil).strftime("%m/%d %H:%M"),
            fontsize=12,
            ha="center",
        )
        plt.text(
            times_plot[len(times_plot) - diff_astro_civil - 1],
            -4,
            self._observer.astropy_time_to_datetime(end_time).strftime("%m/%d %H:%M"),
            fontsize=12,
            ha="center",
        )

        # Save the plot
        plot_name = f"uptonight-{self._prefix}alttime-{target_id.lower().replace(' ', '-').replace('/', '-')}.png"
        plt.savefig(f"{self._output_dir}/{plot_name}")

        plt.clf()
        plt.close()

    def save_png(self, plt, output_datestamp):
        """Save plot as png

        Args:
            plt (Plot): The plot
        """
        if not self._live:
            if output_datestamp:
                plt.savefig(
                    f"{self._output_dir}/uptonight-{self._prefix}plot-{self._current_day}{self._filter_ext}.png"
                )
            plt.savefig(f"{self._output_dir}/uptonight-{self._prefix}plot{self._filter_ext}.png")
        else:
            plt.savefig(f"{self._output_dir}/uptonight-{self._prefix}liveplot{self._filter_ext}.png")

    def legend(self, ax, astronight_from, astronight_to):
        """Create legend and descriptions of the plot

        Args:
            ax (Axes): An Axes object (ax) with a map of the sky.
            astronight_from (str): Datetime string for beginning of astronomical darkness
            astronight_to (str): Datetime string for ending of astronomical darkness
        """

        figtext_x = 0.02
        figtext_y_inc_large = 0.020
        figtext_y_inc_small = 0.015
        if self._layout == LAYOUT_PORTRAIT:
            # figtext_y = 0.4
            figtext_y = 0.46
        else:
            figtext_y = 0.915

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
            if self._layout == LAYOUT_PORTRAIT:
                # ax.legend(loc="upper right", bbox_to_anchor=(0.5, -0.075))
                ax.legend(loc="upper right", bbox_to_anchor=(1.15, 0.049))
            else:
                ax.legend(loc="upper right", bbox_to_anchor=(1.4, 1))

            if not self._live:
                ax.set_title(
                    f"{self._sun_moon.darkness().capitalize()} night: {astronight_from} to {astronight_to} (duration {duration[0]}:{duration[1]}hs)"
                )
            else:
                ax.set_title(f"{astronight_from}")
            plt.figtext(
                figtext_x,
                figtext_y,
                "Sunset/rise: {} / {}".format(
                    self._sun_moon.sun_next_setting_civil_short(),
                    self._sun_moon.sun_next_rising_civil_short(),
                ),
                size=12,
            )
            figtext_y -= figtext_y_inc_large
            plt.figtext(
                figtext_x,
                figtext_y,
                "Moonrise/set: {} / {}".format(
                    self._sun_moon.moon_next_rising_short(),
                    self._sun_moon.moon_next_setting_short(),
                ),
                size=12,
            )
            figtext_y -= figtext_y_inc_large
            plt.figtext(
                figtext_x,
                figtext_y,
                "Moon illumination: {:.0f}%".format(self._sun_moon.moon_illumination()),
                size=12,
            )
            figtext_y -= figtext_y_inc_large
            plt.figtext(
                figtext_x,
                figtext_y,
                "Alt constraint min/max: {}° / {}°".format(
                    self._constraints["altitude_constraint_min"],
                    self._constraints["altitude_constraint_max"],
                ),
                size=12,
            )
            figtext_y -= figtext_y_inc_large
            plt.figtext(
                figtext_x,
                figtext_y,
                "Airmass constraint: {}".format(self._constraints["airmass_constraint"]),
                size=12,
            )
            figtext_y -= figtext_y_inc_large
            plt.figtext(
                figtext_x,
                figtext_y,
                "Size constraint min/max: {}' / {}'".format(
                    self._constraints["size_constraint_min"],
                    self._constraints["size_constraint_max"],
                ),
                size=12,
            )
            figtext_y -= figtext_y_inc_large
            plt.figtext(
                figtext_x,
                figtext_y,
                "Fraction of time: {:.0f}%".format(self._constraints["fraction_of_time_observable_threshold"] * 100),
                size=12,
            )
            figtext_y -= figtext_y_inc_large
            plt.figtext(
                figtext_x,
                figtext_y,
                "Moon separation: {:.0f}°".format(self._moon_separation),
                size=12,
            )
            figtext_y -= figtext_y_inc_large

            plt.figtext(figtext_x, figtext_y, "Solar System: Big circle", size=8)
            figtext_y -= figtext_y_inc_small
            plt.figtext(figtext_x, figtext_y, "DSO Nebula: Diamond", size=8)
            figtext_y -= figtext_y_inc_small
            plt.figtext(figtext_x, figtext_y, "DSO Galaxy: Circle", size=8)
            figtext_y -= figtext_y_inc_small
            plt.figtext(figtext_x, figtext_y, "DSO Rest: Square", size=8)
            figtext_y -= figtext_y_inc_small
            plt.figtext(figtext_x, figtext_y, "Comets: x", size=8)

            # plt.tight_layout()

    def _style_plot(self):
        """Style modifications for the plot"""

        # Font
        plt.rcParams["font.size"] = 14

        # Lines
        plt.rcParams["lines.linewidth"] = 2
        plt.rcParams["lines.markersize"] = 4

        plt.rcParams["xtick.labelsize"] = 13
        plt.rcParams["ytick.labelsize"] = 13
        plt.rcParams["xtick.color"] = self._colors["ticks"]  # "#F2F2F2"
        plt.rcParams["ytick.color"] = self._colors["ticks"]  # "#F2F2F2"

        # Axes
        plt.rcParams["axes.titlesize"] = 14
        plt.rcParams["axes.labelcolor"] = self._colors["text"]  # "w"
        plt.rcParams["axes.facecolor"] = self._colors["axes"]  # "#262626"
        plt.rcParams["axes.edgecolor"] = self._colors["axes"]  # "#F2F2F2"
        if self._layout == LAYOUT_PORTRAIT:
            plt.rcParams["axes.titley"] = 1.05
        else:
            plt.rcParams["axes.titley"] = 1.05
        # Legend
        plt.rcParams["legend.facecolor"] = self._colors["legend"]  # "#262626"
        plt.rcParams["legend.edgecolor"] = self._colors["legend"]  # "#262626"
        plt.rcParams["legend.fontsize"] = 6
        # plt.rcParams["legend.framealpha"] = 0.2

        # Figure
        plt.rcParams["figure.facecolor"] = self._colors["figure"]  # "#1C1C1C"
        plt.rcParams["figure.edgecolor"] = self._colors["figure"]  # "#1C1C1C"
        if self._layout == LAYOUT_PORTRAIT:
            plt.rcParams["figure.figsize"] = (10, 15)
        else:
            plt.rcParams["figure.figsize"] = (15, 10)
        plt.rcParams["figure.dpi"] = 300

        # Other
        plt.rcParams["grid.color"] = self._colors["grid"]  # "w"
        plt.rcParams["text.color"] = self._colors["text"]  # "w"
