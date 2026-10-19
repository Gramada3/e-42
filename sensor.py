"""Senzori pentru fiecare apartament: sumă de plată, scadență, plăți, indecși."""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EblocConfigEntry
from .api import Apartment
from .const import INDEX_MISSING, INDEX_SCALE, METER_TYPES, MONEY_SCALE
from .coordinator import EblocCoordinator
from .entity import ApartmentEntity

CURRENCY = "RON"


def _money(raw: Any) -> float | None:
    try:
        return round(int(raw) / MONEY_SCALE, 2)
    except (TypeError, ValueError):
        return None


def _date(raw: Any) -> date | None:
    try:
        return date.fromisoformat(str(raw)[:10])
    except (TypeError, ValueError):
        return None


def _index(raw: Any) -> float | None:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    if value == INDEX_MISSING:
        return None
    return round(value / INDEX_SCALE, 3)


async def async_setup_entry(
    hass: HomeAssistant, entry: EblocConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    for key, apt in coordinator.data.items():
        entities += [
            AmountDueSensor(coordinator, key),
            DueDateSensor(coordinator, key),
            BillingMonthSensor(coordinator, key),
            LastPaymentSensor(coordinator, key),
        ]
        entities += [
            MeterSensor(coordinator, key, str(m.get("id_contor")))
            for m in apt.meters
            if m.get("id_contor") is not None
        ]
    async_add_entities(entities)


class ApartmentSensor(ApartmentEntity, SensorEntity):
    """Senzor legat de un apartament."""


class AmountDueSensor(ApartmentSensor):
    suffix = "de_plata"
    _attr_name = "De plată"
    _attr_icon = "mdi:cash-clock"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = CURRENCY
    _attr_suggested_display_precision = 2

    @property
    def native_value(self) -> float | None:
        return _money(self.apt.home.get("total_plata")) if self.apt else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.apt:
            return {}
        home = self.apt.home
        return {
            "cod_client": home.get("cod_client"),
            "proprietar": home.get("nume"),
            "nr_persoane": home.get("nr_pers"),
        }


class DueDateSensor(ApartmentSensor):
    suffix = "scadenta"
    _attr_name = "Scadență"
    _attr_icon = "mdi:calendar-alert"
    _attr_device_class = SensorDeviceClass.DATE

    @property
    def native_value(self) -> date | None:
        return _date(self.apt.assoc_info.get("data_scadenta")) if self.apt else None


class BillingMonthSensor(ApartmentSensor):
    suffix = "luna"
    _attr_name = "Luna afișată"
    _attr_icon = "mdi:calendar-month"

    @property
    def native_value(self) -> str | None:
        return (self.apt.assoc_info.get("luna") or None) if self.apt else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.apt:
            return {}
        info = self.apt.assoc_info
        return {
            "perioada_indecsi_start": info.get("indecsi_start"),
            "perioada_indecsi_sfarsit": info.get("indecsi_end"),
            "se_pot_trimite_indecsi": str(info.get("can_edit_index", "0")) == "1",
        }


class LastPaymentSensor(ApartmentSensor):
    suffix = "ultima_plata"
    _attr_name = "Ultima plată"
    _attr_icon = "mdi:cash-check"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = CURRENCY
    _attr_suggested_display_precision = 2

    def _sorted(self) -> list[dict[str, Any]]:
        if not self.apt:
            return []
        return sorted(self.apt.payments, key=lambda p: str(p.get("data", "")), reverse=True)

    @property
    def native_value(self) -> float | None:
        payments = self._sorted()
        return _money(payments[0].get("suma")) if payments else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        payments = self._sorted()
        if not payments:
            return {}
        return {
            "data": str(payments[0].get("data", ""))[:10],
            "istoric": [
                {"data": str(p.get("data", ""))[:10], "suma": _money(p.get("suma"))}
                for p in payments[:12]
            ],
        }


class MeterSensor(ApartmentSensor):
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 3

    def __init__(self, coordinator: EblocCoordinator, key: str, meter_id: str) -> None:
        self._meter_id = meter_id
        self.suffix = f"contor_{meter_id}"
        super().__init__(coordinator, key)
        meter = self._meter() or {}
        kind = str(meter.get("tip", ""))
        self._attr_name = f"Index {meter.get('titlu') or 'contor ' + meter_id}"
        if kind in ("1", "2"):
            self._attr_device_class = SensorDeviceClass.WATER
            self._attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
            self._attr_icon = "mdi:water" if kind == "1" else "mdi:water-thermometer"
        elif kind == "3":
            self._attr_device_class = SensorDeviceClass.GAS
            self._attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
        elif kind == "4":
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        else:
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_icon = "mdi:counter"

    def _meter(self) -> dict[str, Any] | None:
        if not self.apt:
            return None
        return next(
            (m for m in self.apt.meters if str(m.get("id_contor")) == self._meter_id), None
        )

    @property
    def available(self) -> bool:
        return super().available and self._meter() is not None

    @property
    def native_value(self) -> float | None:
        meter = self._meter() or {}
        new = _index(meter.get("index_nou"))
        return new if new is not None else _index(meter.get("index_vechi"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        meter = self._meter() or {}
        return {
            "id_contor": self._meter_id,
            "tip": METER_TYPES.get(str(meter.get("tip", "")), meter.get("tip")),
            "index_vechi": _index(meter.get("index_vechi")),
            "index_nou": _index(meter.get("index_nou")),
            "luna": meter.get("luna"),
        }
