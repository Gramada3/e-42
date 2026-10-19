"""Client minimal pentru API-ul aplicației mobile e-bloc.ro."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from .const import (
    API_ROOT,
    APP_INFO,
    APP_KEY,
    INDEX_SCALE,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


class EblocError(Exception):
    """Eroare generică de comunicare."""


class EblocAuthError(EblocError):
    """Email sau parolă greșite."""


def hash_password(password: str) -> str:
    """Aplicația trimite parola ca SHA-512 hex (128 caractere)."""
    return hashlib.sha512(password.encode()).hexdigest().rjust(128, "0")


def password_strength(password: str) -> int:
    """2 = minim 8 caractere cu litere și cifre, altfel 1."""
    strong = (
        len(password) >= 8
        and any(ch.isalpha() for ch in password)
        and any(ch.isdigit() for ch in password)
    )
    return 2 if strong else 1


@dataclass
class Apartment:
    """Un apartament dintr-o asociație."""

    assoc_id: str
    assoc_name: str
    ap_id: str
    label: str
    home: dict[str, Any] = field(default_factory=dict)
    assoc_info: dict[str, Any] = field(default_factory=dict)
    meters: list[dict[str, Any]] = field(default_factory=list)
    payments: list[dict[str, Any]] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.assoc_id}_{self.ap_id}"


class EblocClient:
    """Sesiune e-bloc.ro: login, reautentificare automată și citiri."""

    def __init__(self, session: aiohttp.ClientSession, email: str, password: str) -> None:
        self._http = session
        self._email = email.strip()
        self._pass_hash = hash_password(password)
        self._pass_strength = password_strength(password)
        self._sid: str | None = None
        self.user_id: str | None = None
        self._lock = asyncio.Lock()

    async def _get(self, script: str, **params: Any) -> dict[str, Any]:
        params["debug"] = 0
        try:
            async with self._http.get(
                f"{API_ROOT}/{script}",
                params={k: str(v) for k, v in params.items()},
                headers=REQUEST_HEADERS,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                resp.raise_for_status()
                body = await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            raise EblocError(f"{script}: {err}") from err
        if not isinstance(body, dict):
            raise EblocError(f"{script}: răspuns neașteptat")
        return body

    async def _post(self, script: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            async with self._http.post(
                f"{API_ROOT}/{script}",
                json=payload,
                headers={**REQUEST_HEADERS, "Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                resp.raise_for_status()
                body = await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            raise EblocError(f"{script}: {err}") from err
        if not isinstance(body, dict):
            raise EblocError(f"{script}: răspuns neașteptat")
        return body

    async def submit_indexes(self, readings: list[dict[str, Any]]) -> None:
        """Trimite indecși noi.

        Fiecare element: assoc_id, ap_id, meter_id și value (în unitatea
        contorului, ex. 123.456 m³). API-ul primește valoarea × 1000.
        """
        async with self._lock:
            if not self._sid:
                await self.login()

        def payload() -> dict[str, Any]:
            return {
                "session_id": self._sid,
                "aIndex": [
                    {
                        "id_asoc": int(r["assoc_id"]),
                        "id_ap": int(r["ap_id"]),
                        "id_contor": int(r["meter_id"]),
                        "index_nou": round(float(r["value"]) * INDEX_SCALE),
                        "img_data": "",
                        "img_guid": "",
                    }
                    for r in readings
                ],
            }

        body = await self._post("AppContoareSetIndexes.php", payload())
        if body.get("result") == "ok":
            return
        # Sesiunea poate fi expirată: reautentificare și o singură reîncercare
        async with self._lock:
            await self.login()
        body = await self._post("AppContoareSetIndexes.php", payload())
        if body.get("result") != "ok":
            raise EblocError(
                body.get("message") or f"e-bloc.ro a refuzat indecșii ({body.get('result')})"
            )

    async def login(self) -> None:
        body = await self._get(
            "AppLogin.php",
            key=APP_KEY,
            user=self._email,
            pass_sha=self._pass_hash,
            pass_complexity=self._pass_strength,
            facebook_id="",
            google_id="",
            apple_id="",
            nume_user="",
            prenume_user="",
            facebook_access_token="",
            google_id_token="",
            **APP_INFO,
        )
        if body.get("result") != "ok":
            self._sid = None
            raise EblocAuthError(body.get("message") or body.get("result") or "login eșuat")
        self._sid = str(body.get("session_id", ""))
        self.user_id = str(body.get("id_user", ""))

    async def _call(self, script: str, **params: Any) -> dict[str, Any]:
        """Apel autentificat; reface login-ul o dată dacă sesiunea a expirat."""
        async with self._lock:
            if not self._sid:
                await self.login()
        body = await self._get(script, session_id=self._sid, **params)
        if body.get("result") == "ok":
            return body
        async with self._lock:
            await self.login()
        body = await self._get(script, session_id=self._sid, **params)
        if body.get("result") != "ok":
            raise EblocError(f"{script}: {body.get('result')}")
        return body

    async def fetch_all(self) -> dict[str, Apartment]:
        """Citește toate apartamentele cu sume, contoare și plăți."""
        info = await self._call("AppGetInfo.php")
        result: dict[str, Apartment] = {}

        for assoc in info.get("aInfoAsoc") or []:
            assoc_id = str(assoc.get("id", ""))
            if not assoc_id:
                continue
            assoc_name = str(assoc.get("nume") or f"Asociația {assoc_id}")
            home = await self._call("AppHomeGetAp.php", id_asoc=assoc_id)
            assoc_info = {k: v for k, v in home.items() if not isinstance(v, (list, dict))}

            meters_by_ap = await self._meters_for(assoc_id, assoc_info.get("luna", ""))

            for ap in home.get("aInfoAp") or []:
                ap_id = str(ap.get("id_ap", ""))
                if not ap_id:
                    continue
                apt = Apartment(
                    assoc_id=assoc_id,
                    assoc_name=assoc_name,
                    ap_id=ap_id,
                    label=f"Ap. {ap.get('ap', ap_id)}",
                    home=ap,
                    assoc_info=assoc_info,
                    meters=meters_by_ap.get(ap_id, meters_by_ap.get("*", [])),
                )
                try:
                    pay = await self._call(
                        "AppIstoricPlatiGetPlati.php", id_asoc=assoc_id, id_ap=ap_id
                    )
                    apt.payments = pay.get("aChitante") or []
                except EblocError as err:
                    _LOGGER.debug("Istoric plăți indisponibil pentru %s: %s", apt.key, err)
                result[apt.key] = apt

        return result

    async def _meters_for(self, assoc_id: str, fallback_month: str) -> dict[str, list]:
        """Întoarce contoarele grupate pe id_ap ("*" dacă API-ul nu dă id_ap)."""
        month = fallback_month
        try:
            months = await self._call("AppContoareGetIndexLuni.php", id_asoc=assoc_id)
            first = (months.get("aLuni") or [None])[0]
            if isinstance(first, dict):
                first = first.get("luna")
            if first:
                month = str(first)
        except EblocError as err:
            _LOGGER.debug("Fără listă de luni pentru contoare (%s): %s", assoc_id, err)
        if not month:
            return {}

        try:
            data = await self._call("AppContoareGetIndex.php", id_asoc=assoc_id, luna=month)
        except EblocError as err:
            _LOGGER.debug("Contoare indisponibile pentru %s: %s", assoc_id, err)
            return {}

        definitions = {
            str(m.get("id_contor")): m for m in data.get("aInfoContoare") or []
        }
        grouped: dict[str, list] = {}
        for reading in data.get("aInfoIndex") or []:
            meter_id = str(reading.get("id_contor", ""))
            if not meter_id:
                continue
            merged = {**definitions.get(meter_id, {}), **reading, "luna": month}
            grouped.setdefault(str(reading.get("id_ap", "*")), []).append(merged)
        return grouped
