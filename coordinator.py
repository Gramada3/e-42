"""Coordonator care actualizează periodic datele e-bloc.ro."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import Apartment, EblocAuthError, EblocClient, EblocError
from .const import CONF_SCAN_HOURS, DEFAULT_SCAN_HOURS, DOMAIN, INDEX_MISSING, INDEX_SCALE

_LOGGER = logging.getLogger(__name__)


def _scaled(raw) -> float | None:
    """Index brut din API (× 1000) → valoare reală; None dacă lipsește."""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return None if value == INDEX_MISSING else round(value / INDEX_SCALE, 3)


class EblocCoordinator(DataUpdateCoordinator[dict[str, Apartment]]):
    """Ține în memorie ultima citire pentru toate apartamentele."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: EblocClient) -> None:
        hours = entry.options.get(CONF_SCAN_HOURS, DEFAULT_SCAN_HOURS)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(hours=hours),
        )
        self.client = client
        # Indecși introduși în câmpurile „Index nou”, netrimiși încă:
        # {cheie_apartament: {id_contor: valoare}}
        self.drafts: dict[str, dict[str, float]] = {}

    def meter(self, key: str, meter_id: str) -> dict | None:
        apt = (self.data or {}).get(key)
        if not apt:
            return None
        return next((m for m in apt.meters if str(m.get("id_contor")) == meter_id), None)

    async def async_submit(self, key: str, values: dict[str, float]) -> None:
        """Validează și trimite indecșii unui apartament, apoi reîmprospătează."""
        apt = (self.data or {}).get(key)
        if apt is None:
            raise ServiceValidationError("Apartamentul nu mai există în contul e-bloc.ro.")
        if not values:
            raise ServiceValidationError(
                "Nu ai introdus niciun index nou. Completează câmpurile „Index nou” mai întâi."
            )

        info = apt.assoc_info
        if str(info.get("can_edit_index", "0")) != "1":
            period = ""
            if info.get("indecsi_start") and info.get("indecsi_end"):
                period = f" Perioada de citire: {info['indecsi_start']} – {info['indecsi_end']}."
            raise ServiceValidationError(
                f"Asociația nu acceptă indecși în acest moment.{period}"
            )

        readings = []
        for meter_id, value in values.items():
            meter = self.meter(key, meter_id)
            if meter is None:
                raise ServiceValidationError(f"Contorul {meter_id} nu există la {apt.label}.")
            name = meter.get("titlu") or f"contor {meter_id}"
            if value < 0:
                raise ServiceValidationError(f"Indexul pentru {name} nu poate fi negativ.")
            old = _scaled(meter.get("index_vechi"))
            if old is not None and value < old:
                raise ServiceValidationError(
                    f"Indexul nou pentru {name} ({value}) e mai mic decât cel vechi ({old})."
                )
            readings.append(
                {"assoc_id": apt.assoc_id, "ap_id": apt.ap_id, "meter_id": meter_id, "value": value}
            )

        try:
            await self.client.submit_indexes(readings)
        except EblocAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except EblocError as err:
            raise HomeAssistantError(f"Trimiterea a eșuat: {err}") from err

        _LOGGER.info("Indecși trimiși pentru %s: %s", apt.label, values)
        drafts = self.drafts.get(key, {})
        for meter_id in values:
            drafts.pop(meter_id, None)
        await self.async_request_refresh()

    async def _async_update_data(self) -> dict[str, Apartment]:
        try:
            return await self.client.fetch_all()
        except EblocAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except EblocError as err:
            raise UpdateFailed(str(err)) from err
