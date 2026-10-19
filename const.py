"""Constante pentru integrarea E-bloc (personal)."""

from __future__ import annotations

DOMAIN = "ebloc_personal"
NAME = "E-bloc (personal)"

# Endpoint-urile publice folosite de aplicația mobilă e-bloc.ro
API_ROOT = "https://www.e-bloc.ro/ajax"
APP_KEY = "58126855-ef70-4548-a35e-eca020c24570"
APP_INFO = {
    "app_version": "8.90",
    "os_version": "14",
    "device_brand": "samsung",
    "device_model": "SM-S928B",
    "device_type": 1,
}
REQUEST_HEADERS = {
    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 14)",
    "Accept": "application/json",
    "Accept-Language": "ro-RO,ro;q=0.9",
}
REQUEST_TIMEOUT = 30

CONF_SCAN_HOURS = "scan_interval_hours"
DEFAULT_SCAN_HOURS = 6
MIN_SCAN_HOURS = 1
MAX_SCAN_HOURS = 24

# Valori brute din API
MONEY_SCALE = 100  # sume în bani
INDEX_SCALE = 1000  # indecși × 1000
INDEX_MISSING = -999999999

METER_TYPES = {
    "1": "apă rece",
    "2": "apă caldă",
    "3": "gaz",
    "4": "energie",
}
