"""Configurare din interfață: email + parolă, apoi interval de actualizare."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EblocAuthError, EblocClient, EblocError
from .const import CONF_SCAN_HOURS, DEFAULT_SCAN_HOURS, DOMAIN, MAX_SCAN_HOURS, MIN_SCAN_HOURS, NAME

LOGIN_SCHEMA = vol.Schema(
    {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
)


class EblocConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _check(self, email: str, password: str) -> tuple[str | None, str | None]:
        """Încearcă login-ul; întoarce (user_id, cod_eroare)."""
        client = EblocClient(async_get_clientsession(self.hass), email, password)
        try:
            await client.login()
        except EblocAuthError:
            return None, "invalid_auth"
        except EblocError:
            return None, "cannot_connect"
        return client.user_id, None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            user_id, error = await self._check(user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(user_id or user_input[CONF_EMAIL].lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"{NAME} – {user_input[CONF_EMAIL]}", data=user_input
                )
        return self.async_show_form(step_id="user", data_schema=LOGIN_SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            _, error = await self._check(entry.data[CONF_EMAIL], user_input[CONF_PASSWORD])
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={"email": entry.data[CONF_EMAIL]},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return EblocOptionsFlow()


class EblocOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_SCAN_HOURS, DEFAULT_SCAN_HOURS)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_HOURS, default=current): vol.All(
                        vol.Coerce(int), vol.Range(min=MIN_SCAN_HOURS, max=MAX_SCAN_HOURS)
                    )
                }
            ),
        )
