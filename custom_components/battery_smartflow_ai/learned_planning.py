from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Literal

from homeassistant.util import dt as dt_util

from .decision_engine import PricePoint
from .forecast import ForecastSummary


LEARNED_STATUS_NOT_STARTED = "not_started"
LEARNED_STATUS_COLLECTING = "collecting"
LEARNED_STATUS_INSUFFICIENT_DATA = "insufficient_data"
LEARNED_STATUS_READY = "ready"
LEARNED_STATUS_ACTIVE = "active"

LEARNED_BLOCK_NOT_ENOUGH_DAYS = "not_enough_days"
LEARNED_BLOCK_NOT_ENOUGH_USABLE_DAYS = "not_enough_usable_days"
LEARNED_BLOCK_NIGHT_WINDOW_COVERAGE_TOO_LOW = "night_window_coverage_too_low"
LEARNED_BLOCK_MORNING_WINDOW_COVERAGE_TOO_LOW = "morning_window_coverage_too_low"
LEARNED_BLOCK_EVENING_WINDOW_COVERAGE_TOO_LOW = "evening_window_coverage_too_low"
LEARNED_BLOCK_DATA_QUALITY_TOO_LOW = "data_quality_too_low"

DEADLINE_REASON_BEFORE_PEAK_WINDOW = "before_peak_window"
DEADLINE_REASON_BEFORE_POOR_FORECAST_PERIOD = "before_poor_forecast_period"
DEADLINE_REASON_BEFORE_TYPICAL_MORNING_LOAD = "before_typical_morning_load"
DEADLINE_REASON_DEFAULT_OVERNIGHT_TARGET = "default_overnight_target"

LEARNED_MODE_DISABLED = "disabled"
LEARNED_MODE_COLLECTING = "collecting"
LEARNED_MODE_CLASSIC_FALLBACK = "classic_fallback"
LEARNED_MODE_READY = "ready"
LEARNED_MODE_WAIT = "wait"
LEARNED_MODE_CHARGE = "charge"

LEARNED_REASON_NOT_READY = "learned_charge_window_not_ready"
LEARNED_REASON_WAIT = "learned_charge_window_wait"
LEARNED_REASON_ACTIVE = "learned_charge_window_active"
LEARNED_REASON_LATEST_START_REACHED = "learned_charge_window_latest_start_reached"
LEARNED_REASON_NO_CHARGE_NEEDED = "learned_charge_window_no_charge_needed"
LEARNED_REASON_DEADLINE_TOO_CLOSE_START_NOW = "learned_charge_window_deadline_too_close_start_now"

SLOTS_PER_DAY = 96
SLOT_MINUTES = 15
ROLLING_DAYS = 14

MIN_HISTORY_DAYS = 7
MIN_USABLE_DAYS = 5
MIN_CORE_WINDOW_DAYS = 4
MIN_DATA_COVERAGE = 0.80

DEFAULT_FALLBACK_CHARGE_POWER_W = 1200.0
MIN_EFFECTIVE_CHARGE_POWER_W = 100.0

MIN_LEARNED_CHARGE_POWER_SAMPLE_W = 300.0
MIN_LEARNED_CHARGE_POWER_SAMPLES = 4

LearningStatus = Literal[
    "not_started",
    "collecting",
    "insufficient_data",
    "ready",
    "active",
]

DeadlineReason = Literal[
    "before_peak_window",
    "before_poor_forecast_period",
    "before_typical_morning_load",
    "default_overnight_target",
]


@dataclass
class LearningSample:
    """One measured energy sample used by the learned planning model.

    energy_kwh should represent consumption/discharge energy assigned to the time range.
    The interval may span partial slots; the builder will distribute energy proportionally.
    """

    start: datetime
    end: datetime
    energy_kwh: float


@dataclass
class LearningChargePowerSample:
    """One measured charging power sample used to estimate realistic charge speed."""

    ts: datetime
    power_w: float
    

@dataclass
class LearnedSlotModel:
    """Median consumption model for one day with 96 15-minute slots."""

    slot_kwh: list[float] = field(default_factory=lambda: [0.0] * SLOTS_PER_DAY)
    slot_sample_count: list[int] = field(default_factory=lambda: [0] * SLOTS_PER_DAY)
    data_coverage: float = 0.0
    history_days: int = 0
    usable_days: int = 0
    night_window_days: int = 0
    morning_window_days: int = 0
    evening_window_days: int = 0


