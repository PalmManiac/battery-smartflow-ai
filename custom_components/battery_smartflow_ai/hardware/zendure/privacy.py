"""Central diagnostic privacy boundary for native Zendure data.

Credentials remain transport-layer inputs.  This module only creates detached,
JSON-safe diagnostic representations and must never be used as an internal
device identity store.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, Mapping


REDACTED = "[REDACTED]"

_SECRET_MARKERS = (
    "accesstoken",
    "apikey",
    "appkey",
    "auth",
    "bearer",
    "clientid",
    "clientsecret",
    "cookie",
    "credential",
    "nonce",
    "password",
    "privatekey",
    "refreshtoken",
    "secret",
    "signature",
    "ssid",
    "token",
    "username",
)
_NETWORK_MARKERS = (
    "apibase",
    "apiurl",
    "baseurl",
    "broker",
    "endpoint",
    "hostname",
    "ipaddress",
    "mqtturl",
)
_IDENTITY_KEYS = {
    "deviceid": "DEVICE",
    "devicekey": "DEVICE",
    "packid": "PACK",
    "packkey": "PACK",
    "productkey": "PRODUCT",
    "serial": "SERIAL",
    "serialnumber": "SERIAL",
    "sn": "SERIAL",
    "snnumber": "SERIAL",
}
_IDENTITY_CONTAINERS = {
    "devices": "DEVICE",
    "devicemap": "DEVICE",
    "packs": "PACK",
    "packmap": "PACK",
}
_PERSONAL_KEYS = {"devicename"}
_AUTHORIZATION_PATTERN = re.compile(
    r"(?i)\bauthorization(\s*[:=]\s*)(?:(bearer|basic)\s+)?[^\s,;&]+"
)
_BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b("
    r"access[_ -]?token|refresh[_ -]?token|api[_ -]?key|app[_ -]?key|"
    r"client[_ -]?(?:id|secret)|password|secret|signature|token|"
    r"username|ssid"
    r")\b(\s*[:=]\s*)([^\s,;&]+)"
)
_NETWORK_URL_PATTERN = re.compile(r"(?i)\b(?:https?|mqtts?)://[^\s,;&]+")
_IPV4_PATTERN = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
_LOCAL_HOST_PATTERN = re.compile(r"(?i)\b[a-z0-9][a-z0-9.-]*\.local\b")


def _normalized_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def _identity_kind(key: Any) -> str | None:
    return _IDENTITY_KEYS.get(_normalized_key(key))


def _is_secret_key(key: Any) -> bool:
    normalized = _normalized_key(key)
    return any(marker in normalized for marker in _SECRET_MARKERS)


def _is_network_key(key: Any) -> bool:
    normalized = _normalized_key(key)
    return normalized in {"host", "ip", "server", "url"} or any(
        marker in normalized for marker in _NETWORK_MARKERS
    )


def _is_personal_key(key: Any) -> bool:
    return _normalized_key(key) in _PERSONAL_KEYS


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Diagnostic timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_safe(value: Any) -> Any:
    if isinstance(value, str):
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, datetime):
        return _iso_utc(value)
    if isinstance(value, Enum):
        return _json_safe(value.value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]
    return str(value)


class ZendureDiagnosticSanitizer:
    """Create one package-local, privacy-safe diagnostic view."""

    def __init__(self) -> None:
        self._aliases: dict[tuple[str, str], str] = {}
        self._secret_values: set[str] = set()
        self._identity_values: dict[str, str] = {}

    def sanitize(self, value: Any) -> Any:
        """Return a detached JSON-safe copy with secrets and identities removed."""

        safe = _json_safe(deepcopy(value))
        self._discover(safe)
        return self._sanitize_value(safe)

    def sanitize_exception(self, error: BaseException) -> str:
        """Return an exception summary safe for logs and diagnostics."""

        return self._sanitize_text(f"{type(error).__name__}: {error}")

    def _alias(self, kind: str, value: Any) -> str:
        original = str(value)
        key = (kind, original)
        if key not in self._aliases:
            number = 1 + sum(
                1 for existing_kind, _ in self._aliases if existing_kind == kind
            )
            self._aliases[key] = f"ZD_{kind}_A{number}"
        return self._aliases[key]

    def _discover(self, value: Any, container_kind: str | None = None) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if container_kind is not None:
                    original_key = str(key)
                    alias = self._alias(container_kind, original_key)
                    if len(original_key) >= 4:
                        self._identity_values[original_key] = alias
                if _is_secret_key(key):
                    if isinstance(item, (str, int, float)) and not isinstance(item, bool):
                        text = str(item)
                        if len(text) >= 4:
                            self._secret_values.add(text)
                    continue
                kind = _identity_kind(key)
                if kind is not None and item is not None:
                    original = str(item)
                    alias = self._alias(kind, original)
                    if len(original) >= 4:
                        self._identity_values[original] = alias
                self._discover(
                    item,
                    _IDENTITY_CONTAINERS.get(_normalized_key(key)),
                )
            return
        if isinstance(value, list):
            for item in value:
                self._discover(item)

    def _sanitize_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            for key, item in value.items():
                safe_key = self._sanitize_mapping_key(str(key))
                if (
                    _is_secret_key(key)
                    or _is_network_key(key)
                    or _is_personal_key(key)
                ):
                    result[safe_key] = REDACTED
                    continue
                kind = _identity_kind(key)
                if kind is not None and item is not None:
                    result[safe_key] = self._alias(kind, item)
                    continue
                result[safe_key] = self._sanitize_value(item)
            return result
        if isinstance(value, list):
            return [self._sanitize_value(item) for item in value]
        if isinstance(value, str):
            return self._sanitize_text(value)
        return value

    def _sanitize_mapping_key(self, value: str) -> str:
        """Replace identity-bearing map keys without rewriting schema names."""

        text = value
        for original, alias in sorted(
            self._identity_values.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            text = text.replace(original, alias)
        return text

    def _sanitize_text(self, value: str) -> str:
        text = _AUTHORIZATION_PATTERN.sub(
            lambda match: (
                f"Authorization{match.group(1)}"
                f"{match.group(2).title() + ' ' if match.group(2) else ''}"
                f"{REDACTED}"
            ),
            value,
        )
        text = _BEARER_PATTERN.sub(f"Bearer {REDACTED}", text)
        text = _SECRET_ASSIGNMENT_PATTERN.sub(
            lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}",
            text,
        )
        text = _NETWORK_URL_PATTERN.sub(REDACTED, text)
        text = _IPV4_PATTERN.sub(REDACTED, text)
        text = _LOCAL_HOST_PATTERN.sub(REDACTED, text)
        for secret in sorted(self._secret_values, key=len, reverse=True):
            text = text.replace(secret, REDACTED)
        for original, alias in sorted(
            self._identity_values.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            text = text.replace(original, alias)
        return text


def sanitize_zendure_diagnostics(value: Any) -> Any:
    """Sanitize one complete diagnostic payload with one alias namespace."""

    return ZendureDiagnosticSanitizer().sanitize(value)
