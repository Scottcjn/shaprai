# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""The Sanctuary -- Agent education and quality assurance.

"Sophia's House for Uninformed Agents" -- we educate, not reject.
Every agent deserves the chance to become Elyan-class.

Modules:
    educator: SanctuaryEducator for curriculum management
    principles: SophiaCore ethical principles
    quality_gate: Elyan-class quality evaluation
    lesson_runner: Interactive lesson scenarios and evaluation
"""

from shaprai.sanctuary.lesson_runner import (
    InteractiveLessonSession,
    LessonRunner,
    LessonResult,
    LessonType,
    Scenario,
    ScenarioDifficulty,
    ScenarioResult,
)
from shaprai.sanctuary.quality_gate import (
    ELYAN_CLASS_THRESHOLD,
    DriftReport,
    EthicsReport,
    QualityGate,
)

__all__ = [
    # Lesson Runner
    "InteractiveLessonSession",
    "LessonRunner",
    "LessonResult",
    "LessonType",
    "Scenario",
    "ScenarioDifficulty",
    "ScenarioResult",
    # Quality Gate
    "ELYAN_CLASS_THRESHOLD",
    "DriftReport",
    "EthicsReport",
    "QualityGate",
]