@dataclass
class LearningReadiness:
    status: LearningStatus = LEARNED_STATUS_NOT_STARTED
    blocking_reason: str | None = None
    history_days: int = 0
    usable_days: int = 0
    night_window_days: int = 0
    morning_window_days: int = 0
    evening_window_days: int = 0
    data_coverage: float = 0.0

    @property
    def ready(self) -> bool:
        return self.status in (LEARNED_STATUS_READY, LEARNED_STATUS_ACTIVE)


@dataclass
class LearnedChargePlan:
    """Computed learned charge plan.

    This object is still decision-neutral. The DecisionEngine can later decide
    whether it wants to wait, charge or fall back to classic planning.
    """

    status: LearningStatus = LEARNED_STATUS_NOT_STARTED
    mode: str = LEARNED_MODE_DISABLED
    blocking_reason: str | None = None

    expected_consumption_kwh: float = 0.0
    available_battery_energy_kwh: float = 0.0
    reserve_margin_kwh: float = 0.0
    forecast_adjustment_kwh: float = 0.0
    raw_required_charge_energy_kwh: float = 0.0
    required_charge_energy_kwh: float = 0.0
    max_chargeable_energy_kwh: float = 0.0

    effective_charge_power_w: float = 0.0
    effective_window_slots: int = 0
    effective_window_minutes: int = 0

    planning_deadline: datetime | None = None
    deadline_reason: str | None = None
    optimal_charge_start: datetime | None = None
    optimal_charge_end: datetime | None = None
    window_score: float | None = None

    decision_reason: str | None = None

    bell_weights: list[float] = field(default_factory=list)
    selected_prices: list[float] = field(default_factory=list)


@dataclass
class LearnedProfileDiagnostics:
    """Transparency values derived from the learned 96-slot load profile."""

    typical_daily_consumption_kwh: float = 0.0
    average_house_load_w: float = 0.0
    current_slot_consumption_kwh: float = 0.0
    current_slot_average_w: float = 0.0
    current_slot_index: int = 0
    

def _as_local(dt: datetime) -> datetime:
    return dt_util.as_local(dt)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(float(minimum), min(float(value), float(maximum)))


def _slot_index(dt: datetime) -> int:
    local = _as_local(dt)
    return max(
        0,
        min(
            SLOTS_PER_DAY - 1,
            (local.hour * 60 + local.minute) // SLOT_MINUTES,
        ),
    )


def _slot_start_for_date(day: date, slot: int) -> datetime:
    slot = max(0, min(SLOTS_PER_DAY - 1, int(slot)))
    minutes = slot * SLOT_MINUTES
    base = datetime.combine(day, time(0, 0))
    local_tz = dt_util.get_default_time_zone()
    base = base.replace(tzinfo=local_tz)
    return base + timedelta(minutes=minutes)


def _date_range(start_day: date, end_day: date) -> list[date]:
    if end_day < start_day:
        return []

    out: list[date] = []
    cur = start_day
    while cur <= end_day:
        out.append(cur)
        cur += timedelta(days=1)
    return out


def _core_window_slots(start_hour: int, end_hour: int) -> range:
    start_slot = int((start_hour * 60) / SLOT_MINUTES)
    end_slot = int((end_hour * 60) / SLOT_MINUTES)
    return range(max(0, start_slot), min(SLOTS_PER_DAY, end_slot))


def _triangle_weights(slot_count: int) -> list[float]:
    """Return normalized symmetric triangle weights.

    Examples before normalization:
    3 -> [1, 2, 1]
    4 -> [1, 2, 2, 1]
    5 -> [1, 2, 3, 2, 1]
    """

    n = max(1, int(slot_count))

    if n == 1:
        return [1.0]

    raw: list[int] = []
    for idx in range(n):
        raw.append(min(idx + 1, n - idx))

    total = float(sum(raw))
    if total <= 0:
        return [1.0 / n] * n

    return [float(v) / total for v in raw]


