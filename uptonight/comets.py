import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from astroplan import (
    FixedTarget,
    time_grid_from_range,
)
from astroplan.plots import plot_sky
from astropy import units as u
from astropy.coordinates import SkyCoord
from matplotlib import cm
from skyfield.almanac import find_discrete, risings_and_settings
from skyfield.api import Loader, Topos, load
from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN
from skyfield.data import mpc

from uptonight.const import (
    DEFAULT_MAGNITUDE_LIMIT,
)

_LOGGER = logging.getLogger(__name__)

# The position of this comet is calculated from orbital elements published by the Minor Planet Center (MPC).


class UpTonightComets:
    """UpTonight Comets"""

    def __init__(
        self,
        observer,
        observation_timeframe,
        constraints,
        output_dir=".",
        magnitude_limit=DEFAULT_MAGNITUDE_LIMIT,
    ):
        """Init comets

        Args:
            observer (Observer): The astroplan observer
            observation_timeframe (dict): Observing time ranges
            constraints (dict): Observing constraints
            output_dir (str): Output directory
            magnitude_limit (float): Magnitude limit
        """
        self._observer = observer
        self._observation_timeframe = observation_timeframe
        self._constraints = constraints
        self._output_dir = output_dir
        self._magnitude_limit = magnitude_limit

        # Load comet data
        with load.open(mpc.COMET_URL) as f:
            self._comets_data = mpc.load_comets_dataframe(f)

        # Load Skyfield data
        _sf_load = Loader("./skyfield-data")
        self._ts = _sf_load.timescale()
        self._eph = _sf_load("de421.bsp")

        _LOGGER.info(f"Comets URL: {mpc.COMET_URL}")
        _LOGGER.info(f"Comets loaded: {len(self._comets_data)}")

        # Convert observers location to decimal
        location_dec = SkyCoord(
            lat=self._observer.latitude,
            lon=self._observer.longitude,
            unit=(u.deg, u.deg),
            frame="geocentrictrueecliptic",
        )

        # Keep only the most recent orbit for each comet,
        # and index by designation for fast lookup.
        self._comets_data = (
            self._comets_data.sort_values("reference")
            .groupby("designation", as_index=False)
            .last()
            .set_index("designation", drop=False)
        )

        # Load Earth and observer's location
        self._sun, self._earth = self._eph["sun"], self._eph["earth"]
        self._topos = Topos(
            latitude_degrees=location_dec.lat.deg,
            longitude_degrees=location_dec.lon.deg,
            elevation_m=self._observer.elevation.value,
        )
        self._observer_location = self._earth + self._topos

        # Define observation time (e.g., a specific date in 2024)
        self._observation_time = self._ts.from_astropy(self._observation_timeframe["observing_start_time"])

    def comets(self, uptonight_comets, ax):
        """Create plot and table of comets

        Args:
            uptonight_comets (Table): Result table for comets.

        Returns:
            uptonight_comets (Table): Result table for comets.
            ax (Axes): An Axes object (ax) with a map of the sky.
        """
        # Single pass: compute all positional and distance data
        _LOGGER.debug(f"Computing positions for {len(self._comets_data)} comets")
        ephemeris = self._comets_data.apply(self._compute_comet_ephemeris, axis=1)
        self._comets_data[["distance_au_earth", "distance_au_sun", "ra", "dec", "alt", "az"]] = ephemeris

        # Compute visual magnitudes and filter by magnitude limit
        _LOGGER.debug(
            f"Computing visual magnitudes for {len(self._comets_data)} comets (magnitude limit: {self._magnitude_limit})"
        )
        self._comets_data["visual_magnitude"] = self._comets_data.apply(self._compute_visual_magnitude, axis=1)
        self._comets_data = self._comets_data.loc[self._comets_data["visual_magnitude"] < self._magnitude_limit]

        if len(self._comets_data) > 0:
            observable_comets = self._comets_data.sort_values(by=["visual_magnitude"]).copy()

            # Single pass: compute rise and set times
            _LOGGER.debug(f"Computing rise/set times for {len(observable_comets)} comets")
            self._start_time = self._observation_time - timedelta(hours=12)
            self._end_time = self._observation_time + timedelta(hours=12)
            rise_set = observable_comets.apply(self._compute_rise_set_time, axis=1)
            observable_comets[["rise_time", "set_time"]] = rise_set
            observable_comets["is_observable"] = observable_comets.apply(self._comet_observable, axis=1)
            observable_comets = observable_comets[observable_comets["is_observable"]]
            observable_comets_no = len(observable_comets)
            _LOGGER.info(f"Number of comets observable: {observable_comets_no}")

            if observable_comets_no > 0:
                # Find the visually brightest comet (lowest magnitude)
                brightest_comet = observable_comets.loc[observable_comets["visual_magnitude"].idxmin()]
                _LOGGER.info(
                    f"The visually brightest comet is {brightest_comet['designation']} with a magnitude of {brightest_comet['visual_magnitude']:.2f}."
                )

                with open(f"{self._output_dir}/comets.txt", "w") as f:
                    f.write(observable_comets.to_string(header=True, index=False))

                observable_comets_selected = observable_comets[
                    [
                        "designation",
                        "distance_au_earth",
                        "distance_au_sun",
                        "magnitude_g",
                        "visual_magnitude",
                        "alt",
                        "az",
                        "ra",
                        "dec",
                        "rise_time",
                        "set_time",
                    ]
                ]

                cmap = cm.hsv
                # For the comets, we're using the timespan in between civil darkness
                time_resolution = 1 * u.minute
                time_grid = time_grid_from_range(
                    [
                        self._observation_timeframe["observing_start_time_civil"],
                        self._observation_timeframe["observing_end_time_civil"],
                    ],
                    time_resolution=time_resolution,
                )

                _LOGGER.info("Creating plot and table of comets")
                target_no = 0
                for row in observable_comets_selected.itertuples(index=True):
                    target = FixedTarget(
                        coord=SkyCoord(
                            f"{row.ra} {row.dec}",
                            unit=(u.hourangle, u.deg),
                        ),
                        name=str(row.designation) + f", mag:  {str(int(round(row.visual_magnitude * 10, 0)) / 10)}",
                    )

                    ax = plot_sky(
                        target,
                        self._observer,
                        time_grid,
                        style_kwargs=dict(
                            color=cmap(target_no / observable_comets_no * 0.75),
                            label="_Hidden",
                            marker=".",
                            s=0.5,
                        ),
                        north_to_east_ccw=self._constraints["north_to_east_ccw"],
                        ax=ax,
                    )
                    ax = plot_sky(
                        target,
                        self._observer,
                        self._observation_timeframe["observing_start_time_civil"],
                        style_kwargs=dict(
                            color=cmap(target_no / observable_comets_no * 0.75),
                            label=target.name,
                            marker="x",
                            s=30,
                        ),
                        north_to_east_ccw=self._constraints["north_to_east_ccw"],
                        ax=ax,
                    )

                    uptonight_comets.add_row(
                        (
                            row.designation,
                            target.coord.to_string("hmsdms"),
                            row.distance_au_earth,
                            row.distance_au_sun,
                            row.magnitude_g,
                            row.visual_magnitude,
                            row.alt,
                            row.az,
                            str(row.rise_time.strftime("%m/%d/%Y %H:%M:%S")),
                            str(row.set_time.strftime("%m/%d/%Y %H:%M:%S")),
                        )
                    )

                    target_no = target_no + 1
        else:
            _LOGGER.debug("No comets within constraints")

        return uptonight_comets, ax

    def _compute_comet_ephemeris(self, comet):
        """Compute all positional and distance data for one comet in a single orbit propagation pass.

        Returns a pandas Series with distance_au_earth, distance_au_sun, ra (hours),
        dec (degrees), alt (degrees), az (degrees).
        """
        comet_helio = mpc.comet_orbit(comet, self._ts, GM_SUN)
        comet_orbit = self._sun + comet_helio

        distance_sun = comet_helio.at(self._observation_time).distance().au
        ra, dec, distance_earth = self._earth.at(self._observation_time).observe(comet_orbit).radec()
        alt, az, _ = self._observer_location.at(self._observation_time).observe(comet_orbit).apparent().altaz()

        return pd.Series(
            {
                "distance_au_earth": distance_earth.au,
                "distance_au_sun": distance_sun,
                "ra": ra.hours,
                "dec": dec.degrees,
                "alt": alt.degrees,
                "az": az.degrees,
            }
        )

    def _compute_rise_set_time(self, comet):
        """Compute rise and set times for a comet in a single find_discrete call.

        Returns a pandas Series with rise_time and set_time (datetime or None each).
        """
        comet_orbit = self._sun + mpc.comet_orbit(comet, self._ts, GM_SUN)

        t, y = find_discrete(
            self._start_time, self._end_time, risings_and_settings(self._eph, comet_orbit, self._topos)
        )

        rise_times = t[y == 1]
        set_times = t[y == 0]

        # If set comes before rise in our window, extend forward to catch the next set
        if len(rise_times) > 0 and len(set_times) > 0 and set_times[0].tt < rise_times[0].tt:
            _start_time = self._observation_time + timedelta(hours=12)
            _end_time = self._observation_time + timedelta(hours=36)
            t, y = find_discrete(_start_time, _end_time, risings_and_settings(self._eph, comet_orbit, self._topos))

        rise_time, set_time = None, None
        for time, event in zip(t, y):
            event_time = time.utc_datetime()
            if event == 1:
                rise_time = event_time
            elif event == 0:
                set_time = event_time

        if isinstance(rise_time, datetime):
            rise_time = rise_time.replace(tzinfo=None).replace(microsecond=0)
        if isinstance(set_time, datetime):
            set_time = set_time.replace(tzinfo=None).replace(microsecond=0)

        return pd.Series({"rise_time": rise_time, "set_time": set_time})

    def _compute_visual_magnitude(self, comet):
        """Calculate visual magnitude using the standard comet magnitude formula."""
        return (
            comet["magnitude_g"]
            + 5 * np.log10(comet["distance_au_earth"])
            + comet["magnitude_k"] * np.log10(comet["distance_au_sun"])
        )

    def _comet_observable(self, comet):
        """Test if comet is observable during the civil darkness

        Args:
            comet (row): Row of comet

        Returns:
            (bool): True if comet is visible
        """
        # Always up or down tests
        if comet["rise_time"] is None and comet["alt"] <= 0:
            _LOGGER.debug(f"Comet {comet['designation']} is not rising and is below the horizon, so cannot be observed")
            return False
        if comet["rise_time"] is None and comet["alt"] > 0:
            _LOGGER.debug(f"Comet {comet['designation']} is not rising, but is above the horizon so can be seen")
            return True
        if comet["set_time"] is None and comet["alt"] > 0:
            _LOGGER.debug(f"Comet {comet['designation']} is not setting, but is above the horizon so can be seen")
            return True
        if comet["set_time"] is None and comet["alt"] <= 0:
            _LOGGER.debug(
                f"Comet {comet['designation']} is not setting and is below the horizon, so cannot be observed"
            )
            return False

        start1 = comet["rise_time"].to_datetime64()
        start2 = self._observation_timeframe["observing_start_time"]
        end1 = comet["set_time"].to_datetime64()
        end2 = self._observation_timeframe["observing_end_time"]

        observable = max(start1, start2) <= min(end1, end2)
        _LOGGER.debug(f"Comet {comet['designation']} observable: {observable}.")

        return observable
