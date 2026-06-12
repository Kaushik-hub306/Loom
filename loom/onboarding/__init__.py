"""Loom onboarding — instant onboarding and succession knowledge capture."""

from .packs import OnboardingPack, OnboardingManager
from .succession import SuccessionSession, SuccessionManager

# Public alias — the user-facing name for a succession capture session.
SuccessionCapture = SuccessionSession

__all__ = ["OnboardingPack", "OnboardingManager", "SuccessionCapture", "SuccessionManager"]