def build_profile_diagnostics(
    model: LearnedSlotModel,
    now: datetime,
) -> LearnedProfileDiagnostics:
    """Build simple transparency values from the learned daily load profile."""

    if model is None or not model.slot_kwh:
        return LearnedProfileDiagnostics()

    typical_daily_kwh = max(0.0, float(sum(model.slot_kwh)))
    average_house_load_w = (typical_daily_kwh / 24.0) * 1000.0

    slot = _slot_index(now)
    current_slot_kwh = 0.0

    if 0 <= slot < len(model.slot_kwh):
        current_slot_kwh = max(0.0, float(model.slot_kwh[slot] or 0.0))

    current_slot_average_w = (
        current_slot_kwh / (SLOT_MINUTES / 60.0)
    ) * 1000.0

    return LearnedProfileDiagnostics(
        typical_daily_consumption_kwh=round(typical_daily_kwh, 3),
        average_house_load_w=round(average_house_load_w, 1),
        current_slot_consumption_kwh=round(current_slot_kwh, 3),
        current_slot_average_w=round(current_slot_average_w, 1),
        current_slot_index=int(slot),
    )
    

def _forecast_outlook(forecast: ForecastSummary | None) -> str:
    if forecast is None:
        return "unknown"
    return str(getattr(forecast, "pv_outlook", "unknown") or "unknown")


def build_slot_model(
    samples: list[LearningSample],
    now: datetime,
    rolling_days: int = ROLLING_DAYS,
) -> LearnedSlotModel:
    """Build a robust median 96-slot consumption model from raw samples."""

    now_local = _as_local(now)
    end_day = now_local.date()
    start_day = end_day - timedelta(days=max(1, int(rolling_days)) - 1)

    samples_by_slot: list[list[float]] = [[] for _ in range(SLOTS_PER_DAY)]
    day_slot_energy: dict[date, list[float]] = {
        day: [0.0] * SLOTS_PER_DAY for day in _date_range(start_day, end_day)
    }

    for sample in samples:
        if sample.energy_kwh <= 0:
            continue

        start = _as_local(sample.start)
        end = _as_local(sample.end)

        if end <= start:
            continue

        if end.date() < start_day or start.date() > end_day:
            continue

        total_seconds = max(1.0, (end - start).total_seconds())
        cur = start

        while cur < end:
            cur_day = cur.date()
            if cur_day < start_day or cur_day > end_day:
                next_cur = min(end, cur + timedelta(minutes=SLOT_MINUTES))
                cur = next_cur
                continue

            slot = _slot_index(cur)
            slot_start = _slot_start_for_date(cur_day, slot)
            slot_end = slot_start + timedelta(minutes=SLOT_MINUTES)
            overlap_end = min(end, slot_end)
            overlap_seconds = max(0.0, (overlap_end - cur).total_seconds())

            if overlap_seconds > 0:
                part_kwh = float(sample.energy_kwh) * (overlap_seconds / total_seconds)
                day_slot_energy[cur_day][slot] += part_kwh

            cur = overlap_end if overlap_end > cur else cur + timedelta(minutes=1)

    # Count only real history days with meaningful sample coverage.
    # This avoids a single learned slot at the beginning/end of the
    # rolling window making the history jump to 14 days.
    covered_slots_by_day = {
        day: sum(1 for v in slots if v > 0)
        for day, slots in day_slot_energy.items()
    }

    min_history_slots = max(1, int(math.ceil(SLOTS_PER_DAY * 0.10)))

    history_dates = {
        day
        for day, covered_slots in covered_slots_by_day.items()
        if covered_slots >= min_history_slots
    }

    history_days = len(history_dates)
    usable_days = 0

    night_window_days = 0
    morning_window_days = 0
    evening_window_days = 0

    night_slots = list(_core_window_slots(0, 6))
    morning_slots = list(_core_window_slots(6, 10))
    evening_slots = list(_core_window_slots(17, 22))

    covered_slots_total = 0
    possible_slots_total = max(1, history_days * SLOTS_PER_DAY)

    for day, slots in day_slot_energy.items():
        if day not in history_dates:
            continue

        covered_slots = covered_slots_by_day.get(day, 0)
        day_coverage = covered_slots / SLOTS_PER_DAY

        if day_coverage >= 0.50:
            usable_days += 1

        if any(slots[s] > 0 for s in night_slots):
            night_window_days += 1

        if any(slots[s] > 0 for s in morning_slots):
            morning_window_days += 1

        if any(slots[s] > 0 for s in evening_slots):
            evening_window_days += 1

        covered_slots_total += covered_slots

        for slot, value in enumerate(slots):
            if value > 0:
                samples_by_slot[slot].append(value)

    model_slots: list[float] = []
    slot_sample_count: list[int] = []

    for slot in range(SLOTS_PER_DAY):
        vals = samples_by_slot[slot]
        slot_sample_count.append(len(vals))

        if vals:
            model_slots.append(float(statistics.median(vals)))
            continue

        # Fallback: neighboring slots.
        neighbor_vals: list[float] = []
        for distance in (1, 2, 3, 4):
            left = slot - distance
            right = slot + distance

            if left >= 0:
                neighbor_vals.extend(samples_by_slot[left])
            if right < SLOTS_PER_DAY:
                neighbor_vals.extend(samples_by_slot[right])

            if neighbor_vals:
                break

        if neighbor_vals:
            model_slots.append(float(statistics.median(neighbor_vals)))
        else:
            model_slots.append(0.0)

    data_coverage = covered_slots_total / possible_slots_total

    return LearnedSlotModel(
        slot_kwh=model_slots,
        slot_sample_count=slot_sample_count,
        data_coverage=float(data_coverage),
        history_days=history_days,
        usable_days=usable_days,
        night_window_days=night_window_days,
        morning_window_days=morning_window_days,
        evening_window_days=evening_window_days,
    )


