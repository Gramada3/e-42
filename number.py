"""Câmpuri „Index nou” per contor. Valoarea rămâne locală până la apăsarea butonului."""

from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EblocConfigEntry
from .coordinator import EblocCoordinator, _scaled
from .entity import ApartmentEntity

UNITS = {
    "1": UnitOfVolume.CUBIC_METERS,
    "2": UnitOfVolume.CUBIC_METERS,
    "3": UnitOfVolume.CUBIC_METERS,
    "4": UnitOfEnergy.KILO_WATT_HOUR,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: EblocConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        NewIndexNumber(coordinator, key, str(m["id_contor"]))
        for key, apt in coordinator.data.items()
        for m in apt.meters
        if m.get("id_contor") is not None
    )


class NewIndexNumber(ApartmentEntity, NumberEntity):
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0
    _attr_native_max_value = 9_999_999
    _attr_native_step = 0.001
    _attr_icon = "mdi:counter"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: EblocCoordinator, key: str, meter_id: str) -> None:
        self._meter_id = meter_id
        self.suffix = f"index_nou_{meter_id}"
        super().__init__(coordinator, key)
        meter = coordinator.meter(key, meter_id) or {}
        self._attr_name = f"Index nou {meter.get('titlu') or 'contor ' + meter_id}"
        self._attr_native_unit_of_measurement = UNITS.get(str(meter.get("tip", "")))

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.meter(self._key, self._meter_id) is not None

    @property
    def native_value(self) -> float | None:
        return self.coordinator.drafts.get(self._key, {}).get(self._meter_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        meter = self.coordinator.meter(self._key, self._meter_id) or {}
        return {
            "index_vechi": _scaled(meter.get("index_vechi")),
            "index_transmis": _scaled(meter.get("index_nou")),
            "netrimis": self.native_value is not None,
        }

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.drafts.setdefault(self._key, {})[self._meter_id] = round(value, 3)
        self.async_write_ha_state()
