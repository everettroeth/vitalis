"""Menstrual cycle tracking for Vitalis.

This subpackage implements temperature-assisted cycle prediction, ovulation
detection, and symptom correlation.  All data is treated as GDPR special
category data — opt-in only, excluded from household sharing.

Modules:
    cycle_tracker      — Cycle prediction engine (calendar + temperature)
    temp_ovulation     — Temperature shift detection for ovulation
    symptom_correlator — Correlate symptoms with phase + wearable metrics
"""

from src.wearables.menstrual.cycle_tracker import CycleTracker, CyclePrediction
from src.wearables.menstrual.temp_ovulation import TempOvulationDetector, OvulationDetectionResult
from src.wearables.menstrual.symptom_correlator import SymptomCorrelator, SymptomInsight

__all__ = [
    "CycleTracker",
    "CyclePrediction",
    "TempOvulationDetector",
    "OvulationDetectionResult",
    "SymptomCorrelator",
    "SymptomInsight",
]
