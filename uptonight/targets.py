import logging
import os

import numpy as np
import yaml
from astroplan import (
    FixedTarget,
    observability_table,
)
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.table import Table

# from astroquery.simbad import Simbad

_LOGGER = logging.getLogger(__name__)


class Targets:
    """UpTonight Target Generation"""

    def __init__(
        self,
        target_list=None,
        custom_targets=[],
        target=None,
    ):
        self._target_list = target_list
        self._custom_targets = custom_targets
        self._input_targets, self._fixed_targets = self._create_target_list(target)
        self._targets_table = self._create_uptonight_targets_table()
        self._bodies_table = self._create_uptonight_bodies_table()
        self._comets_table = self._create_uptonight_comets_table()

        return None

    def input_targets(self):
        if self._input_targets is not None:
            return self._input_targets
        return None

    def fixed_targets(self):
        if self._fixed_targets is not None:
            return self._fixed_targets
        return None

    def targets_table(self):
        if self._targets_table is not None:
            return self._targets_table
        return None

    def bodies_table(self):
        if self._bodies_table is not None:
            return self._bodies_table
        return None

    def comets_table(self):
        if self._comets_table is not None:
            return self._comets_table
        return None

    def _create_target_list(self, target=None):
        """Creates a table and list of targets in scope for the calculations.

        The method reads the provided csv file containing the Gary Imm objects and adds custom
        targets defined in the const.py file. The table is used as a lookup table to populate the
        result table. Iteration is done via the FixedTarget list.
        For visibility, Polaris is appended lastly.

        Args:
            target (str, optional): Single target mode

        Returns:
            (Table): Targets to calculate
            (List): Targets to calculate
        """

        input_targets = None

        # Default to GaryImm
        if self._target_list is None:
            self._target_list = "targets/GaryImm"

        if os.path.isfile(f"{self._target_list}.yaml"):
            with open(f"{self._target_list}.yaml", "r", encoding="utf-8") as ymlfile:
                targets = yaml.load(ymlfile, Loader=yaml.FullLoader)
                input_targets = Table(
                    names=(
                        "name",
                        "description",
                        "type",
                        "constellation",
                        "size",
                        "ra",
                        "dec",
                        "mag",
                    ),
                    dtype=(
                        str,
                        str,
                        str,
                        str,
                        np.float16,
                        str,
                        str,
                        np.float16,
                    ),
                )
                for input_target in targets:
                    if target is None or target == input_target.get("name"):
                        name = input_target.get("name")
                        desc = input_target.get("description")
                        type = input_target.get("type")
                        constellation = input_target.get("constellation")
                        ra = input_target.get("ra")
                        dec = input_target.get("dec")
                        size = input_target.get("size")
                        mag = input_target.get("mag")
                        if mag == -9999:
                            mag = 0.0
                        input_targets.add_row(
                            [
                                name,
                                desc,
                                type,
                                constellation,
                                float(size),
                                ra,
                                dec,
                                float(mag),
                            ]
                        )
        else:
            input_targets = Table.read(f"{self._target_list}.csv", format="ascii.csv")

        # Adding visual magnitude to target csvs without magnitude by
        # querying Simbad
        # Simbad.add_votable_fields('flux(V)')
        # Simbad.ROW_LIMIT = 1
        # input_targets['mag'] = input_targets['mag'].astype(float)
        # input_targets["mag"].info.format = ".1f"

        # for index, name in enumerate(input_targets['name']):
        #     simbad = Simbad.query_object(name)
        #     if simbad:
        #         if simbad[0]['FLUX_V'] != '--':
        #             simbad_mag = float(simbad[0]['FLUX_V'])
        #             print(f"name: {name}, mag: {simbad_mag}")
        #             input_targets[index]['mag'] = simbad_mag

        # Create astroplan.FixedTarget objects for each one in the table
        # Used to calculate the fraction of time observable
        fixed_targets = [
            FixedTarget(
                coord=SkyCoord(f"{ra} {dec}", unit=(u.hourangle, u.deg)),
                name=name,
            )
            for name, common_name, type, constellation, size, ra, dec, mag in input_targets
        ]

        # Add custom targets
        for custom_target in self._custom_targets:
            if target is None or target == custom_target.get("name"):
                name = custom_target.get("name")
                desc = custom_target.get("description")
                ra = custom_target.get("ra")
                dec = custom_target.get("dec")
                size = custom_target.get("size", 0)
                mag = custom_target.get("mag", 0)
                input_targets.add_row(
                    [
                        name,
                        desc,
                        custom_target.get("type"),
                        custom_target.get("constellation"),
                        size,
                        ra,
                        dec,
                        mag,
                    ]
                )
                fixed_targets.append(
                    FixedTarget(coord=SkyCoord(f"{ra} {dec}", unit=(u.hourangle, u.deg)), name=name),
                )

        # Lastly we add Polaris
        input_targets.add_row(
            [
                "Polaris",
                "North star",
                "Star",
                "Ursa Minor",
                0.0,
                "02 31 49",
                "89 15 51",
                1.98,
            ]
        )
        # We need to add Polaris here as well to have the same number of objects as in the input_targets table
        fixed_targets.append(FixedTarget.from_name("Polaris"))

        # input_targets.write(f"{self._target_list}-mag.csv", format="ascii.csv")

        return input_targets, fixed_targets

    def input_targets_add_foto(
        self, constraints, observability_constraints, observation_timeframe, observer, fixed_targets
    ):
        """Add fraction of time observable to target list

        Args:
            constraints (dict): Configured constraints
            observability_constraints (list): Altitude, airmass and moon separation constraint
            observation_timeframe (dict): Start and end times, time range and current day
            observer (Observer): Our observer
            fixed_targets (List): Targets to calculate

        Returns:
            input_targets (Table): Targets to calculate including foto
        """

        observability_targets = observability_table(
            observability_constraints,
            observer,
            fixed_targets,
            time_range=observation_timeframe["time_range"],
        )
        observability_targets["fraction of time observable"].info.format = ".3f"
        # self._fixed_targets = None  # We don't need this list anymore

        # Merge fraction of time observable with input_targets and reverse sort the table
        self._input_targets["fraction of time observable"] = observability_targets["fraction of time observable"]
        self._input_targets.sort("fraction of time observable")
        self._input_targets.reverse()

        return self._input_targets

    def _create_uptonight_targets_table(self):
        """Creates the result table for deep sky objects

        Rows will be added while objects are calculated

        Returns:
            uptonight_targets (Table): Result table
        """
        uptonight_targets = Table(
            names=(
                "id",
                "target name",
                "hmsdms",
                "right ascension",
                "declination",
                "altitude",
                "azimuth",
                "meridian transit",
                "antimeridian transit",
                "type",
                "constellation",
                "size",
                "mag",
                "foto",
            ),
            dtype=(
                str,
                str,
                str,
                np.float16,
                np.float16,
                np.float16,
                np.float16,
                str,
                str,
                str,
                str,
                np.float16,
                np.float16,
                np.float16,
            ),
        )
        uptonight_targets["right ascension"].info.format = ".1f"
        uptonight_targets["declination"].info.format = ".1f"
        uptonight_targets["altitude"].info.format = ".1f"
        uptonight_targets["azimuth"].info.format = ".1f"
        uptonight_targets["size"].info.format = ".1f"
        uptonight_targets["mag"].info.format = ".1f"
        uptonight_targets["foto"].info.format = ".1f"

        return uptonight_targets

    def _create_uptonight_bodies_table(self):
        """Creates the result table for solar system bodies

        Rows will be added while objects are calculated

        Returns:
            uptonight_bodies (Table): Result table
        """
        uptonight_bodies = Table(
            names=(
                "target name",
                "hmsdms",
                "right ascension",
                "declination",
                "max altitude",
                "visual magnitude",
                "azimuth",
                "max altitude time",
                "meridian transit",
                "antimeridian transit",
                "type",
                "foto",
            ),
            dtype=(
                str,
                str,
                np.float16,
                np.float16,
                np.float16,
                np.float16,
                np.float16,
                str,
                str,
                str,
                str,
                np.float16,
            ),
        )
        uptonight_bodies["right ascension"].info.format = ".1f"
        uptonight_bodies["declination"].info.format = ".1f"
        uptonight_bodies["max altitude"].info.format = ".1f"
        uptonight_bodies["visual magnitude"].info.format = ".1f"
        uptonight_bodies["azimuth"].info.format = ".1f"
        uptonight_bodies["foto"].info.format = ".1f"

        return uptonight_bodies

    def _create_uptonight_comets_table(self):
        """Creates the result table for comets

        Rows will be added while objects are calculated

        Returns:
            uptonight_comets (Table): Result table
        """
        uptonight_comets = Table(
            names=(
                "target name",
                "hmsdms",
                "distance earth au",
                "distance sun au",
                "absolute magnitude",  # magnitude_g
                "visual magnitude",
                "altitude",
                "azimuth",
                "rise time",
                "set time",
            ),
            dtype=(
                str,
                str,
                np.float16,
                np.float16,
                np.float16,
                np.float16,
                np.float16,
                np.float16,
                str,
                str,
            ),
        )
        uptonight_comets["distance earth au"].info.format = ".3f"
        uptonight_comets["distance sun au"].info.format = ".3f"
        uptonight_comets["absolute magnitude"].info.format = ".2f"
        uptonight_comets["visual magnitude"].info.format = ".2f"
        uptonight_comets["azimuth"].info.format = ".1f"
        uptonight_comets["azimuth"].info.format = ".1f"

        return uptonight_comets
