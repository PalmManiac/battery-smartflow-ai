"""Privacy-safe presentation helpers for native Zendure setup."""

from __future__ import annotations

from typing import Any


STORED_APP_TOKEN_MASK = "••••••••••••"


def resolve_app_token_input(value: Any, stored_token: Any) -> str:
    """Return a replacement token or reuse the privately stored value."""

    submitted = str(value or "").strip()
    stored = str(stored_token or "").strip()
    if not submitted or submitted == STORED_APP_TOKEN_MASK:
        return stored
    return submitted


def native_device_name(display_name: Any, model: Any) -> str:
    """Build one readable name without repeating an identical model."""

    name = str(display_name or "").strip()
    product_model = str(model or "").strip()
    if not name:
        return product_model or "Zendure device"
    if not product_model or product_model.casefold() in name.casefold():
        return name
    return f"{name} – {product_model}"


def native_device_label(
    display_name: Any,
    model: Any,
    pack_count: int | None,
) -> str:
    """Add packs only when at least one pack was positively reported."""

    label = native_device_name(display_name, model)
    if _known_positive_pack_count(pack_count):
        unit = "pack" if pack_count == 1 else "packs"
        return f"{label} ({pack_count} {unit})"
    return label


def native_device_summary_line(
    display_name: Any,
    model: Any,
    pack_count: int | None,
    online: bool | None,
) -> str:
    """Build the compact detail line shown above the device selector."""

    parts = [native_device_name(display_name, model)]
    if _known_positive_pack_count(pack_count):
        unit = "pack" if pack_count == 1 else "packs"
        parts.append(f"{pack_count} {unit}")
    parts.append(
        "online"
        if online is True
        else "offline"
        if online is False
        else "status unknown"
    )
    return f"• {', '.join(parts)}"


def _known_positive_pack_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0
