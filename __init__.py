"""Integrare Home Assistant pentru contul tău e-bloc.ro."""

from __future__ import annotations

import re

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import EblocClient
from .const import DOMAIN
from .coordinator import EblocCoordinator

PLATFORMS = [Platform.SENSOR, Platform.NUMBER, Platform.BUTTON]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_SUBMIT_INDEX = "trimite_index"
ATTR_VALUE = "valoare"
SUBMIT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_VALUE): vol.All(vol.Coerce(float), vol.Range(min=0)),
    }
)
# unique_id-ul senzorilor de index și al câmpurilor „Index nou”
_METER_UID = re.compile(rf"^{DOMAIN}_(?P<key>.+)_(?:contor|index_nou)_(?P<meter>[^_]+)$")

type EblocConfigEntry = ConfigEntry[EblocCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async def submit_index(call: ServiceCall) -> None:
        entity_id = call.data[ATTR_ENTITY_ID]
        entry_reg = er.async_get(hass).async_get(entity_id)
        match = _METER_UID.match(entry_reg.unique_id) if entry_reg else None
        if not entry_reg or entry_reg.platform != DOMAIN or not match:
            raise ServiceValidationError(
                f"{entity_id} nu este un contor din integrarea E-bloc (personal)."
            )
        entry = hass.config_entries.async_get_entry(entry_reg.config_entry_id)
        if entry is None or entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError("Integrarea E-bloc (personal) nu este încărcată.")
        coordinator: EblocCoordinator = entry.runtime_data
        await coordinator.async_submit(
            match["key"], {match["meter"]: round(call.data[ATTR_VALUE], 3)}
        )

    hass.services.async_register(DOMAIN, SERVICE_SUBMIT_INDEX, submit_index, schema=SUBMIT_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: EblocConfigEntry) -> bool:
    client = EblocClient(
        async_get_clientsession(hass), entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD]
    )
    coordinator = EblocCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_reload_on_options))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EblocConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _reload_on_options(hass: HomeAssistant, entry: EblocConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
