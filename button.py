"""Buton „Trimite indecșii”: trimite la e-bloc.ro valorile din câmpurile „Index nou”."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EblocConfigEntry
from .entity import ApartmentEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: EblocConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        SubmitIndexesButton(coordinator, key)
        for key, apt in coordinator.data.items()
        if apt.meters
    )


class SubmitIndexesButton(ApartmentEntity, ButtonEntity):
    suffix = "trimite_indecsi"
    _attr_name = "Trimite indecșii"
    _attr_icon = "mdi:send"

    async def async_press(self) -> None:
        drafts = dict(self.coordinator.drafts.get(self._key, {}))
        await self.coordinator.async_submit(self._key, drafts)