def evaluate_readiness(model: LearnedSlotModel) -> LearningReadiness:
    """Evaluate whether the learned model is allowed to be used."""

    if model.history_days <= 0:
        return LearningReadiness(
            status=LEARNED_STATUS_NOT_STARTED,
            blocking_reason=LEARNED_BLOCK_NOT_ENOUGH_DAYS,
            history_days=model.history_days,
            usable_days=model.usable_days,
            night_window_days=model.night_window_days,
            morning_window_days=model.morning_window_days,
            evening_window_days=model.evening_window_days,
            data_coverage=model.data_coverage,
        )

    if model.history_days < MIN_HISTORY_DAYS:
        return LearningReadiness(
            status=LEARNED_STATUS_COLLECTING,
            blocking_reason=LEARNED_BLOCK_NOT_ENOUGH_DAYS,
            history_days=model.history_days,
            usable_days=model.usable_days,
            night_window_days=model.night_window_days,
            morning_window_days=model.morning_window_days,
            evening_window_days=model.evening_window_days,
            data_coverage=model.data_coverage,
        )

    if model.usable_days < MIN_USABLE_DAYS:
        return LearningReadiness(
            status=LEARNED_STATUS_INSUFFICIENT_DATA,
            blocking_reason=LEARNED_BLOCK_NOT_ENOUGH_USABLE_DAYS,
            history_days=model.history_days,
            usable_days=model.usable_days,
            night_window_days=model.night_window_days,
            morning_window_days=model.morning_window_days,
            evening_window_days=model.evening_window_days,
            data_coverage=model.data_coverage,
        )

    if model.night_window_days < MIN_CORE_WINDOW_DAYS:
        blocking = LEARNED_BLOCK_NIGHT_WINDOW_COVERAGE_TOO_LOW
    elif model.morning_window_days < MIN_CORE_WINDOW_DAYS:
        blocking = LEARNED_BLOCK_MORNING_WINDOW_COVERAGE_TOO_LOW
    elif model.evening_window_days < MIN_CORE_WINDOW_DAYS:
        blocking = LEARNED_BLOCK_EVENING_WINDOW_COVERAGE_TOO_LOW
    elif model.data_coverage < MIN_DATA_COVERAGE:
        blocking = LEARNED_BLOCK_DATA_QUALITY_TOO_LOW
    else:
        blocking = None

    if blocking is not None:
        return LearningReadiness(
            status=LEARNED_STATUS_INSUFFICIENT_DATA,
            blocking_reason=blocking,
            history_days=model.history_days,
            usable_days=model.usable_days,
            night_window_days=model.night_window_days,
            morning_window_days=model.morning_window_days,
            evening_window_days=model.evening_window_days,
            data_coverage=model.data_coverage,
        )

    return LearningReadiness(
        status=LEARNED_STATUS_READY,
        blocking_reason=None,
        history_days=model.history_days,
        usable_days=model.usable_days,
        night_window_days=model.night_window_days,
        morning_window_days=model.morning_window_days,
        evening_window_days=model.evening_window_days,
        data_coverage=model.data_coverage,
    )


