"""Safe filesystem export for V4.4.0 JSON debug packages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import re

from .debug_package import DebugPackage, redact_secrets
from .core.clock import SystemClock


DEBUG_DIRECTORY = Path("bsfai") / "debug"
DEFAULT_MAX_EXPORT_BYTES = 16 * 1024 * 1024
DEFAULT_MAX_RETAINED_PACKAGES = 10
_DEBUG_FILE_GLOB = "bsfai_debug_*.json"
_ENTITY_ID_PATTERN = re.compile(r"^([a-z_][a-z0-9_]*)\.([a-z0-9_]+)$")
_ENTITY_DOMAINS = {
    "binary_sensor",
    "button",
    "climate",
    "cover",
    "device_tracker",
    "fan",
    "input_boolean",
    "input_datetime",
    "input_number",
    "input_select",
    "input_text",
    "light",
    "lock",
    "media_player",
    "number",
    "person",
    "select",
    "sensor",
    "switch",
    "text",
    "update",
}


class DebugExportError(RuntimeError):
    """Raised when a debug package cannot be exported safely."""


@dataclass(frozen=True, slots=True)
class DebugExportResult:
    """Details of one successful debug-package export."""

    path: Path
    size_bytes: int
    removed_old_packages: int


def _filename(created_at: datetime) -> str:
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("Debug timestamps must be timezone-aware")
    stamp = created_at.astimezone(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    return f"bsfai_debug_{stamp}.json"


def _available_destination(directory: Path, filename: str) -> Path:
    """Return a new destination without overwriting an existing debug package."""

    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    for suffix in range(1, 10_000):
        candidate = directory / f"{stem}_{suffix}.json"
        if not candidate.exists():
            return candidate
    raise DebugExportError("Unable to allocate a unique debug package filename")


def _serialize(package: DebugPackage) -> bytes:
    """Serialize through the package API and redact once more at the I/O edge."""

    safe_package = _anonymize_entity_ids(redact_secrets(package.as_dict()))
    safe_package["meta"]["entity_ids_anonymized"] = True
    safe_package["meta"]["serialization"] = "compact"
    text = json.dumps(
        safe_package,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=False,
        allow_nan=False,
    )
    return (text + "\n").encode("utf-8")


def _anonymize_entity_ids(value):
    """Replace exact HA entity IDs with stable package-local aliases.

    Domains and equality relationships remain visible for support analysis,
    while object IDs containing names, addresses or device serials do not
    leave the Home Assistant instance in an exported package.
    """

    aliases: dict[str, str] = {}

    def anonymize(item):
        if isinstance(item, dict):
            return {key: anonymize(child) for key, child in item.items()}
        if isinstance(item, list):
            return [anonymize(child) for child in item]
        if not isinstance(item, str):
            return item

        match = _ENTITY_ID_PATTERN.fullmatch(item)
        if match is None or match.group(1) not in _ENTITY_DOMAINS:
            return item

        if item not in aliases:
            aliases[item] = (
                f"{match.group(1)}.debug_entity_{len(aliases) + 1:02d}"
            )
        return aliases[item]

    return anonymize(value)


def _prune_old_packages(directory: Path, *, retain: int) -> int:
    """Delete only old files matching BSFAI's own debug filename pattern."""

    packages = sorted(
        (path for path in directory.glob(_DEBUG_FILE_GLOB) if path.is_file()),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
        reverse=True,
    )
    removed = 0
    for path in packages[retain:]:
        try:
            path.unlink()
            removed += 1
        except OSError:
            # Retention cleanup must never invalidate an otherwise successful
            # export. A later export can retry removal.
            continue
    return removed


def export_debug_package(
    package: DebugPackage,
    *,
    config_directory: str | Path,
    max_export_bytes: int = DEFAULT_MAX_EXPORT_BYTES,
    max_retained_packages: int = DEFAULT_MAX_RETAINED_PACKAGES,
) -> DebugExportResult:
    """Atomically export one package below the Home Assistant config path."""

    if max_export_bytes < 1:
        raise ValueError("max_export_bytes must be at least 1")
    if max_retained_packages < 1:
        raise ValueError("max_retained_packages must be at least 1")

    try:
        payload = _serialize(package)
    except (TypeError, ValueError) as err:
        raise DebugExportError(f"Debug package serialization failed: {err}") from err
    if len(payload) > max_export_bytes:
        raise DebugExportError(
            f"Debug package exceeds the {max_export_bytes}-byte export limit"
        )

    directory = Path(config_directory).resolve() / DEBUG_DIRECTORY
    temporary_path: Path | None = None
    try:
        directory.mkdir(parents=True, exist_ok=True)
        destination = _available_destination(
            directory,
            _filename(package.created_at or SystemClock().utc_now()),
        )
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".bsfai_debug_",
            suffix=".tmp",
            dir=directory,
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
        temporary_path = None
    except OSError as err:
        raise DebugExportError(f"Debug package write failed: {err}") from err
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass

    removed = _prune_old_packages(
        directory,
        retain=max_retained_packages,
    )
    return DebugExportResult(
        path=destination,
        size_bytes=len(payload),
        removed_old_packages=removed,
    )
