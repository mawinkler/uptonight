import matplotlib.pyplot as plt


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
        current_day,
        filter_ext,
        live,
    ):
        """Init plot

        Args:
            observer (Observer): The astroplan opbserver
            observation_timeframe (dict): Oberserving time ranges
            constraints (dict): Observing contraints
            moon_separation (int): Moon separation as degrees
            sun_moon (SunMoon): Sun and Moon helper
            output_dir (str): Output directory
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
        self._current_day = current_day
        self._filter_ext = filter_ext
        self._live = live

        self._style_plot()

        return None

    def save_png(self, plt, output_datestamp):
        """Save plot as png

        Args:
            plt (Plot): The plot
        """
        if not self._live:
            if output_datestamp:
                plt.savefig(f"{self._output_dir}/uptonight-plot-{self._current_day}{self._filter_ext}.png")
            plt.savefig(f"{self._output_dir}/uptonight-plot{self._filter_ext}.png")
        else:
            plt.savefig(f"{self._output_dir}/uptonight-liveplot{self._filter_ext}.png")

    def legend(self, ax, astronight_from, astronight_to):
        """Create legend and descriptions of the plot

        Args:
            ax (Axes): An Axes object (ax) with a map of the sky.
            astronight_from (str): Datetime string for beginning of astronomical darkness
            astronight_to (str): Datetime string for ending of astronomical darkness
        """

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
                    self._sun_moon.sun_next_setting_civil_short(),
                    self._sun_moon.sun_next_rising_civil_short(),
                ),
                size=12,
            )
            plt.figtext(
                0.02,
                0.895,
                "Moonrise/set: {} / {}".format(
                    self._sun_moon.moon_next_rising_short(),
                    self._sun_moon.moon_next_setting_short(),
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
            plt.figtext(0.02, 0.735, "DSO Nebula: Diamond", size=8)
            plt.figtext(0.02, 0.720, "DSO Galaxy: Circle", size=8)
            plt.figtext(0.02, 0.705, "DSO Rest: Square", size=8)
            plt.figtext(0.02, 0.690, "Comets: x", size=8)

            plt.tight_layout()

    def _style_plot(self):
        """Style modifications for the plot"""

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
        plt.rcParams["legend.fontsize"] = 6
        # plt.rcParams["legend.framealpha"] = 0.2

        # Figure
        plt.rcParams["figure.facecolor"] = "#1C1C1C"
        plt.rcParams["figure.edgecolor"] = "#1C1C1C"
        plt.rcParams["figure.figsize"] = (15, 10)
        plt.rcParams["figure.dpi"] = 300

        # Other
        plt.rcParams["grid.color"] = "w"
        plt.rcParams["text.color"] = "w"
