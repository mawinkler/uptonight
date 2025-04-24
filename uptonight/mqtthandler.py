import json
import logging
import random
import string
import time
from threading import Thread

import paho.mqtt.client as mqtt
from paho.mqtt import MQTTException

from .const import (
    DEVICE_TYPE_CAMERA,
    DEVICE_TYPE_UPTONIGHT,
    FEATURE_OBJECTS,
    MANUFACTURER,
    SENSOR_DEVICE_CLASS,
    SENSOR_ICON,
    SENSOR_NAME,
    SENSOR_STATE_CLASS,
    SENSOR_TYPE,
    SENSOR_UNIT,
    STATE_OFF,
    STATE_ON,
)

_LOGGER = logging.getLogger(__name__)


class MQTTHandler:
    def __init__(
        self,
        service,
    ) -> None:
        self._mqttclient = None

        self._mqtthost = service.get("host", "localhost")
        self._mqttport = service.get("port", 1883)
        self._mqttuser = service.get("user")
        self._mqttpassword = service.get("password")
        self._mqttclientid = service.get("clientid", "uptonight")

        self._mqttclient = None
        self._mqttthread = None
        self._mqttclientconnected = False

    def connect(self):
        """Connect to mqtt broker and Gardena Smart System"""

        unique_id = "".join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(12))
        # if self._publisher is None:
        proto = mqtt.MQTTv5
        self._mqttclient = mqtt.Client(client_id=f"{self._mqttclientid}-{unique_id}", protocol=proto)
        self._mqttclient.username_pw_set(self._mqttuser, self._mqttpassword)
        self._mqttclient.on_connect = self.on_mqtt_connect
        self._mqttclient.on_disconnect = self.on_mqtt_disconnect
        self._mqttclient.will_set(f"{self._mqttclientid}/connected", "0", 0, True)
        self._mqttthread = Thread(target=self._mqttclient.loop_forever)
        self._mqttclientconnected = False

        _LOGGER.info(f"Connecting to MQTT broker on {self._mqtthost} at {self._mqttport}")
        self._mqttclient.connect(self._mqtthost, int(self._mqttport))
        self._mqttthread.start()

        # Wait up to 5 seconds for MQTT connection
        for i in range(50):
            if self._mqttclientconnected is True:
                break
            time.sleep(0.1)

        if self._mqttclientconnected is False:
            self.shutdown()

        _LOGGER.info("MQTT broker connected")

        return self._mqttclient

        # tie to mqtt client
        # self._mqttthread.join()

    def connected(self) -> bool:
        return self._mqttclientconnected

    def on_mqtt_connect(self, client, userdata, flags, rc, properties) -> None:
        """Callback when the broker responds to our connection request."""

        self._mqttclientconnected = True

        _LOGGER.info(f"Connected to MQTT broker on {self._mqtthost} at {self._mqttport}")

        if flags.get("session_present"):
            _LOGGER.debug("MQTT session present")

        if rc == 0:
            _LOGGER.debug("MQTT success connect")
            client.publish(
                f"{self._mqttclientid}/lwt",
                "ON",
            )
        else:
            _LOGGER.error(f"MQTT connect not successful. Return code: {rc}")

    def disconnect(self):
        self._mqttclient.disconnect()

    def on_mqtt_disconnect(self, client, userdata, rc, properties) -> None:
        """Callback when the client disconnects from the broker."""

        self._mqttclientconnected = False

        # client.publish(
        #     f"{self._mqttclientid}/lwt",
        #     "OFF",
        # )
        _LOGGER.info(f"Disconnected from MQTT broker on {self._mqtthost} at {self._mqttport}")