def expected_consumption_until(
    model: LearnedSlotModel,
    now: datetime,
    deadline: datetime,
) -> float:
    """Estimate consumption between now and deadline using the learned slot model."""

    now_local = _as_local(now)
    deadline_local = _as_local(deadline)

    if deadline_local <= now_local:
        return 0.0

    total = 0.0
    cur = now_local

    while cur < deadline_local:
        slot = _slot_index(cur)
        slot_start = _slot_start_for_date(cur.date(), slot)
        slot_end = slot_start + timedelta(minutes=SLOT_MINUTES)
        overlap_end = min(deadline_local, slot_end)
        overlap_seconds = max(0.0, (overlap_end - cur).total_seconds())

        if overlap_seconds > 0:
            factor = overlap_seconds / float(SLOT_MINUTES * 60)
            total += float(model.slot_kwh[slot]) * factor

        cur = overlap_end if overlap_end > cur else cur + timedelta(minutes=1)

    return max(0.0, float(total))


def available_battery_energy_kwh(
    total_battery_capacity_kwh: float,
    current_soc: float,
    soc_min: float,
) -> float:
    return float(total_battery_capacity_kwh) * max(
        0.0,
        (float(current_soc) - float(soc_min)) / 100.0,
    )


def max_chargeable_energy_kwh(
    total_battery_capacity_kwh: float,
    current_soc: float,
    soc_max: float,
) -> float:
    return float(total_battery_capacity_kwh) * max(
        0.0,
        (float(soc_max) - float(current_soc)) / 100.0,
    )


def reserve_margin_kwh(expected_consumption_kwh: float) -> float:
    return max(0.3, float(expected_consumption_kwh) * 0.15)


def forecast_adjustment_kwh(
    expected_consumption_kwh: float,
    forecast: ForecastSummary | None,
) -> float:
    outlook = _forecast_outlook(forecast)

    if outlook == "good":
        return 0.0

    if outlook == "mixed":
        return min(0.75, float(expected_consumption_kwh) * 0.05)

    if outlook == "poor":
        return min(0.75, float(expected_consumption_kwh) * 0.15)

    return 0.0


def compute_required_charge_energy_kwh(
    expected_consumption_kwh: float,
    reserve_kwh: float,
    forecast_adjustment: float,
    available_energy_kwh: float,
    max_chargeable_kwh: float,
) -> tuple[float, float]:
    raw = (
        float(expected_consumption_kwh)
        + float(reserve_kwh)
        + float(forecast_adjustment)
        - float(available_energy_kwh)
    )

    required = _clamp(raw, 0.0, float(max_chargeable_kwh))
    return float(raw), float(required)


def learned_typical_charge_power_w(
    samples: list[LearningChargePowerSample],
    now: datetime,
    rolling_days: int = ROLLING_DAYS,
) -> float | None:
    """Estimate a realistic learned AC charge power from recent charge samples.

    Uses the median to avoid spikes and short unstable phases.
    """

    if not samples:
        return None

    now_local = _as_local(now)
    window_start = now_local - timedelta(days=max(1, int(rolling_days)))

    values: list[float] = []

    for sample in samples:
        ts = _as_local(sample.ts)

        if ts < window_start or ts > now_local:
            continue

        power = float(sample.power_w or 0.0)

        # Ignore tiny keepalive / soft-start / noise values.
        if power < MIN_LEARNED_CHARGE_POWER_SAMPLE_W:
            continue

        values.append(power)

    if len(values) < MIN_LEARNED_CHARGE_POWER_SAMPLES:
        return None

    return round(float(statistics.median(values)), 1)
    

