"""Parser adapter implementations.

All adapters are automatically registered by ``registry._build_default_registry()``.
This module exposes them for direct import convenience.
"""

from src.parsers.adapters.quest import QuestParser
from src.parsers.adapters.labcorp import LabcorpParser
from src.parsers.adapters.insidetracker import InsideTrackerParser
from src.parsers.adapters.function_health import FunctionHealthParser
from src.parsers.adapters.dexafit import DexaFitParser
from src.parsers.adapters.bodyspec import BodySpecParser
from src.parsers.adapters.dexa_generic import DexaGenericParser
from src.parsers.adapters.trudiagnostic import TruDiagnosticParser
from src.parsers.adapters.elysium import ElysiumParser
from src.parsers.adapters.epi_generic import EpigeneticGenericParser
from src.parsers.adapters.generic import GenericAIParser

__all__ = [
    "QuestParser",
    "LabcorpParser",
    "InsideTrackerParser",
    "FunctionHealthParser",
    "DexaFitParser",
    "BodySpecParser",
    "DexaGenericParser",
    "TruDiagnosticParser",
    "ElysiumParser",
    "EpigeneticGenericParser",
    "GenericAIParser",
]
