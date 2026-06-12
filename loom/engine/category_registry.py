"""CategoryRegistry — loads domain/category taxonomy from YAML config files.

Replaces the hardcoded KEYWORD_PATTERNS dict in DomainExtractor with a
data-driven taxonomy that arbitrary domains can extend just by dropping a YAML
file into the config directory.

Each YAML file declares a domain and its categories. Each category has a
``label`` (human-readable name) and a list of ``prompts`` (keywords used for
matching / classification).

Example YAML (``python.yaml``)::

    domain: python
    label: Python
    categories:
      type_safety:
        label: Type Safety
        prompts:
          - "type hints"
          - "mypy"
          - "type annotations"
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class CategoryRegistry:
    """Generalized domain/category registry driven by YAML domain configs.

    Any YAML file in ``config_dir`` is loaded as a domain.  Each domain
    declares its own categories with keyword ``prompts`` used for
    classification and domain detection.
    """

    def __init__(self, config_dir: Path | None = None):
        self._domains: dict[str, dict[str, Any]] = {}

        if config_dir is None:
            return

        config_dir = Path(config_dir)
        if not config_dir.exists():
            return

        for yaml_file in sorted(config_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(yaml_file.read_text()) or {}
            except yaml.YAMLError:
                continue

            domain = data.get("domain", yaml_file.stem)
            label = data.get("label", domain)
            categories_raw = data.get("categories", {})

            categories: dict[str, dict[str, Any]] = {}
            for cat_name, cat_def in categories_raw.items():
                categories[cat_name] = {
                    "label": cat_def.get("label", cat_name),
                    "prompts": cat_def.get("prompts", []),
                }

            self._domains[domain] = {
                "label": label,
                "categories": categories,
            }

    # ── listing ──────────────────────────────────────────────────────────

    def list_domains(self) -> list[str]:
        """Return all loaded domain names."""
        return sorted(self._domains.keys())

    def list_categories(self, domain: str) -> list[str]:
        """Return category names for a domain."""
        info = self._domains.get(domain)
        if info is None:
            return []
        return sorted(info["categories"].keys())

    def get_category_label(self, domain: str, category: str) -> str | None:
        """Return the human-readable label for a domain/category pair."""
        info = self._domains.get(domain)
        if info is None:
            return None
        cat = info["categories"].get(category)
        if cat is None:
            return None
        return cat["label"]

    def get_prompts(self, domain: str, category: str) -> list[str]:
        """Return the prompt/keyword list for a domain/category pair."""
        info = self._domains.get(domain)
        if info is None:
            return []
        cat = info["categories"].get(category)
        if cat is None:
            return []
        return list(cat["prompts"])

    # ── detection ────────────────────────────────────────────────────────

    def detect_domain(self, feedback: str) -> dict[str, Any] | None:
        """Detect which domain this feedback belongs to.

        Returns a dict with ``domain``, ``confidence`` (0.0-1.0), and
        ``suggested_categories``, or ``None`` when no domain matches.
        """
        feedback_lower = feedback.lower()
        best_domain: str | None = None
        best_score = 0
        best_categories: list[str] = []

        for domain, info in self._domains.items():
            score = 0
            matched_cats: list[str] = []
            for cat_name, cat_info in info["categories"].items():
                for prompt in cat_info["prompts"]:
                    if prompt.lower() in feedback_lower:
                        score += 1
                        if cat_name not in matched_cats:
                            matched_cats.append(cat_name)

            if score > best_score:
                best_score = score
                best_domain = domain
                best_categories = matched_cats

        if best_domain is None:
            return None

        # Normalize confidence: each prompt match contributes 0.1, capped at 1.0
        confidence = min(1.0, best_score * 0.1)
        return {
            "domain": best_domain,
            "confidence": confidence,
            "suggested_categories": best_categories,
        }

    # ── classification ───────────────────────────────────────────────────

    def classify(self, domain: str, feedback: str) -> dict[str, int] | None:
        """Return a dict mapping category name to match-score for *domain*.

        Returns ``None`` or an empty dict when the domain is unknown.
        """
        info = self._domains.get(domain)
        if info is None:
            return None

        feedback_lower = feedback.lower() if feedback else ""
        scores: dict[str, int] = {}

        for cat_name, cat_info in info["categories"].items():
            cat_score = 0
            for prompt in cat_info["prompts"]:
                if prompt.lower() in feedback_lower:
                    cat_score += 1
            scores[cat_name] = cat_score

        return scores