def effective_charge_power_w(
    profile_charge_limit_w: float,
    learned_typical_charge_power_w: float | None,
    current_effective_charge_cap_w: float,
) -> float:
    candidates = [
        max(0.0, float(profile_charge_limit_w or 0.0)),
        max(0.0, float(current_effective_charge_cap_w or 0.0)),
    ]

    if learned_typical_charge_power_w is not None and learned_typical_charge_power_w > 0:
        candidates.append(float(learned_typical_charge_power_w))
    else:
        candidates.append(DEFAULT_FALLBACK_CHARGE_POWER_W)

    power = min(v for v in candidates if v > 0) if any(v > 0 for v in candidates) else 0.0
    return max(0.0, float(power))


def compute_window_slots(
    required_charge_energy_kwh: float,
    effective_charge_power_w_value: float,
) -> tuple[int, int]:
    if required_charge_energy_kwh <= 0:
        return 0, 0

    effective_kw = float(effective_charge_power_w_value or 0.0) / 1000.0
    if effective_kw <= 0:
        return 0, 0

    base_window_minutes = (float(required_charge_energy_kwh) / effective_kw) * 60.0
    base_window_slots = int(math.ceil(base_window_minutes / SLOT_MINUTES))

    safety_slots = 1 if base_window_minutes <= 60.0 else 2
    effective_slots = max(2, base_window_slots + safety_slots)

    # Safety cap: prevent unrealistic all-night windows from conservative fallback power.
    effective_slots = min(effective_slots, 20)

    return effective_slots, effective_slots * SLOT_MINUTES


def choose_deadline(
    now: datetime,
    price_points: list[PricePoint],
    forecast: ForecastSummary | None,
) -> tuple[datetime, str]:
    """Choose one active planning deadline.

    V4.1.0 priority:
    1. next relevant peak window
    2. forecast-critical period
    3. typical morning load
    4. default overnight target
    """

    now_local = _as_local(now)

    future_prices = [
        p for p in price_points
        if _as_local(p.start) > now_local and _as_local(p.end) > now_local
    ]

    if future_prices:
        prices = [float(p.price) for p in future_prices]
        avg_price = sum(prices) / len(prices)
        peak_threshold = max(avg_price * 1.35, avg_price + 0.03)

        peak_candidates = [
            p for p in future_prices
            if float(p.price) >= peak_threshold
        ]

        if peak_candidates:
            first_peak = min(peak_candidates, key=lambda p: _as_local(p.start))
            return _as_local(first_peak.start), DEADLINE_REASON_BEFORE_PEAK_WINDOW

    outlook = _forecast_outlook(forecast)
    if outlook == "poor":
        # Conservative V4.1 start of forecast-critical period.
        forecast_deadline = now_local + timedelta(hours=3)
        return forecast_deadline, DEADLINE_REASON_BEFORE_POOR_FORECAST_PERIOD

    tomorrow = now_local.date()
    morning_deadline = datetime.combine(tomorrow, time(6, 0))
    morning_deadline = morning_deadline.replace(
        tzinfo=dt_util.get_default_time_zone(),
    )

    if morning_deadline <= now_local:
        morning_deadline += timedelta(days=1)

    if now_local.hour < 10:
        return morning_deadline, DEADLINE_REASON_BEFORE_TYPICAL_MORNING_LOAD

    fallback = datetime.combine(now_local.date() + timedelta(days=1), time(6, 0))
    fallback = fallback.replace(
        tzinfo=dt_util.get_default_time_zone(),
    )

    return fallback, DEADLINE_REASON_DEFAULT_OVERNIGHT_TARGET


