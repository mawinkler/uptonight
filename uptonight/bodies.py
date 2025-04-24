import logging

from astroplan import (
    AltitudeConstraint,
    FixedTarget,
    is_observable,
    observability_table,
    time_grid_from_range,
)
from astroplan.plots import plot_sky
from astropy import units as u
from astropy.coordinates import AltAz, SkyCoord, get_body
from skyfield.api import Loader, Topos
from skyfield.magnitudelib import planetary_magnitude

from uptonight.const import (
    BODIES,
)

_LOGGER = logging.getLogger(__name__)


class UpTonightBodies:
    """UpTonight Bodies"""

    # Load Skyfield data
    _load = Loader("~/skyfield-data")
    _ts = _load.timescale()

    # Load ephemeris data for comet orbit propagation
    _eph = _load("de421.bsp")

    _eph_map = {
        "mercury": "mercury",
        "venus": "venus",
        "mars": "mars",
        "jupiter": "jupiter barycenter",
        "saturn": "saturn barycenter",
        "uranus": "uranus barycenter",
        "neptune": "neptune barycenter",
    }

    _earth = _eph["earth"]

    def __init__(
        self,
        observer,
        observation_timeframe,
        constraints,
    ):
        """Init bodies

        Args:
            observer (Observer): The astroplan opbserver
            observation_timeframe (dict): Oberserving time ranges
            constraints (dict): Observing contraints
        """
        self._observer = observer
        self._observation_timeframe = observation_timeframe
        self._constraints = constraints

        location_dec = SkyCoord(
            lat=self._observer.latitude,
            lon=self._observer.longitude,
            unit=(u.deg, u.deg),
            frame="geocentrictrueecliptic",
        )
        observer_location = Topos(
            latitude_degrees=location_dec.lat.deg,
            longitude_degrees=location_dec.lon.deg,
            elevation_m=self._observer.elevation.value,
        )

        self._observer_sf = self._earth + observer_location

        _LOGGER.info(f"Bodies loaded: {len(BODIES)}")

    def bodies(self, uptonight_bodies, ax):
        """Create plot and table of bodies

        Args:
            uptonight_bodies (Table): Result table for bodies.

        Returns:
            uptonight_bodies (Table): Result table for bodies.
            ax (Axes): An Axes object (ax) with a map of the sky.
        """
        # For the comets, we're using the timespan in between civil darkness
        time_resolution = 1 * u.minute
        time_grid = time_grid_from_range(
            [
                self._observation_timeframe["observing_start_time"],
                self._observation_timeframe["observing_end_time"],
            ],
            time_resolution=time_resolution,
        )

        _LOGGER.info("Creating plot and table of bodies")
        object_frame = AltAz(obstime=time_grid, location=self._observer.location)

        # No altitude and moon separation constraints for the bodies
        observability_constraints = [
            AltitudeConstraint(0 * u.deg, 90 * u.deg),
        ]

        # for name, planet_label, color, size, jplid in BODIES:
        #     observable = is_observable(
        #         observability_constraints,
        #         self._observer,
        #         get_body(planet_label, self._observation_timeframe["time_range"]),
        #         time_range=self._observation_timeframe["time_range"],
        #     )
        #     if True in observable:
        #         _LOGGER.debug(f"{planet_label.capitalize()} is observable")
        #         object_body = get_body(planet_label, time_grid)
        #         object_altaz = object_body.transform_to(object_frame)
        #         ax = plot_sky(
        #             object_altaz,
        #             self._observer,
        #             time_grid,
        #             style_kwargs=dict(color=color, label=name, linewidth=3, alpha=0.5, s=size),
        #             north_to_east_ccw=self._constraints["north_to_east_ccw"],
        #         )

        _LOGGER.debug("Creating result table of bodies")
        for name, planet_label, color, size, jplid in BODIES:
            # if planet_label != "sun":
            observable = is_observable(
                observability_constraints,
                self._observer,
                get_body(planet_label, self._observation_timeframe["time_range"]),
                time_range=self._observation_timeframe["time_range"],
            )
            if True in observable:
                _LOGGER.debug(f"{planet_label.capitalize()} is observable")

                # target = FixedTarget(name=name, coord=get_body(planet_label, midnight_observer))
                visual_magnitude = 0
                if planet_label != "moon" and planet_label != "sun":
                    # _LOGGER.debug(f"Calculating visual magnitude for {name}")
                    visual_magnitude = self._visual_magnitude(planet_label)
                    target = FixedTarget(
                        name=name + f", mag:  {visual_magnitude:.1f}",
                        coord=get_body(planet_label, self._observation_timeframe["observing_start_time"]),
                    )
                else:
                    target = FixedTarget(
                        name=name,
                        coord=get_body(planet_label, self._observation_timeframe["observing_start_time"]),
                    )

                observability_targets = observability_table(
                    observability_constraints,
                    self._observer,
                    [target],
                    time_range=self._observation_timeframe["time_range"],
                )
                observability_targets["fraction of time observable"].info.format = ".3f"
                fraction_of_time_observable = observability_targets["fraction of time observable"][0]

                # _LOGGER.debug(f"Calculating max altitude for {name}")
                # Calculate meridian transit and antitransit
                meridian_transit_time, meridian_antitransit_time, meridian_transit, meridian_antitransit = (
                    self._transits(target)
                )

                # Calculate max altitude
                object_body, max_altitude_time, max_altitude, azimuth = self._max_altitude(
                    meridian_transit_time, planet_label
                )

                # Add target to results table
                uptonight_bodies.add_row(
                    (
                        name,
                        object_body.to_string("hmsdms"),
                        object_body.ra,
                        object_body.dec,
                        max_altitude,
                        visual_magnitude,
                        azimuth,
                        str(max_altitude_time),
                        meridian_transit,
                        meridian_antitransit,
                        "Planet" if name != "Moon" else "Moon",
                        fraction_of_time_observable,
                    )
                )

                object_body = get_body(planet_label, time_grid)
                object_altaz = object_body.transform_to(object_frame)
                ax = plot_sky(
                    object_altaz,
                    self._observer,
                    time_grid,
                    style_kwargs=dict(color=color, label="_Hidden", marker=".", s=5),
                    north_to_east_ccw=self._constraints["north_to_east_ccw"],
                    ax=ax,
                )
                ax = plot_sky(
                    object_altaz[0],
                    self._observer,
                    self._observation_timeframe["observing_start_time"],
                    style_kwargs=dict(color=color, label=target.name, linewidth=3, alpha=0.5, s=size),
                    north_to_east_ccw=self._constraints["north_to_east_ccw"],
                    ax=ax,
                )
        uptonight_bodies.sort("foto")
        uptonight_bodies.reverse()

        return uptonight_bodies, ax

    def _transits(self, target):
        """Calculate meridian transit and anti transit for target

        Args:
            target (FixedTarget): Fixed target for transit calculation

        Returns:
            meridian_transit_time (Time): Transit time
            meridian_antitransit_time (Time): Anti transit time
            meridian_transit (str): Transit datetime as string
            meridian_antitransit (str): Anti transit datetime as string
        """
        meridian_transit = ""
        meridian_antitransit = ""

        # Calculate meridian transit and antitransit
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

        return meridian_transit_time, meridian_antitransit_time, meridian_transit, meridian_antitransit

    def _max_altitude(self, meridian_transit_time, planet_label):
        """Calculate max altitude, its time and azimuth

        Args:
            meridian_transit_time (Time): Meridian transit
            planet_label (str): Ephemeris label of the planet

        Returns:
            object_body (SkyCoord): Coordinates of the body
            max_altitude_time (str): Time of max altitude
            max_altitude (degree): Max altitude
            azimuth: Azimuth of max altitude within observation time frame
        """
        max_altitude = 0

        # Meridian transmit during astronomical night
        if (
            self._observation_timeframe["observing_start_time"] < meridian_transit_time
            and self._observation_timeframe["observing_end_time"] > meridian_transit_time
        ):
            # It's within astronomical darkness
            object_body = get_body(planet_label, meridian_transit_time)
            object_altaz = AltAz(obstime=meridian_transit_time, location=self._observer.location)
            body_altaz = object_body.transform_to(object_altaz)
            max_altitude_time = str(
                self._observer.astropy_time_to_datetime(meridian_transit_time).strftime("%m/%d/%Y %H:%M:%S")
            )
            max_altitude = body_altaz.alt
            azimuth = body_altaz.az
        else:
            if meridian_transit_time > self._observation_timeframe["observing_end_time"]:
                object_body = get_body(planet_label, self._observation_timeframe["observing_start_time"])
                object_altaz = AltAz(
                    obstime=self._observation_timeframe["observing_start_time"],
                    location=self._observer.location,
                )
                body_altaz = object_body.transform_to(object_altaz)
                max_altitude_time = str(
                    self._observer.astropy_time_to_datetime(
                        self._observation_timeframe["observing_start_time"]
                    ).strftime("%m/%d/%Y %H:%M:%S")
                )
                if body_altaz.az.is_within_bounds("0d", "180d"):
                    object_body = get_body(planet_label, self._observation_timeframe["observing_end_time"])
                    object_altaz = AltAz(
                        obstime=self._observation_timeframe["observing_end_time"],
                        location=self._observer.location,
                    )
                    body_altaz = object_body.transform_to(object_altaz)
                    max_altitude_time = str(
                        self._observer.astropy_time_to_datetime(
                            self._observation_timeframe["observing_end_time"]
                        ).strftime("%m/%d/%Y %H:%M:%S")
                    )
                max_altitude = body_altaz.alt
                azimuth = body_altaz.az

        return object_body, max_altitude_time, max_altitude, azimuth

    def _visual_magnitude(self, planet_label):
        """Calculates the visual magnitude for the solar system body

        Args:
            planet_label (str): Ephemeris label of the planet

        Returns:
            magnitude (float): The visual magnitude
        """
        t = self._ts.from_astropy(self._observation_timeframe["observing_start_time"])

        astrometric = self._observer_sf.at(t).observe(self._eph[self._eph_map[planet_label]]).apparent()
        magnitude = planetary_magnitude(astrometric)

        return magnitude
