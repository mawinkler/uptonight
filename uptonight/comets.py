import logging
from datetime import datetime, timedelta

import numpy as np
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

    # Load comet data
    # with load.open(mpc.COMET_URL, reload=True) as f:
    with load.open(mpc.COMET_URL) as f:
        _comets_data = mpc.load_comets_dataframe(f)

    # Load Skyfield data
    _load = Loader("~/skyfield-data")
    _ts = _load.timescale()

    # Load ephemeris data for comet orbit propagation
    _eph = _load("de421.bsp")

    def __init__(
        self,
        observer,
        observation_timeframe,
        constraints,
        magnitude_limit=DEFAULT_MAGNITUDE_LIMIT,
    ):
        """Init comets

        Args:
            observer (Observer): The astroplan opbserver
            observation_timeframe (dict): Oberserving time ranges
            constraints (dict): Observing contraints
            magnitude_limit (float): Magnitude limit
        """
        self._observer = observer
        self._observation_timeframe = observation_timeframe
        self._constraints = constraints
        self._magnitude_limit = magnitude_limit

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
        # Compute comets positions and distances

        _LOGGER.debug(f"Compute the distance to Earth for {len(self._comets_data)} comets")
        self._comets_data["distance_au_earth"] = self._comets_data.apply(
            self._get_comet_position_and_distance_earth, axis=1
        )
        _LOGGER.debug(f"Compute the distance to Sun for {len(self._comets_data)} comets")
        self._comets_data["distance_au_sun"] = self._comets_data.apply(
            self._get_comet_position_and_distance_sun, axis=1
        )

        # Function to compute visual magnitude
        # Apply the function to compute visual magnitude for each comet and
        # limit comets visiul magnitude to some reasonable value
        _LOGGER.debug(
            f"Compute the visual magnitudes for {len(self._comets_data)} comets (magnitude limit: {self._magnitude_limit})"
        )
        self._comets_data["visual_magnitude"] = self._comets_data.apply(self._compute_visual_magnitude, axis=1)
        self._comets_data = self._comets_data.loc[self._comets_data["visual_magnitude"] < self._magnitude_limit]

        if len(self._comets_data) > 0:
            # Compute coordinates for comets
            _LOGGER.debug(f"Compute the coordinates for {len(self._comets_data)} comets")
            observable_comets = self._comets_data
            self._comets_data["alt"] = self._comets_data.apply(self._comet_alt, axis=1)
            self._comets_data["az"] = self._comets_data.apply(self._comet_az, axis=1)
            self._comets_data["ra"] = self._comets_data.apply(self._comet_ra, axis=1)
            self._comets_data["dec"] = self._comets_data.apply(self._comet_dec, axis=1)

            # Sort comets by visual magnitude
            observable_comets = observable_comets.sort_values(by=["visual_magnitude"])

            # Calculate rise and set times for the comets
            _LOGGER.debug(f"Compute the rise and set times for {len(observable_comets)} comets")
            self._start_time = self._observation_time - timedelta(hours=12)
            self._end_time = self._observation_time + timedelta(hours=12)
            observable_comets["rise_time"] = observable_comets.apply(self._compute_rise_time, axis=1)
            observable_comets["set_time"] = observable_comets.apply(self._compute_set_time, axis=1)
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

                with open("comets.txt", "w") as f:
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

    def _get_comet_position_and_distance_earth(self, comet):
        """Calculate comets distance to Earth

        Args:
            comet (row): Row of comet

        Returns:
            distance (AU): Distance in astronomical unit
        """
        comet_orbit = self._sun + mpc.comet_orbit(comet, self._ts, GM_SUN)

        # Calculate comet position at the observation time
        ra, dec, distance = self._earth.at(self._observation_time).observe(comet_orbit).radec()

        return distance.au

    def _get_comet_position_and_distance_sun(self, comet):
        """Calculate comets distance to Sun

        Args:
            comet (row): Row of comet

        Returns:
            distance (AU): Distance in astronomical unit
        """
        comet_orbit = mpc.comet_orbit(comet, self._ts, GM_SUN)

        # Calculate comet position at the observation time
        distance = comet_orbit.at(self._observation_time).distance()

        return distance.au

    def _comet_ra(self, comet):
        """Calculate comets ra

        Args:
            comet (row): Row of comet

        Returns:
            ra (hours): Ra
        """
        comet_orbit = self._sun + mpc.comet_orbit(comet, self._ts, GM_SUN)

        # Calculate comet position at the observation time
        ra, dec, distance = self._earth.at(self._observation_time).observe(comet_orbit).radec()

        return ra.hours

    def _comet_dec(self, comet):
        """Calculate comets dec

        Args:
            comet (row): Row of comet

        Returns:
            dec (degrees): Dec
        """
        comet_orbit = self._sun + mpc.comet_orbit(comet, self._ts, GM_SUN)

        # Calculate comet position at the observation time
        ra, dec, distance = self._earth.at(self._observation_time).observe(comet_orbit).radec()

        return dec.degrees

    def _compute_visual_magnitude(self, comet):
        """Calculate comets visual magnitude

        Args:
            comet (row): Row of comet

        Returns:
            visual_magnitude (float): Visual magnitude
        """
        absolute_mag = comet["magnitude_g"]  # Absolute magnitude
        slope_param = comet["magnitude_k"]  # Slope parameter
        heliocentric_dist = comet["distance_au_sun"]  # Distance from the Sun in AU
        geocentric_dist = comet["distance_au_earth"]  # Distance from the Earth in AU

        visual_magnitude = (
            absolute_mag + 5 * np.log10(heliocentric_dist) + 2.5 * slope_param * np.log10(geocentric_dist)
        )

        return visual_magnitude

    def _comet_alt(self, comet):
        """Calculate comets alt

        Args:
            comet (row): Row of comet

        Returns:
            alt (degrees): Altitude
        """
        comet_orbit = self._sun + mpc.comet_orbit(comet, self._ts, GM_SUN)

        # Calculate altitude and azimuth for the comet
        alt, az, distance = self._observer_location.at(self._observation_time).observe(comet_orbit).apparent().altaz()

        # Return altitude
        return alt.degrees

    def _comet_az(self, comet):
        """Calculate comets azimuth

        Args:
            comet (row): Row of comet

        Returns:
            az (degrees): Azimuth
        """
        comet_orbit = self._sun + mpc.comet_orbit(comet, self._ts, GM_SUN)

        # Calculate altitude and azimuth for the comet
        alt, az, distance = self._observer_location.at(self._observation_time).observe(comet_orbit).apparent().altaz()

        # Return azimuth
        return az.degrees

    def _compute_rise_time(self, comet):
        """Calculate comets rise time

        Args:
            comet (row): Row of comet

        Returns:
            rise_time (datetime): Rise time, None if comet does not rise
        """
        comet_orbit = self._sun + mpc.comet_orbit(comet, self._ts, GM_SUN)

        t, y = find_discrete(
            self._start_time, self._end_time, risings_and_settings(self._eph, comet_orbit, self._topos)
        )

        # Filter out rise and set events
        # rise_times = t[y == 1]
        # set_times = t[y == 0]

        rise_time, set_time = None, None
        for time, event in zip(t, y):
            event_time = time.utc_datetime()
            if event == 1:  # Rising event
                rise_time = event_time
            elif event == 0:  # Setting event
                set_time = event_time

        if type(rise_time) is datetime:
            return rise_time.replace(tzinfo=None).replace(microsecond=0)
        return None

    def _compute_set_time(self, comet):
        """Calculate comets set time

        Args:
            comet (row): Row of comet

        Returns:
            set_time (datetime): Set time, None if comet does not rise
        """
        comet_orbit = self._sun + mpc.comet_orbit(comet, self._ts, GM_SUN)

        t, y = find_discrete(
            self._start_time, self._end_time, risings_and_settings(self._eph, comet_orbit, self._topos)
        )

        # Filter out rise and set events
        rise_times = t[y == 1]
        set_times = t[y == 0]

        # Ensure that set_time is after rise_time
        if set_times < rise_times:
            _start_time = self._observation_time + timedelta(hours=12)
            _end_time = self._observation_time + timedelta(hours=36)
            t, y = find_discrete(_start_time, _end_time, risings_and_settings(self._eph, comet_orbit, self._topos))
            # set_times = t[y == 0]

        rise_time, set_time = None, None
        for time, event in zip(t, y):
            event_time = time.utc_datetime()
            if event == 1:  # Rising event
                rise_time = event_time
            elif event == 0:  # Setting event
                set_time = event_time

        if type(set_time) is datetime:
            return set_time.replace(tzinfo=None).replace(microsecond=0)
        return None

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