def optimize_charge_window(
    now: datetime,
    deadline: datetime,
    price_points: list[PricePoint],
    window_slots: int,
) -> tuple[datetime | None, datetime | None, float | None, list[float], list[float], str | None]:
    """Find the best charge window using normalized triangle weights."""

    if window_slots <= 0:
        return None, None, None, [], [], LEARNED_REASON_NO_CHARGE_NEEDED

    now_local = _as_local(now)
    deadline_local = _as_local(deadline)

    if deadline_local <= now_local:
        return now_local, now_local, None, [], [], LEARNED_REASON_DEADLINE_TOO_CLOSE_START_NOW

    future = [
        p for p in price_points
        if _as_local(p.end) > now_local and _as_local(p.start) < deadline_local
    ]
    future.sort(key=lambda p: _as_local(p.start))

    if len(future) < window_slots:
        return (
            now_local,
            now_local + timedelta(minutes=window_slots * SLOT_MINUTES),
            None,
            [],
            [],
            LEARNED_REASON_DEADLINE_TOO_CLOSE_START_NOW,
        )

    weights = _triangle_weights(window_slots)

    best_start: datetime | None = None
    best_end: datetime | None = None
    best_score: float | None = None
    best_prices: list[float] = []

    for idx in range(0, len(future) - window_slots + 1):
        window = future[idx: idx + window_slots]
        start = _as_local(window[0].start)
        end = _as_local(window[-1].end)

        # A charge window that has already started but is still active must remain
        # eligible. The plan is rebuilt regularly, so rejecting every window whose
        # start lies a few seconds in the past would continuously move the planned
        # start into the future and prevent charging from ever becoming active.
        if end <= now_local:
            continue

        if end > deadline_local:
            continue

        prices = [float(p.price) for p in window]
        score = sum(price * weight for price, weight in zip(prices, weights))

        if best_score is None or score < best_score:
            best_score = score
            best_start = start
            best_end = end
            best_prices = prices
        elif best_score is not None and math.isclose(score, best_score, rel_tol=0.0, abs_tol=0.000001):
            # Tie breaker: later start wins.
            if best_start is None or start > best_start:
                best_score = score
                best_start = start
                best_end = end
                best_prices = prices

    if best_start is None or best_end is None:
        return (
            now_local,
            now_local + timedelta(minutes=window_slots * SLOT_MINUTES),
            None,
            weights,
            [],
            LEARNED_REASON_DEADLINE_TOO_CLOSE_START_NOW,
        )

    return best_start, best_end, best_score, weights, best_prices, None


