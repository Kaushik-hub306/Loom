"""Loom onboarding — instant onboarding and succession knowledge capture."""

from .packs import OnboardingManager, OnboardingPack
from .succession import SuccessionManager, SuccessionSession

# Public alias — the user-facing name for a succession capture session.
SuccessionCapture = SuccessionSession

__all__ = ["OnboardingPack", "OnboardingManager", "SuccessionCapture", "SuccessionManager"]
