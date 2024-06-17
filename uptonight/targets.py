import os
import logging
import numpy as np
import yaml
from astroplan import (
    FixedTarget,
    observability_table,
)
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.table import Table

from uptonight.const import (
    CUSTOM_TARGETS,
)

# from astroquery.simbad import Simbad

_LOGGER = logging.getLogger(__name__)


class Targets:
    """UpTonight Target Generation"""

    def __init__(
        self,
        target_list=None,
    ):
        self._input_targets, self._fixed_targets = self._create_target_list(target_list=target_list)
        self._targets_table = self._create_uptonight_targets_table()

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

    def _create_target_list(self, target_list=None):
        """
        Creates a table and list of targets in scope for the calculations.

        The method reads the provided csv file containing the Gary Imm objects and adds custom
        targets defined in the const.py file. The table is used as a lookup table to populate the
        result table. Iteration is done via the FixedTarget list.
        For visibility, Polaris is appended lastly.

        Parameters
        ----------
        target_list

        Returns
        -------
        astropy.Table, [astroplan.FixedTarget]
            Lookup table, list of targets to calculate
        """

        input_targets = None

        # Default to GaryImm
        if target_list is None:
            target_list = "targets/GaryImm"

        if os.path.isfile(f"{target_list}.yaml"):
            with open(f"{target_list}.yaml", "r", encoding="utf-8") as ymlfile:
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
                for custom_target in targets:
                    name = custom_target.get("name")
                    desc = custom_target.get("description")
                    type = custom_target.get("type")
                    constellation = custom_target.get("constellation")
                    ra = custom_target.get("ra")
                    dec = custom_target.get("dec")
                    size = custom_target.get("size")
                    mag = custom_target.get("mag")
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
            print("csv")
            input_targets = Table.read(f"{target_list}.csv", format="ascii.csv")

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
        for custom_target in CUSTOM_TARGETS:
            name = custom_target.get("name")
            desc = custom_target.get("description")
            ra = custom_target.get("ra")
            dec = custom_target.get("dec")
            size = custom_target.get("size")
            mag = custom_target.get("mag")
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

        # input_targets.write(f"{target_list}-mag.csv", format="ascii.csv")

        return input_targets, fixed_targets

    def input_targets_add_foto(
        self, constraints, observability_constraints, observation_timeframe, observer, fixed_targets
    ):
        """_summary_

        Args:
            constraints (_type_): _description_
            observability_constraints (_type_): _description_
            observation_timeframe (_type_): _description_
            observer (_type_): _description_
            fixed_targets (_type_): _description_

        Returns:
            _type_: _description_
        """

        _LOGGER.debug("Adding fraction of time observable to input targets")
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
        """Creates the result table.

        Rows will be added while objects are calculated

        Parameters
        ----------
        none

        Returns
        -------
        astropy.Table: Result table
        """

        uptonight_targets = Table(
            names=(
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
