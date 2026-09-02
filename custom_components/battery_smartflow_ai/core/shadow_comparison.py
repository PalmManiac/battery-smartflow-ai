"""Read-only comparison of native and legacy neutral device observations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math
from types import MappingProxyType
from typing import Any, Mapping

from .models import MeasuredValue, ValueValidity


class ShadowComparisonStatus(StrEnum):
    """Diagnostic classification of one neutral semantic field."""

    IDENTICAL = "identical"
    WITHIN_TOLERANCE = "within_tolerance"
    TIME_SHIFT_PLAUSIBLE = "time_shift_plausible"
    NATIVE_MISSING = "native_missing"
    REFERENCE_MISSING = "reference_missing"
    UNSUPPORTED = "unsupported"
    TYPE_MISMATCH = "type_mismatch"
    SCALE_MISMATCH = "scale_mismatch"
    SIGN_MISMATCH = "sign_mismatch"
    UNIT_MISMATCH = "unit_mismatch"
    DERIVED_REFERENCE_ONLY = "derived_reference_only"
    NATIVE_ONLY = "native_only"
    MISMATCH = "mismatch"


@dataclass(frozen=True, slots=True)
class ShadowValue:
    """One neutral value with unit and provenance, not a raw property."""

    measurement: MeasuredValue[Any]
    unit: str | None = None
    derived: bool = False


@dataclass(frozen=True, slots=True)
class ShadowFieldRule:
    """Evidence-based comparison rule; defaults make no guessed tolerance."""

    absolute_tolerance: float = 0.0
    max_time_delta_seconds: float | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.absolute_tolerance):
            raise ValueError("absolute_tolerance must be finite")
        if self.absolute_tolerance < 0:
            raise ValueError("absolute_tolerance must be non-negative")
        if self.max_time_delta_seconds is not None:
            if not math.isfinite(self.max_time_delta_seconds):
                raise ValueError("max_time_delta_seconds must be finite")
            if self.max_time_delta_seconds < 0:
                raise ValueError("max_time_delta_seconds must be non-negative")


@dataclass(frozen=True, slots=True)
class ShadowPackSnapshot:
    """Pack values keyed by a stable source identity, never list position."""

    pack_id: str
    values: Mapping[str, ShadowValue]

    def __post_init__(self) -> None:
        if not self.pack_id:
            raise ValueError("pack_id is required")
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))


@dataclass(frozen=True, slots=True)
class ShadowDeviceSnapshot:
    """One source's neutral observations for a main system and its packs."""

    system_id: str
    values: Mapping[str, ShadowValue]
    packs: Mapping[str, ShadowPackSnapshot]

    def __post_init__(self) -> None:
        if not self.system_id:
            raise ValueError("system_id is required")
        packs = dict(self.packs)
        if any(pack_id != pack.pack_id for pack_id, pack in packs.items()):
            raise ValueError("pack mapping key must equal the stable pack_id")
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))
        object.__setattr__(self, "packs", MappingProxyType(packs))


@dataclass(frozen=True, slots=True)
class ShadowBinding:
    """Explicit V4-to-V5 identity association for one main system."""

    native_system_id: str
    reference_system_id: str
    pack_ids: Mapping[str, str]

    def __post_init__(self) -> None:
        if not self.native_system_id or not self.reference_system_id:
            raise ValueError("both main-system identities are required")
        values = dict(self.pack_ids)
        if len(set(values.values())) != len(values):
            raise ValueError("reference pack identities must be unique")
        object.__setattr__(self, "pack_ids", MappingProxyType(values))


