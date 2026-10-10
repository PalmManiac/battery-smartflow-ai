"""Read signed grid power from a Shelly Pro 3EM Gen2 over local HTTP."""

from __future__ import annotations

import hashlib
import math
import re
import secrets
from dataclasses import dataclass
from urllib.parse import urlsplit


class ShellyPro3EMError(Exception):
    """Raised when the Shelly Pro 3EM cannot provide a valid reading."""


@dataclass(frozen=True)
class ShellyPro3EMReading:
    """Signed total and per-phase active power, in watts."""

    total_power_w: float
    phase_a_power_w: float | None = None
    phase_b_power_w: float | None = None
    phase_c_power_w: float | None = None


@dataclass
class ShellyDigestSession:
    """Small RFC 7616 SHA-256 digest state for one Shelly HTTP endpoint."""

    username: str = "admin"
    password: str = ""
    realm: str | None = None
    nonce: str | None = None
    challenge: str | None = None
    nonce_count: int = 0

    def reset(self) -> None:
        self.realm = None
        self.nonce = None
        self.challenge = None
        self.nonce_count = 0

    def authorization(self, *, method: str, uri: str, challenge: str) -> str:
        """Create an Authorization header from Shelly's SHA-256 challenge."""

        fields = _parse_digest_challenge(challenge)
        if fields.get("algorithm", "SHA-256").upper() != "SHA-256":
            raise ShellyPro3EMError("unsupported_digest_algorithm")
        if "auth" not in fields.get("qop", "auth").split(","):
            raise ShellyPro3EMError("unsupported_digest_qop")

        realm = fields.get("realm", "")
        nonce = fields.get("nonce", "")
        if not realm or not nonce or not self.password:
            raise ShellyPro3EMError("invalid_digest_challenge")

        if nonce != self.nonce or realm != self.realm or fields.get("stale") == "true":
            self.realm = realm
            self.nonce = nonce
            self.challenge = challenge
            self.nonce_count = 0

        self.nonce_count += 1
        nc = f"{self.nonce_count:08x}"
        cnonce = f"{secrets.randbits(64):016x}"
        ha1 = _sha256(f"{self.username}:{realm}:{self.password}")
        ha2 = _sha256(f"{method}:{uri}")
        response = _sha256(f"{ha1}:{nonce}:{nc}:{cnonce}:auth:{ha2}")

        parts = [
            f'username="{_quote(self.username)}"',
            f'realm="{_quote(realm)}"',
            f'nonce="{_quote(nonce)}"',
            f'uri="{_quote(uri)}"',
            'algorithm=SHA-256',
            f'response="{response}"',
            "qop=auth",
            f"nc={nc}",
            f'cnonce="{cnonce}"',
        ]
        if opaque := fields.get("opaque"):
            parts.append(f'opaque="{_quote(opaque)}"')
        return "Digest " + ", ".join(parts)


def validate_shelly_host(host: str) -> str:
    """Normalize a hostname/IP and reject schemes, paths, and credentials."""

    value = str(host or "").strip()
    if not value or any(char in value for char in "/@?#"):
        raise ValueError("invalid_shelly_host")
    if "://" in value or value.startswith("[") or value.endswith("]"):
        raise ValueError("invalid_shelly_host")
    parsed = urlsplit(f"http://{value}")
    if not parsed.hostname or parsed.port is not None or parsed.path not in ("", "/"):
        raise ValueError("invalid_shelly_host")
    return parsed.hostname


def parse_shelly_pro_3em_power(payload: object) -> float:
    """Return total grid power in watts (positive import, negative export)."""

    return parse_shelly_pro_3em_reading(payload).total_power_w


def parse_shelly_pro_3em_reading(payload: object) -> ShellyPro3EMReading:
    """Parse total and per-phase active power from an EM.GetStatus payload."""

    if not isinstance(payload, dict):
        raise ShellyPro3EMError("invalid_status_payload")

    phases: list[float | None] = []
    for phase in "abc":
        raw_phase = payload.get(f"{phase}_act_power")
        if raw_phase is None:
            phases.append(None)
            continue
        try:
            phase_power = float(raw_phase)
        except (TypeError, ValueError) as err:
            raise ShellyPro3EMError("invalid_phase_power") from err
        if not math.isfinite(phase_power):
            raise ShellyPro3EMError("invalid_phase_power")
        phases.append(phase_power)

    value = payload.get("total_act_power")
    if value is None:
        if any(phase is None for phase in phases):
            raise ShellyPro3EMError("missing_total_power")
        value = sum(phase for phase in phases if phase is not None)

    try:
        power = float(value)
    except (TypeError, ValueError) as err:
        raise ShellyPro3EMError("invalid_total_power") from err
    if not math.isfinite(power):
        raise ShellyPro3EMError("invalid_total_power")
    return ShellyPro3EMReading(power, *phases)


async def async_read_shelly_pro_3em_power(
    session,
    *,
    host: str,
    password: str = "",
    auth: ShellyDigestSession | None = None,
    timeout_seconds: float = 3.0,
) -> float:
    """Poll the documented Gen2 EM.GetStatus endpoint over the local network."""

    return (
        await async_read_shelly_pro_3em_reading(
            session,
            host=host,
            password=password,
            auth=auth,
            timeout_seconds=timeout_seconds,
        )
    ).total_power_w


async def async_read_shelly_pro_3em_reading(
    session,
    *,
    host: str,
    password: str = "",
    auth: ShellyDigestSession | None = None,
    timeout_seconds: float = 3.0,
) -> ShellyPro3EMReading:
    """Poll the documented Gen2 EM.GetStatus endpoint over the local network."""

    normalized_host = validate_shelly_host(host)
    host_for_url = (
        f"[{normalized_host}]" if ":" in normalized_host else normalized_host
    )
    url = f"http://{host_for_url}/rpc/EM.GetStatus?id=0"
    uri = "/rpc/EM.GetStatus?id=0"
    auth_state = auth or ShellyDigestSession(password=password)
    auth_state.password = password
    timeout = timeout_seconds

    challenge = auth_state.challenge if password else None
    for attempt in range(2):
        headers = {}
        if challenge:
            headers["Authorization"] = auth_state.authorization(
                method="GET", uri=uri, challenge=challenge
            )
        async with session.get(
            url,
            timeout=timeout,
            headers=headers or None,
        ) as response:
            if response.status == 401:
                challenge = response.headers.get("WWW-Authenticate", "")
                auth_state.reset()
                if not password:
                    raise ShellyPro3EMError("authentication_required")
                if attempt == 1:
                    raise ShellyPro3EMError("authentication_failed")
                continue
            if response.status >= 400:
                raise ShellyPro3EMError(f"http_{response.status}")
            return parse_shelly_pro_3em_reading(
                await response.json(content_type=None)
            )

    raise ShellyPro3EMError("authentication_failed")


def _parse_digest_challenge(challenge: str) -> dict[str, str]:
    """Parse quoted or token values from a WWW-Authenticate Digest header."""

    if not challenge.lower().startswith("digest "):
        raise ShellyPro3EMError("unsupported_authentication_scheme")
    return {
        key.lower(): (quoted if quoted else token).strip()
        for key, quoted, token in re.findall(
            r'([A-Za-z0-9_-]+)\s*=\s*(?:"((?:\\.|[^"])*)"|([^,\s]+))',
            challenge[7:],
        )
    }


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
