from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Iterable

from .regulation_models import GridHistoryState


DEFAULT_GRID_HISTORY_SHORT_SAMPLES = 3
DEFAULT_GRID_HISTORY_MEDIUM_SAMPLES = 6
DEFAULT_GRID_HISTORY_MAX_SAMPLES = 12

# Fallback / hard limit for large changes.
DEFAULT_FAST_LOAD_CHANGE_W = 600.0

# ZHA-inspired statistical fast-change detection.
# A change is considered "fast" when it clearly deviates from the recent
# medium history. The hard watt limit remains active as a safe fallback.
DEFAULT_FAST_LOAD_STDDEV_FACTOR = 3.5
DEFAULT_FAST_LOAD_STDDEV_MIN_W = 15.0

DEFAULT_TARGET_IMPORT_W = 10.0
DEFAULT_NEAR_TARGET_BAND_W = 40.0
DEFAULT_STABLE_IMPORT_THRESHOLD_W = 60.0
DEFAULT_STABLE_EXPORT_THRESHOLD_W = 60.0


@dataclass
class GridHistoryConfig:
    short_samples: int = DEFAULT_GRID_HISTORY_SHORT_SAMPLES
    medium_samples: int = DEFAULT_GRID_HISTORY_MEDIUM_SAMPLES
    max_samples: int = DEFAULT_GRID_HISTORY_MAX_SAMPLES

    fast_load_change_w: float = DEFAULT_FAST_LOAD_CHANGE_W
    fast_load_stddev_factor: float = DEFAULT_FAST_LOAD_STDDEV_FACTOR
    fast_load_stddev_min_w: float = DEFAULT_FAST_LOAD_STDDEV_MIN_W

    target_import_w: float = DEFAULT_TARGET_IMPORT_W
    near_target_band_w: float = DEFAULT_NEAR_TARGET_BAND_W

    stable_import_threshold_w: float = DEFAULT_STABLE_IMPORT_THRESHOLD_W
    stable_export_threshold_w: float = DEFAULT_STABLE_EXPORT_THRESHOLD_W


class GridHistory:
    """Short signed grid history.

    Internal convention:
    grid_power_w > 0 = Netzbezug
    grid_power_w < 0 = Einspeisung

    The history is intentionally short. It is not meant to slow down power
    regulation. It gives the ModeArbiter context for stable mode changes and
    gives the PowerController a short average for smoother target calculation.

    V4.2.0:
    Fast load changes are detected using both a hard watt threshold and a
    ZHA-inspired statistical deviation from the recent medium history.
    """

    def __init__(self, config: GridHistoryConfig | None = None) -> None:
        self.config = config or GridHistoryConfig()

        max_len = max(
            1,
            int(self.config.max_samples),
            int(self.config.short_samples),
            int(self.config.medium_samples),
        )

        self._samples: deque[float] = deque(maxlen=max_len)

        self._stable_import_cycles = 0
        self._stable_export_cycles = 0
        self._near_target_cycles = 0

    def reset(self) -> None:
        self._samples.clear()
        self._stable_import_cycles = 0
        self._stable_export_cycles = 0
        self._near_target_cycles = 0

    def update(
        self,
        *,
        grid_import_w: float,
        grid_export_w: float,
    ) -> GridHistoryState:
        """Add a new sample and return the current history state.

        Args:
            grid_import_w: positive import power from grid
            grid_export_w: positive export power to grid

        Returns:
            GridHistoryState with signed current power, averages and counters.
        """

        import_w = max(0.0, float(grid_import_w or 0.0))
        export_w = max(0.0, float(grid_export_w or 0.0))

        grid_now_w = import_w - export_w

        previous = self._samples[-1] if self._samples else grid_now_w

        # Use the history before appending the new sample for deviation checks.
        # That way a sudden jump is compared against the recent calm baseline.
        previous_medium_values = self._last_values(self.config.medium_samples)
        previous_medium_avg = self._avg_values(previous_medium_values)
        previous_medium_stddev = self._stddev_values(previous_medium_values)

        self._samples.append(grid_now_w)

        short_avg = self._avg_last(self.config.short_samples)
        medium_avg = self._avg_last(self.config.medium_samples)

        grid_delta_w = grid_now_w - previous

        stable_import = grid_now_w >= float(self.config.stable_import_threshold_w)
        stable_export = grid_now_w <= -float(self.config.stable_export_threshold_w)

        if stable_import:
            self._stable_import_cycles += 1
        else:
            self._stable_import_cycles = 0

        if stable_export:
            self._stable_export_cycles += 1
        else:
            self._stable_export_cycles = 0

        target = float(self.config.target_import_w)
        near_band = max(0.0, float(self.config.near_target_band_w))

        if abs(grid_now_w - target) <= near_band:
            self._near_target_cycles += 1
        else:
            self._near_target_cycles = 0

        fast_load_rise_detected, fast_load_drop_detected = (
            self._detect_fast_load_change(
                grid_now_w=grid_now_w,
                grid_delta_w=grid_delta_w,
                previous_medium_avg=previous_medium_avg,
                previous_medium_stddev=previous_medium_stddev,
                previous_sample_count=len(previous_medium_values),
            )
        )

        return GridHistoryState(
            grid_now_w=round(float(grid_now_w), 2),
            grid_avg_short_w=round(float(short_avg), 2),
            grid_avg_medium_w=round(float(medium_avg), 2),
            grid_delta_w=round(float(grid_delta_w), 2),
            stable_import_cycles=int(self._stable_import_cycles),
            stable_export_cycles=int(self._stable_export_cycles),
            near_target_cycles=int(self._near_target_cycles),
            fast_load_rise_detected=bool(fast_load_rise_detected),
            fast_load_drop_detected=bool(fast_load_drop_detected),
            post_load_drop_hold_active=False,
            post_output_overshoot_hold_active=False,
        )

    def _detect_fast_load_change(
        self,
        *,
        grid_now_w: float,
        grid_delta_w: float,
        previous_medium_avg: float,
        previous_medium_stddev: float,
        previous_sample_count: int,
    ) -> tuple[bool, bool]:
        """Detect sudden load changes.

        Uses two mechanisms:
        1. Hard watt threshold for very large jumps.
        2. Statistical deviation from recent medium history, inspired by the
           Zendure-HA/ZHA P1-style approach.

        Rise:
            grid value moves strongly upward, e.g. more import or less export.

        Drop:
            grid value moves strongly downward, e.g. less import or more export.
        """

        hard_limit = max(0.0, float(self.config.fast_load_change_w))

        hard_rise = grid_delta_w >= hard_limit
        hard_drop = grid_delta_w <= -hard_limit

        # Statistical detection only makes sense with at least a few previous
        # samples. Otherwise the hard threshold is enough.
        if previous_sample_count < 3:
            return bool(hard_rise), bool(hard_drop)

        stddev_min = max(0.0, float(self.config.fast_load_stddev_min_w))
        stddev_factor = max(0.1, float(self.config.fast_load_stddev_factor))

        dynamic_limit = max(
            stddev_min,
            previous_medium_stddev * stddev_factor,
        )

        deviation_from_recent_avg = grid_now_w - previous_medium_avg

        statistical_rise = deviation_from_recent_avg >= dynamic_limit
        statistical_drop = deviation_from_recent_avg <= -dynamic_limit

        return (
            bool(hard_rise or statistical_rise),
            bool(hard_drop or statistical_drop),
        )

    def _avg_last(self, count: int) -> float:
        return self._avg_values(self._last_values(count))

    def _last_values(self, count: int) -> list[float]:
        count = max(1, int(count or 1))
        return list(self._samples)[-count:]

    def _avg_values(self, values: Iterable[float]) -> float:
        values_list = list(values)
        if not values_list:
            return 0.0

        return sum(values_list) / len(values_list)

    def _stddev_values(self, values: Iterable[float]) -> float:
        values_list = list(values)
        if len(values_list) < 2:
            return 0.0

        avg = self._avg_values(values_list)
        variance = sum((value - avg) ** 2 for value in values_list) / len(values_list)
        return math.sqrt(max(0.0, variance))

    @property
    def samples(self) -> tuple[float, ...]:
        return tuple(self._samples)