@dataclass(frozen=True, slots=True)
class ShadowFieldComparison:
    """Compact evidence for one compared semantic value."""

    scope: str
    field: str
    status: ShadowComparisonStatus
    native_value: Any | None
    reference_value: Any | None
    native_validity: ValueValidity | None
    reference_validity: ValueValidity | None
    absolute_difference: float | None = None
    time_delta_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class ShadowDeviceReport:
    """Bounded diagnostic report for one explicitly bound main system."""

    native_system_id: str
    reference_system_id: str
    comparisons: tuple[ShadowFieldComparison, ...]

    @property
    def compared_fields(self) -> int:
        return len(self.comparisons)

    @property
    def within_tolerance(self) -> int:
        return sum(
            item.status
            in {
                ShadowComparisonStatus.IDENTICAL,
                ShadowComparisonStatus.WITHIN_TOLERANCE,
            }
            for item in self.comparisons
        )

    @property
    def time_shift_plausible(self) -> int:
        return sum(
            item.status is ShadowComparisonStatus.TIME_SHIFT_PLAUSIBLE
            for item in self.comparisons
        )

    @property
    def mismatches(self) -> int:
        return sum(_is_mismatch(item.status) for item in self.comparisons)

    @property
    def last_mismatch(self) -> ShadowFieldComparison | None:
        """Return the newest comparison-order mismatch for compact diagnostics."""

        return next(
            (
                item
                for item in reversed(self.comparisons)
                if _is_mismatch(item.status)
            ),
            None,
        )

    @property
    def status_counts(self) -> Mapping[ShadowComparisonStatus, int]:
        """Summarize categories without creating a persistent sensor surface."""

        counts = {status: 0 for status in ShadowComparisonStatus}
        for item in self.comparisons:
            counts[item.status] += 1
        return MappingProxyType(counts)


class ShadowComparator:
    """Compare only; this type intentionally has no command or backend port."""

    def __init__(
        self,
        rules: Mapping[str, ShadowFieldRule] | None = None,
    ) -> None:
        self._rules = MappingProxyType(dict(rules or {}))

    def compare_many(
        self,
        native: Mapping[str, ShadowDeviceSnapshot],
        reference: Mapping[str, ShadowDeviceSnapshot],
        bindings: tuple[ShadowBinding, ...],
    ) -> tuple[ShadowDeviceReport, ...]:
        """Compare any number of explicitly bound systems independently."""

        native_ids = [item.native_system_id for item in bindings]
        reference_ids = [item.reference_system_id for item in bindings]
        if len(set(native_ids)) != len(native_ids):
            raise ValueError("native system binding must be unique")
        if len(set(reference_ids)) != len(reference_ids):
            raise ValueError("reference system binding must be unique")
        reports = []
        for binding in bindings:
            try:
                native_device = native[binding.native_system_id]
                reference_device = reference[binding.reference_system_id]
            except KeyError as error:
                raise ValueError("bound main system is missing") from error
            reports.append(
                self.compare_device(native_device, reference_device, binding)
            )
        return tuple(reports)

    def compare_device(
        self,
        native: ShadowDeviceSnapshot,
        reference: ShadowDeviceSnapshot,
        binding: ShadowBinding,
    ) -> ShadowDeviceReport:
        """Compare one bound system and only explicitly associated packs."""

        if native.system_id != binding.native_system_id:
            raise ValueError("native snapshot does not match binding")
        if reference.system_id != binding.reference_system_id:
            raise ValueError("reference snapshot does not match binding")
        comparisons = list(
            self._compare_values("main", native.values, reference.values)
        )
        for native_pack_id, reference_pack_id in binding.pack_ids.items():
            native_pack = native.packs.get(native_pack_id)
            reference_pack = reference.packs.get(reference_pack_id)
            scope = f"pack:{native_pack_id}"
            if native_pack is None or reference_pack is None:
                comparisons.append(
                    ShadowFieldComparison(
                        scope=scope,
                        field="pack_identity",
                        status=(
                            ShadowComparisonStatus.NATIVE_MISSING
                            if native_pack is None
                            else ShadowComparisonStatus.REFERENCE_MISSING
                        ),
                        native_value=native_pack_id if native_pack else None,
                        reference_value=(
                            reference_pack_id if reference_pack else None
                        ),
                        native_validity=None,
                        reference_validity=None,
                    )
                )
                continue
            comparisons.extend(
                self._compare_values(
                    scope,
                    native_pack.values,
                    reference_pack.values,
                )
            )
        return ShadowDeviceReport(
            native_system_id=native.system_id,
            reference_system_id=reference.system_id,
            comparisons=tuple(comparisons),
        )

    def _compare_values(
        self,
        scope: str,
        native: Mapping[str, ShadowValue],
        reference: Mapping[str, ShadowValue],
    ) -> tuple[ShadowFieldComparison, ...]:
        fields = sorted(set(native) | set(reference))
        return tuple(
            self._compare_field(
                scope,
                field,
                native.get(field),
                reference.get(field),
                self._rules.get(field, ShadowFieldRule()),
            )
            for field in fields
        )

    @staticmethod
    def _compare_field(
        scope: str,
        field: str,
        native: ShadowValue | None,
        reference: ShadowValue | None,
        rule: ShadowFieldRule,
    ) -> ShadowFieldComparison:
        status, difference, time_delta = _classify(native, reference, rule)
        return ShadowFieldComparison(
            scope=scope,
            field=field,
            status=status,
            native_value=(native.measurement.value if native else None),
            reference_value=(reference.measurement.value if reference else None),
            native_validity=(native.measurement.validity if native else None),
            reference_validity=(
                reference.measurement.validity if reference else None
            ),
            absolute_difference=difference,
            time_delta_seconds=time_delta,
        )


