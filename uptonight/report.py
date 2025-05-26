import json
import logging
import queue
import time
from io import BytesIO

from uptonight.const import DEVICE_TYPE_CAMERA, FEATURE_BODIES, FEATURE_COMETS, FEATURE_OBJECTS, FUNCTIONS
from uptonight.mqtthandler import MQTTDeviceHandler, MQTTHandler

_LOGGER = logging.getLogger(__name__)

message_queue = queue.Queue()


class Report:
    """UpTonight Reports"""

    def __init__(
        self,
        observer,
        astronight_from,
        astronight_to,
        sun_moon,
        output_dir,
        current_day,
        filter_ext,
        constraints,
        prefix,
        target_list,
        plot,
    ):
        """Init reports

        Args:
            observer (Observer): The astroplan opbserver
            astronight_from (str): Observation start time
            astronight_to (str): Observation end time
            constraints (dict): Observing contraints
            sun_moon (SunMoon): Sun and Moon helper
            output_dir (str): Output directory
            current_day (Time): Day for calculation
            filter_ext (str): Object filter
            constraints (dict): Constraints
        """
        self._observer = observer
        self._astronight_from = astronight_from
        self._astronight_to = astronight_to
        self._sun_moon = sun_moon
        self._output_dir = output_dir
        self._current_day = current_day
        self._filter_ext = filter_ext
        self._constraints = constraints
        self._prefix = prefix
        self._target_list = target_list
        self._plot = plot

        return None

    def save_mqtt(self, mqtt_service, uptonight_result, result_type, output_datestamp):
        """Save report as mqtt

        Args:
            uptonight_result (Table): Results
            result_type (str): Type
        """
        target_list = self._target_list.split("/")[1]
        self._mqtt_handler = MQTTHandler(mqtt_service)
        mqtt_client = None
        while not self._mqtt_handler.connected():
            try:
                mqtt_client = self._mqtt_handler.connect()
            except ConnectionRefusedError as cre:
                _LOGGER.error(f"MQTT Connection error: {cre}")
                time.sleep(3)

        if result_type == FEATURE_OBJECTS:
            uptonight_result.remove_columns(
                [
                    "hmsdms",
                    "right ascension",
                    "declination",
                    "altitude",
                    "azimuth",
                ]
            )
        if result_type == FEATURE_BODIES:
            uptonight_result.remove_columns(
                [
                    "hmsdms",
                    "right ascension",
                    "declination",
                ]
            )
        if result_type == FEATURE_COMETS:
            uptonight_result.remove_columns(
                [
                    "hmsdms",
                    "absolute magnitude",
                ]
            )
        for device in FUNCTIONS:
            mqtt_device = {
                "device_type": device,
                "observatory": f"{self._observer.name.title()}",
                "type": f"{result_type.title()}",
                "catalogue": f"{target_list}",
                "functions": list(FUNCTIONS.get(device)),
            }

            _LOGGER.info(f"Create Home Assistant MQTT configuration for a {result_type}")
            mqtt_device_handler = MQTTDeviceHandler(mqtt_client, message_queue, mqtt_device)
            mqtt_device_handler.create_mqtt_config()

            moon_separation = 0
            if self._constraints["moon_separation_use_illumination"]:
                moon_separation = self._sun_moon.moon_illumination()
            else:
                moon_separation = self._constraints["moon_separation_min"]

            uptonight_table = json.loads(uptonight_result.to_pandas().to_json(orient="records"))
            data = {
                "target_list": target_list,
                "observatory": self._observer.name,
                "site_longitude": round(self._observer.location.lon.value, 4),
                "site_latitude": round(self._observer.location.lat.value, 4),
                "elevation": round(self._observer.location.height.value, 2),
                "astronight_from": self._astronight_from.isoformat(),
                "astronight_to": self._astronight_to.isoformat(),
                "darkness": self._sun_moon.darkness().title(),
                "moon_illumination": round(self._sun_moon.moon_illumination(), 1),
                "altitude_constraint_min": self._constraints["altitude_constraint_min"],
                "altitude_constraint_max": self._constraints["altitude_constraint_max"],
                "airmass_constraint": self._constraints["airmass_constraint"],
                "moon_separation": round(moon_separation, 1),
                "size_constraint_min": self._constraints["size_constraint_min"],
                "size_constraint_max": self._constraints["size_constraint_max"],
                "uptonight_table": uptonight_table,
            }

            message_queue.put(data)

            if device in (DEVICE_TYPE_CAMERA):
                buf = BytesIO()
                self._plot.savefig(buf, format="png")  # You can also use 'jpg', 'svg', etc.

                # Get bytearray
                buf.seek(0)
                plot_bytes = bytearray(buf.read())

                _LOGGER.debug(f"Image size {len(plot_bytes)} bytes")
                data = {
                    "screen": plot_bytes,
                }

                message_queue.put(data)

        mqtt_device_handler.looper()

        mqtt_client.disconnect()

    def save_txt(self, uptonight_result, result_type, output_datestamp):
        """Save report as txt

        Args:
            uptonight_result (Table): Results
            result_type (str): Type
        """
        if result_type != "" and not result_type.endswith("-"):
            result_type += "-"

        if len(uptonight_result) > 0:
            uptonight_result.write(
                f"{self._output_dir}/uptonight-{self._prefix}{result_type}report{self._filter_ext}.txt",
                overwrite=True,
                format="ascii.fixed_width_two_line",
            )
        else:
            with open(
                f"{self._output_dir}/uptonight-{self._prefix}{result_type}report{self._filter_ext}.txt",
                "w",
                encoding="utf-8",
            ) as report:
                report.writelines("")

        with open(
            f"{self._output_dir}/uptonight-{self._prefix}{result_type}report{self._filter_ext}.txt",
            "r",
            encoding="utf-8",
        ) as report:
            contents = report.readlines()

        contents = self._report_add_info(contents)

        if output_datestamp:
            with open(
                f"{self._output_dir}/uptonight-{self._prefix}{result_type}report-{self._current_day}{self._filter_ext}.txt",
                "w",
                encoding="utf-8",
            ) as report:
                report.write(contents)
        with open(
            f"{self._output_dir}/uptonight-{self._prefix}{result_type}report{self._filter_ext}.txt",
            "w",
            encoding="utf-8",
        ) as report:
            report.write(contents)

    def save_json(self, uptonight_result, result_type, output_datestamp):
        """Save report as json

        Args:
            uptonight_result (Table): Results
            result_type (str): Type
        """
        if result_type != "" and not result_type.endswith("-"):
            result_type += "-"

        if output_datestamp:
            uptonight_result.write(
                f"{self._output_dir}/uptonight-{self._prefix}{result_type}report-{self._current_day}.json",
                overwrite=True,
                format="pandas.json",
            )
        uptonight_result.write(
            f"{self._output_dir}/uptonight-{self._prefix}{result_type}report.json",
            overwrite=True,
            format="pandas.json",
        )

    def _report_add_info(self, contents):
        """Add observatory information to report

        Args:
            contents (str): Content

        Returns:
            contents (str): Modified content
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
            f"Observation timespan: {self._astronight_from.strftime("%m/%d %H:%M")} to {self._astronight_to.strftime("%m/%d %H:%M")} in {self._sun_moon.darkness()} darkness",
        )
        contents.insert(11, "\n")
        contents.insert(12, "Moon illumination: {:.0f}%".format(self._sun_moon.moon_illumination()))
        contents.insert(13, "\n")
        contents.insert(
            14,
            f"Contraints: Altitude constraint minimum: {self._constraints['altitude_constraint_min']}°, maximum: {self._constraints['altitude_constraint_max']}°, "
            + f"Airmass constraint: {self._constraints['airmass_constraint']}, Moon separation constraint: {moon_separation:.0f}°, "
            + f"Size constraint minimum: {self._constraints['size_constraint_min']}', maximum: {self._constraints['size_constraint_max']}'",
        )
        contents.insert(15, "\n")
        contents.insert(16, f"Altitude and Azimuth calculated for {self._astronight_from.strftime("%m/%d %H:%M")}")
        contents.insert(17, "\n")
        contents.insert(18, "\n")

        contents = "".join(contents)

        return contents