def build_learned_charge_plan(
    model: LearnedSlotModel,
    readiness: LearningReadiness,
    now: datetime,
    price_points: list[PricePoint],
    forecast: ForecastSummary | None,
    total_battery_capacity_kwh: float,
    current_soc: float,
    soc_min: float,
    soc_max: float,
    profile_charge_limit_w: float,
    current_effective_charge_cap_w: float,
    learned_typical_charge_power_w: float | None = None,
    force_active: bool = False,
) -> LearnedChargePlan:
    """Build a complete learned charge plan summary.

    Important:
    - If readiness is not ready, the function still calculates diagnostic values.
    - In that case, mode stays classic_fallback and the plan must not actively control charging.
    """

    diagnostics_only = not readiness.ready

    if diagnostics_only and model.history_days <= 0:
        return LearnedChargePlan(
            status=readiness.status,
            mode=LEARNED_MODE_CLASSIC_FALLBACK,
            blocking_reason=readiness.blocking_reason,
            decision_reason=LEARNED_REASON_NOT_READY,
        )

    deadline, deadline_reason = choose_deadline(
        now=now,
        price_points=price_points,
        forecast=forecast,
    )

    expected_kwh = expected_consumption_until(
        model=model,
        now=now,
        deadline=deadline,
    )

    available_kwh = available_battery_energy_kwh(
        total_battery_capacity_kwh=total_battery_capacity_kwh,
        current_soc=current_soc,
        soc_min=soc_min,
    )

    chargeable_kwh = max_chargeable_energy_kwh(
        total_battery_capacity_kwh=total_battery_capacity_kwh,
        current_soc=current_soc,
        soc_max=soc_max,
    )

    reserve_kwh = reserve_margin_kwh(expected_kwh)
    forecast_kwh = forecast_adjustment_kwh(expected_kwh, forecast)

    raw_required_kwh, required_kwh = compute_required_charge_energy_kwh(
        expected_consumption_kwh=expected_kwh,
        reserve_kwh=reserve_kwh,
        forecast_adjustment=forecast_kwh,
        available_energy_kwh=available_kwh,
        max_chargeable_kwh=chargeable_kwh,
    )

    eff_power_w = effective_charge_power_w(
        profile_charge_limit_w=profile_charge_limit_w,
        learned_typical_charge_power_w=learned_typical_charge_power_w,
        current_effective_charge_cap_w=current_effective_charge_cap_w,
    )

    if required_kwh <= 0.0:
        return LearnedChargePlan(
            status=readiness.status if diagnostics_only else (
                LEARNED_STATUS_ACTIVE if force_active else readiness.status
            ),
            mode=LEARNED_MODE_CLASSIC_FALLBACK if diagnostics_only else LEARNED_MODE_READY,
            blocking_reason=readiness.blocking_reason if diagnostics_only else None,
            expected_consumption_kwh=round(expected_kwh, 3),
            available_battery_energy_kwh=round(available_kwh, 3),
            reserve_margin_kwh=round(reserve_kwh, 3),
            forecast_adjustment_kwh=round(forecast_kwh, 3),
            raw_required_charge_energy_kwh=round(raw_required_kwh, 3),
            required_charge_energy_kwh=0.0,
            max_chargeable_energy_kwh=round(chargeable_kwh, 3),
            effective_charge_power_w=round(eff_power_w, 1),
            planning_deadline=deadline,
            deadline_reason=deadline_reason,
            decision_reason=LEARNED_REASON_NOT_READY if diagnostics_only else LEARNED_REASON_NO_CHARGE_NEEDED,
        )

    window_slots, window_minutes = compute_window_slots(
        required_charge_energy_kwh=required_kwh,
        effective_charge_power_w_value=eff_power_w,
    )

    if window_slots <= 0 or eff_power_w < MIN_EFFECTIVE_CHARGE_POWER_W:
        return LearnedChargePlan(
            status=readiness.status,
            mode=LEARNED_MODE_CLASSIC_FALLBACK,
            blocking_reason="effective_charge_power_too_low",
            expected_consumption_kwh=round(expected_kwh, 3),
            available_battery_energy_kwh=round(available_kwh, 3),
            reserve_margin_kwh=round(reserve_kwh, 3),
            forecast_adjustment_kwh=round(forecast_kwh, 3),
            raw_required_charge_energy_kwh=round(raw_required_kwh, 3),
            required_charge_energy_kwh=round(required_kwh, 3),
            max_chargeable_energy_kwh=round(chargeable_kwh, 3),
            effective_charge_power_w=round(eff_power_w, 1),
            effective_window_slots=int(window_slots),
            effective_window_minutes=int(window_minutes),
            planning_deadline=deadline,
            deadline_reason=deadline_reason,
            decision_reason=LEARNED_REASON_NOT_READY,
        )

    start, end, score, weights, selected_prices, optimizer_reason = optimize_charge_window(
        now=now,
        deadline=deadline,
        price_points=price_points,
        window_slots=window_slots,
    )

    now_local = _as_local(now)

    if optimizer_reason in (
        LEARNED_REASON_DEADLINE_TOO_CLOSE_START_NOW,
        LEARNED_REASON_LATEST_START_REACHED,
    ):
        mode = LEARNED_MODE_CHARGE
        decision_reason = optimizer_reason
    elif start is not None and now_local >= start:
        mode = LEARNED_MODE_CHARGE
        decision_reason = LEARNED_REASON_ACTIVE
    else:
        mode = LEARNED_MODE_WAIT
        decision_reason = LEARNED_REASON_WAIT

    if diagnostics_only:
        mode = LEARNED_MODE_CLASSIC_FALLBACK
        decision_reason = LEARNED_REASON_NOT_READY
        blocking_reason = readiness.blocking_reason
        status = readiness.status
    else:
        blocking_reason = None
        status = LEARNED_STATUS_ACTIVE if force_active else readiness.status

    return LearnedChargePlan(
        status=status,
        mode=mode,
        blocking_reason=blocking_reason,
        expected_consumption_kwh=round(expected_kwh, 3),
        available_battery_energy_kwh=round(available_kwh, 3),
        reserve_margin_kwh=round(reserve_kwh, 3),
        forecast_adjustment_kwh=round(forecast_kwh, 3),
        raw_required_charge_energy_kwh=round(raw_required_kwh, 3),
        required_charge_energy_kwh=round(required_kwh, 3),
        max_chargeable_energy_kwh=round(chargeable_kwh, 3),
        effective_charge_power_w=round(eff_power_w, 1),
        effective_window_slots=int(window_slots),
        effective_window_minutes=int(window_minutes),
        planning_deadline=deadline,
        deadline_reason=deadline_reason,
        optimal_charge_start=start,
        optimal_charge_end=end,
        window_score=round(float(score), 6) if score is not None else None,
        decision_reason=decision_reason,
        bell_weights=weights,
        selected_prices=selected_prices,
    )