class MQTTDeviceHandler:
    def __init__(
        self,
        mqttclient,
        message_queue,
        mqttdevice,
    ) -> None:
        self._mqttclient = mqttclient
        self._message_queue = message_queue

        self._observatory = mqttdevice["observatory"]
        self._type = mqttdevice["type"]
        self._catalogue = mqttdevice["catalogue"]
        self._device_type = mqttdevice["device_type"]

        self._device_functions = mqttdevice["functions"]

    def create_mqtt_config(self) -> None:
        """Creates configuration topics within the homeassistant topics.

        Returns:
            True if thread is alive
        """

        _LOGGER.debug(f"Creating MQTT Config for a {self._device_type}")

        _observatory = self._observatory.lower().replace(" ", "_")
        _type = self._type.lower().replace(" ", "_")
        _catalogue = self._catalogue.lower().replace(" ", "_")
        if self._device_type in (DEVICE_TYPE_UPTONIGHT):
            for function in self._device_functions:
                root_topic = "homeassistant/" + function[SENSOR_TYPE] + "/"
                topic = "uptonight/" + _observatory + "_" + _type + "_" + _catalogue + "/"
                config = {
                    "name": self._catalogue,
                    "state_topic": topic + "state",
                    "json_attributes_topic": topic + "attributes",
                    "state_class": function[SENSOR_STATE_CLASS],
                    "device_class": function[SENSOR_DEVICE_CLASS],
                    "icon": function[SENSOR_ICON],
                    "availability_topic": topic + "lwt",
                    "payload_available": "ON",
                    "payload_not_available": "OFF",
                    "payload_on": STATE_ON,
                    "payload_off": STATE_OFF,
                    "unique_id": self._device_type + "_" + _observatory + "_" + _type + "_" + _catalogue,
                    "value_template": "{{ value_json." + _catalogue + " }}",
                    "device": {
                        "identifiers": [self._type],
                        "name": f"UpTonight {self._observatory} {self._type}",
                        "model": f"{self._observatory} {self._type}",
                        "manufacturer": MANUFACTURER,
                    },
                }
                if function[SENSOR_UNIT] != "" and function[SENSOR_UNIT] is not None:
                    config["unit_of_measurement"] = function[SENSOR_UNIT]

                self._mqttclient.publish(root_topic + topic + "config", json.dumps(config), qos=0, retain=True)

            _LOGGER.debug(f"Published MQTT Config for a {self._device_type}")

        if self._device_type in (DEVICE_TYPE_CAMERA) and _type == FEATURE_OBJECTS:
            # If the device is a camera we create a camera entity configuration
            root_topic = "homeassistant/" + "camera" + "/"
            topic = "uptonight/" + _observatory + "_" + _type + "_" + _catalogue + "/"
            config = {
                "name": f"{self._catalogue} {self._device_functions[0][SENSOR_NAME]}",
                "topic": topic + "screen",
                "availability_topic": topic + "lwt",
                "payload_available": "ON",
                "payload_not_available": "OFF",
                "unique_id": self._device_type + "_" + _observatory + "_" + _type + "_" + _catalogue,
                "device": {
                    "identifiers": [self._type],
                    "name": f"UpTonight {self._observatory} {self._type}",
                    "model": f"{self._observatory} {self._type}",
                    "manufacturer": MANUFACTURER,
                },
            }
            self._mqttclient.publish(root_topic + topic + "config", json.dumps(config), qos=0, retain=True)
            _LOGGER.debug("Published MQTT Camera Config for a %s", self._device_type)

    def publish_device(self, message) -> None:
        """Publish device to mqtt, handle passage if device is mower"""

        _observatory = self._observatory.lower().replace(" ", "_")
        _type = self._type.lower().replace(" ", "_")
        _catalogue = self._catalogue.lower().replace(" ", "_")

        topic = "uptonight/" + _observatory + "_" + _type + "_" + _catalogue + "/"

        try:
            self._mqttclient.publish(topic + "lwt", "ON")
            if message.get("screen", None) is None:
                state = {
                    _catalogue: len(message.get("uptonight_table")),
                }
                attributes = {
                    "observatory": message.get("observatory"),
                    "site_longitude": message.get("site_longitude"),
                    "site_latitude": message.get("site_latitude"),
                    "elevation": message.get("elevation"),
                    "astronight_from": message.get("astronight_from"),
                    "astronight_to": message.get("astronight_to"),
                    "darkness": message.get("darkness"),
                    "moon_illumination": message.get("moon_illumination"),
                    "altitude_constraint_min": message.get("altitude_constraint_min"),
                    "altitude_constraint_max": message.get("altitude_constraint_max"),
                    "airmass_constraint": message.get("airmass_constraint"),
                    "moon_separation": message.get("moon_separation"),
                    "size_constraint_min": message.get("size_constraint_min"),
                    "size_constraint_max": message.get("size_constraint_max"),
                    _type: message.get("uptonight_table"),
                }

                response = self._mqttclient.publish(topic + "state", json.dumps(state))
                response = self._mqttclient.publish(topic + "attributes", json.dumps(attributes))

            if message.get("screen", None) is not None:
                response = self._mqttclient.publish(topic + "screen", message.get("screen", None))
        except MQTTException as mqttex:
            self._mqttclient.publish(topic + "lwt", "OFF")
            _LOGGER.error(f"{self._type}: Not connected")
            raise mqttex

        return response

    def looper(self):
        """Send a MQTT message one by one"""

        while not self._message_queue.empty():
            try:
                if not self._message_queue.empty():
                    message = self._message_queue.get()
                    if message:
                        response = self.publish_device(message)
                        # _LOGGER.debug(
                        #     f"MQTT publish: {message}, Length: {self._message_queue.qsize()}",
                        # )
                        if response[0]:
                            _LOGGER.warning("MQTT failure: %s", response[0])
                time.sleep(0.1)
            except MQTTException as mqttex:
                _LOGGER.error(f"Error sending MQTT message: {mqttex}")
                return
