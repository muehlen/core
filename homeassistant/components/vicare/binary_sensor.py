"""Viessmann ViCare sensor device."""
from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
import logging

from PyViCare.PyViCareUtils import (
    PyViCareInvalidDataError,
    PyViCareNotSupportedFeatureError,
    PyViCareRateLimitError,
)
import requests

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ViCareRequiredKeysMixin
from .const import (
    DOMAIN,
    VICARE_API,
    VICARE_CIRCUITS,
    VICARE_DEVICE_CONFIG,
    VICARE_NAME,
)

_LOGGER = logging.getLogger(__name__)

SENSOR_CIRCULATION_PUMP_ACTIVE = "circulationpump_active"
SENSOR_BURNER_ACTIVE = "burner_active"
SENSOR_CHARGING_ACTIVE = "charging_active"
SENSOR_COMPRESSOR_ACTIVE = "compressor_active"
SENSOR_SOLAR_PUMP_ACTIVE = "solar_pump_active"


@dataclass
class ViCareBinarySensorEntityDescription(
    BinarySensorEntityDescription, ViCareRequiredKeysMixin
):
    """Describes ViCare binary sensor entity."""


CIRCUIT_SENSORS: tuple[ViCareBinarySensorEntityDescription, ...] = (
    ViCareBinarySensorEntityDescription(
        key=SENSOR_CIRCULATION_PUMP_ACTIVE,
        name="Circulation pump active",
        device_class=BinarySensorDeviceClass.POWER,
        value_getter=lambda api: api.getCirculationPumpActive(),
    ),
)

BURNER_SENSORS: tuple[ViCareBinarySensorEntityDescription, ...] = (
    ViCareBinarySensorEntityDescription(
        key=SENSOR_BURNER_ACTIVE,
        name="Burner active",
        device_class=BinarySensorDeviceClass.POWER,
        value_getter=lambda api: api.getActive(),
    ),
)

COMPRESSOR_SENSORS: tuple[ViCareBinarySensorEntityDescription, ...] = (
    ViCareBinarySensorEntityDescription(
        key=SENSOR_COMPRESSOR_ACTIVE,
        name="Compressor active",
        device_class=BinarySensorDeviceClass.POWER,
        value_getter=lambda api: api.getActive(),
    ),
)

GLOBAL_SENSORS: tuple[ViCareBinarySensorEntityDescription, ...] = (
    ViCareBinarySensorEntityDescription(
        key=SENSOR_SOLAR_PUMP_ACTIVE,
        name="Solar pump active",
        device_class=BinarySensorDeviceClass.POWER,
        value_getter=lambda api: api.getSolarPumpActive(),
    ),
    ViCareBinarySensorEntityDescription(
        key=SENSOR_CHARGING_ACTIVE,
        name="Domestic Hot Water Charging active",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_getter=lambda api: api.getDomesticHotWaterChargingActive(),
    ),
)


def _build_entity(name, vicare_api, device_config, sensor):
    """Create a ViCare binary sensor entity."""
    try:
        sensor.value_getter(vicare_api)
        _LOGGER.debug("Found entity %s", name)
    except PyViCareNotSupportedFeatureError:
        _LOGGER.info("Feature not supported %s", name)
        return None
    except AttributeError:
        _LOGGER.debug("Attribute Error %s", name)
        return None

    return ViCareBinarySensor(
        name,
        vicare_api,
        device_config,
        sensor,
    )


async def _entities_from_descriptions(
    hass, name, entities, sensor_descriptions, iterables, config_entry
):
    """Create entities from descriptions and list of burners/circuits."""
    for description in sensor_descriptions:
        for current in iterables:
            suffix = ""
            if len(iterables) > 1:
                suffix = f" {current.id}"
            entity = await hass.async_add_executor_job(
                _build_entity,
                f"{name} {description.name}{suffix}",
                current,
                hass.data[DOMAIN][config_entry.entry_id][VICARE_DEVICE_CONFIG],
                description,
            )
            if entity is not None:
                entities.append(entity)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the ViCare binary sensor devices."""
    name = VICARE_NAME
    api = hass.data[DOMAIN][config_entry.entry_id][VICARE_API]

    entities = []

    for description in GLOBAL_SENSORS:
        entity = await hass.async_add_executor_job(
            _build_entity,
            f"{name} {description.name}",
            api,
            hass.data[DOMAIN][config_entry.entry_id][VICARE_DEVICE_CONFIG],
            description,
        )
        if entity is not None:
            entities.append(entity)

    for description in CIRCUIT_SENSORS:
        for circuit in hass.data[DOMAIN][config_entry.entry_id][VICARE_CIRCUITS]:
            suffix = ""
            if len(hass.data[DOMAIN][config_entry.entry_id][VICARE_CIRCUITS]) > 1:
                suffix = f" {circuit.id}"
            entity = await hass.async_add_executor_job(
                _build_entity,
                f"{name} {description.name}{suffix}",
                circuit,
                hass.data[DOMAIN][config_entry.entry_id][VICARE_DEVICE_CONFIG],
                description,
            )
            if entity is not None:
                entities.append(entity)

    try:
        await _entities_from_descriptions(
            hass, name, entities, BURNER_SENSORS, api.burners, config_entry
        )
    except PyViCareNotSupportedFeatureError:
        _LOGGER.info("No burners found")

    try:
        await _entities_from_descriptions(
            hass, name, entities, COMPRESSOR_SENSORS, api.compressors, config_entry
        )
    except PyViCareNotSupportedFeatureError:
        _LOGGER.info("No compressors found")

    async_add_entities(entities)


class ViCareBinarySensor(BinarySensorEntity):
    """Representation of a ViCare sensor."""

    entity_description: ViCareBinarySensorEntityDescription

    def __init__(
        self, name, api, device_config, description: ViCareBinarySensorEntityDescription
    ):
        """Initialize the sensor."""
        self.entity_description = description
        self._attr_name = name
        self._api = api
        self.entity_description = description
        self._device_config = device_config
        self._state = None

    @property
    def device_info(self):
        """Return device info for this device."""
        return {
            "identifiers": {(DOMAIN, self._device_config.getConfig().serial)},
            "name": self._device_config.getModel(),
            "manufacturer": "Viessmann",
            "model": (DOMAIN, self._device_config.getModel()),
        }

    @property
    def available(self):
        """Return True if entity is available."""
        return self._state is not None

    @property
    def unique_id(self):
        """Return unique ID for this device."""
        tmp_id = (
            f"{self._device_config.getConfig().serial}-{self.entity_description.key}"
        )
        if hasattr(self._api, "id"):
            return f"{tmp_id}-{self._api.id}"
        return tmp_id

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Update state of sensor."""
        try:
            with suppress(PyViCareNotSupportedFeatureError):
                self._state = self.entity_description.value_getter(self._api)
        except requests.exceptions.ConnectionError:
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")
        except PyViCareRateLimitError as limit_exception:
            _LOGGER.error("Vicare API rate limit exceeded: %s", limit_exception)
        except PyViCareInvalidDataError as invalid_data_exception:
            _LOGGER.error("Invalid data from Vicare server: %s", invalid_data_exception)
