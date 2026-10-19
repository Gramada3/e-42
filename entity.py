"""Bază comună pentru entități: un dispozitiv per apartament."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Apartment
from .const import DOMAIN, NAME
from .coordinator import EblocCoordinator


class ApartmentEntity(CoordinatorEntity[EblocCoordinator]):
    _attr_has_entity_name = True
    _attr_attribution = "Date de la e-bloc.ro"
    suffix = ""

    def __init__(self, coordinator: EblocCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        apt = coordinator.data[key]
        self._attr_unique_id = f"{DOMAIN}_{key}_{self.suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, key)},
            name=f"{apt.assoc_name} – {apt.label}",
            manufacturer=NAME,
            model="Apartament",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www.e-bloc.ro",
        )

    @property
    def apt(self) -> Apartment | None:
        return (self.coordinator.data or {}).get(self._key)

    @property
    def available(self) -> bool:
        return super().available and self.apt is not None
