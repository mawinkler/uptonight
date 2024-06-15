from uptonight.const import (
    OUTPUT_DATESTAMP,
)


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
        constraints,
    ):
        self._observer = observer
        self._uptonight_targets = uptonight_targets
        self._astronight_from = astronight_from
        self._astronight_to = astronight_to
        self._sun_moon = sun_moon
        self._output_dir = output_dir
        self._current_day = current_day
        self._filter_ext = filter_ext
        self._constraints = constraints

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

        if len(self._uptonight_targets) > 0:
            self._uptonight_targets.write(
                f"{self._output_dir}/uptonight-report{self._filter_ext}.txt",
                overwrite=True,
                format="ascii.fixed_width_two_line",
            )
        else:
            with open(
                f"{self._output_dir}/uptonight-report{self._filter_ext}.txt",
                "w",
                encoding="utf-8",
            ) as report:
                report.writelines("")

        with open(
            f"{self._output_dir}/uptonight-report{self._filter_ext}.txt",
            "r",
            encoding="utf-8",
        ) as report:
            contents = report.readlines()

        contents = self._report_add_info(contents)

        if OUTPUT_DATESTAMP:
            with open(
                f"{self._output_dir}/uptonight-report-{self._current_day}{self._filter_ext}.txt",
                "w",
                encoding="utf-8",
            ) as report:
                report.write(contents)
        with open(
            f"{self._output_dir}/uptonight-report{self._filter_ext}.txt",
            "w",
            encoding="utf-8",
        ) as report:
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
            self._uptonight_targets.write(
                f"{self._output_dir}/uptonight-report-{self._current_day}.json",
                overwrite=True,
                format="pandas.json",
            )
        self._uptonight_targets.write(
            f"{self._output_dir}/uptonight-report.json",
            overwrite=True,
            format="pandas.json",
        )

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

        moon_separation = 0
        if self._constraints["moon_separation_use_illumination"]:
            moon_separation = self._sun_moon.moon_illumination()
        else:
            moon_separation = self._constraints["moon_separation_min"]

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
        contents.insert(
            12, "Moon illumination: {:.0f}%".format(self._sun_moon.moon_illumination())
        )
        contents.insert(13, "\n")
        contents.insert(
            14,
            f"Contraints: Altitude constraint minimum: {self._constraints['altitude_constraint_min']}°, maximum: {self._constraints['altitude_constraint_max']}°, "
            + f"Airmass constraint: {self._constraints['airmass_constraint']}, Moon separation constraint: {moon_separation:.0f}°, "
            + f"Size constraint minimum: {self._constraints['size_constraint_min']}', maximum: {self._constraints['size_constraint_max']}'",
        )
        contents.insert(15, "\n")
        contents.insert(
            16, f"Altitude and Azimuth calculated for {self._astronight_from}"
        )
        contents.insert(17, "\n")
        contents.insert(18, "\n")

        contents = "".join(contents)

        return contents
