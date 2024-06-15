import matplotlib.pyplot as plt


from uptonight.const import (
    OUTPUT_DATESTAMP,
)


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
                plt.savefig(
                    f"{self._output_dir}/uptonight-plot-{self._current_day}{self._filter_ext}.png"
                )
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