def _classify(
    native: ShadowValue | None,
    reference: ShadowValue | None,
    rule: ShadowFieldRule,
) -> tuple[ShadowComparisonStatus, float | None, float | None]:
    if native is None:
        if reference is not None and reference.derived:
            return ShadowComparisonStatus.DERIVED_REFERENCE_ONLY, None, None
        return ShadowComparisonStatus.NATIVE_MISSING, None, None
    if reference is None:
        return ShadowComparisonStatus.NATIVE_ONLY, None, None
    if (
        native.measurement.validity is ValueValidity.UNSUPPORTED
        or reference.measurement.validity is ValueValidity.UNSUPPORTED
    ):
        return ShadowComparisonStatus.UNSUPPORTED, None, None
    if not native.measurement.valid:
        return ShadowComparisonStatus.NATIVE_MISSING, None, None
    if not reference.measurement.valid:
        return ShadowComparisonStatus.REFERENCE_MISSING, None, None
    if native.unit != reference.unit:
        return ShadowComparisonStatus.UNIT_MISMATCH, None, None
    native_value = native.measurement.value
    reference_value = reference.measurement.value
    time_delta = _time_delta(native.measurement, reference.measurement)
    if native_value == reference_value and type(native_value) is type(reference_value):
        return ShadowComparisonStatus.IDENTICAL, 0.0, time_delta
    if _is_number(native_value) and _is_number(reference_value):
        native_number = float(native_value)
        reference_number = float(reference_value)
        difference = abs(native_number - reference_number)
        if difference <= rule.absolute_tolerance:
            return ShadowComparisonStatus.WITHIN_TOLERANCE, difference, time_delta
        if (
            time_delta is not None
            and rule.max_time_delta_seconds is not None
            and time_delta > rule.max_time_delta_seconds
        ):
            return ShadowComparisonStatus.TIME_SHIFT_PLAUSIBLE, difference, time_delta
        if math.isclose(native_number, -reference_number) and native_number != 0:
            return ShadowComparisonStatus.SIGN_MISMATCH, difference, time_delta
        if _known_scale_mismatch(native_number, reference_number, rule):
            return ShadowComparisonStatus.SCALE_MISMATCH, difference, time_delta
        return ShadowComparisonStatus.MISMATCH, difference, time_delta
    if type(native_value) is not type(reference_value):
        return ShadowComparisonStatus.TYPE_MISMATCH, None, time_delta
    return ShadowComparisonStatus.MISMATCH, None, time_delta


def _time_delta(
    native: MeasuredValue[Any],
    reference: MeasuredValue[Any],
) -> float | None:
    if native.observed_at is None or reference.observed_at is None:
        return None
    return abs((native.observed_at - reference.observed_at).total_seconds())


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _known_scale_mismatch(
    native: float,
    reference: float,
    rule: ShadowFieldRule,
) -> bool:
    if native == 0 or reference == 0:
        return False
    for factor in (0.001, 0.01, 0.1, 10.0, 100.0, 1000.0):
        if abs(native * factor - reference) <= rule.absolute_tolerance:
            return True
    return False


def _is_mismatch(status: ShadowComparisonStatus) -> bool:
    return status not in {
        ShadowComparisonStatus.IDENTICAL,
        ShadowComparisonStatus.WITHIN_TOLERANCE,
        ShadowComparisonStatus.TIME_SHIFT_PLAUSIBLE,
        ShadowComparisonStatus.UNSUPPORTED,
        ShadowComparisonStatus.DERIVED_REFERENCE_ONLY,
        ShadowComparisonStatus.NATIVE_ONLY,
    }
