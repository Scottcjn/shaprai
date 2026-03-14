# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""ShaprAI core modules -- template engine, lifecycle, governance, fleet, driftlock."""

from shaprai.core.driftlock import (
    DriftLock,
    DriftLockConfig,
    DriftLockResult,
    create_driftlock_from_template,
    DEFAULT_WINDOW_SIZE,
    DEFAULT_DRIFT_THRESHOLD,
)

from shaprai.core.driftlock_stress_test import (
    DriftLockStressTester,
    StressTestResult,
    DEFAULT_TURNS,
)

__all__ = [
    "DriftLock",
    "DriftLockConfig",
    "DriftLockResult",
    "create_driftlock_from_template",
    "DEFAULT_WINDOW_SIZE",
    "DEFAULT_DRIFT_THRESHOLD",
    # Stress test modules
    "DriftLockStressTester",
    "StressTestResult",
    "DEFAULT_TURNS",
]