def build_grid_history_config(profile: dict) -> GridHistoryConfig:
    """Build GridHistoryConfig from a device profile.

    Missing profile values fall back to conservative defaults.
    """

    def _profile_float(key: str, default: float) -> float:
        try:
            return float(profile.get(key, default))
        except Exception:
            return float(default)

    def _profile_int(key: str, default: int) -> int:
        try:
            return int(profile.get(key, default))
        except Exception:
            return int(default)

    target_import_w = _profile_float("TARGET_IMPORT_W", DEFAULT_TARGET_IMPORT_W)

    # For "near target" we use the discharge deadband if available, otherwise
    # the legacy DEADBAND_W, otherwise a safe default.
    near_target_band_w = _profile_float(
        "DISCHARGE_DEADBAND_W",
        _profile_float("DEADBAND_W", DEFAULT_NEAR_TARGET_BAND_W),
    )

    return GridHistoryConfig(
        short_samples=_profile_int(
            "GRID_HISTORY_SHORT_SAMPLES",
            DEFAULT_GRID_HISTORY_SHORT_SAMPLES,
        ),
        medium_samples=_profile_int(
            "GRID_HISTORY_MEDIUM_SAMPLES",
            DEFAULT_GRID_HISTORY_MEDIUM_SAMPLES,
        ),
        max_samples=_profile_int(
            "GRID_HISTORY_MAX_SAMPLES",
            DEFAULT_GRID_HISTORY_MAX_SAMPLES,
        ),
        fast_load_change_w=_profile_float(
            "FAST_LOAD_CHANGE_W",
            DEFAULT_FAST_LOAD_CHANGE_W,
        ),
        fast_load_stddev_factor=_profile_float(
            "FAST_LOAD_STDDEV_FACTOR",
            DEFAULT_FAST_LOAD_STDDEV_FACTOR,
        ),
        fast_load_stddev_min_w=_profile_float(
            "FAST_LOAD_STDDEV_MIN_W",
            DEFAULT_FAST_LOAD_STDDEV_MIN_W,
        ),
        target_import_w=target_import_w,
        near_target_band_w=max(20.0, near_target_band_w),
        stable_import_threshold_w=max(40.0, target_import_w + near_target_band_w),
        stable_export_threshold_w=max(40.0, near_target_band_w),
    )