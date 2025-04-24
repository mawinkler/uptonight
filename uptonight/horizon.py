import logging

from astroplan import (
    FixedTarget,
)
from astroplan.plots import plot_sky
from astropy import units as u
from astropy.coordinates import AltAz, EarthLocation, SkyCoord
from astropy.time import Time

_LOGGER = logging.getLogger(__name__)


class UpTonightHorizon:
    """UpTonight Horizon"""

    def __init__(
        self,
        observer,
        observation_timeframe,
        constraints,
        colors,
    ):
        """Init horizon

        Args:
            observer (Observer): The astroplan opbserver
            observation_timeframe (dict): Oberserving time ranges
            constraints (dict): Observing contraints
            colors (dict): Color table
        """
        self._observer = observer
        self._observer_location = EarthLocation.from_geodetic(
            observer.longitude,
            observer.latitude,
            observer.elevation,
        )
        self._observation_timeframe = observation_timeframe
        self._constraints = constraints
        self._colors = colors

        return None

    def horizon(self, horizon, ax):
        """
        Adds the horizon to the plot.

        Args:
            horizon (list): List of alt/az pairs defining the horizon

        Returns:
            ax (Axes): An Axes object (ax) with a map of the sky.
        """

        _LOGGER.info("Creating plot of horizon")

        observation_time = self._observation_timeframe["observing_start_time"]

        for horizon_direction in horizon:
            # Perform the conversion
            ra_deg, dec_deg = self._altaz_to_radec(
                horizon_direction.get("alt"),
                horizon_direction.get("az"),
                self._observation_timeframe["observing_start_time"],
                self._observer_location,
            )

            # Convert RA from degrees to hours, minutes, seconds
            ra = SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg, frame="icrs").ra.to_string(
                unit=u.hour, sep=":", precision=2
            )
            dec = SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg, frame="icrs").dec.to_string(sep=":", precision=2)

            target = FixedTarget(
                coord=SkyCoord(
                    f"{ra} {dec}",
                    unit=(u.hourangle, u.deg),
                ),
                name="_horizon",
            )
            ax = plot_sky(
                target,
                self._observer,
                self._observation_timeframe["observing_start_time"],
                style_kwargs=dict(color=self._colors["ticks"], label=target.name, marker="o", s=10),
                north_to_east_ccw=self._constraints["north_to_east_ccw"],
                ax=ax,
            )

        return ax

    def _altaz_to_radec(self, alt, az, time_str, observer_location):
        """
        Convert altitude-azimuth coordinates to right ascension and declination.

        Args:
            alt (float): Altitude in degrees.
            az (float): Azimuth in degrees.
            time_str (str): Observation time in ISO format (e.g., '2024-04-01T22:30:00').
            observer_location (EarthLocation): Observer's Earth location.

        Returns:
            tuple: (RA in degrees, Dec in degrees).
        """

        # Define the observation time
        time = Time(time_str)

        # Create AltAz frame for the given time and location
        object_altaz = AltAz(obstime=time, location=observer_location)

        # Create a SkyCoord object in AltAz frame
        altaz = SkyCoord(alt=alt * u.deg, az=az * u.deg, frame=object_altaz)

        # Transform to ICRS (equatorial) frame to get RA and Dec
        radec = altaz.transform_to("icrs")

        return radec.ra.degree, radec.dec.degree
