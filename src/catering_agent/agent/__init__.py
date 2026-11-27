"""Bounded proposal-pipeline orchestration."""

from catering_agent.agent.draft_generation import (
    DraftGenerationError,
    DraftGenerationResult,
    generate_draft,
)
from catering_agent.agent.menu_selection import MenuSelectionResult
from catering_agent.agent.pipeline import (
    PipelineRequest,
    PipelineResult,
    run_pipeline,
)
from catering_agent.rules.pricing import PricingResult

__all__ = [
    "MenuSelectionResult",
    "DraftGenerationError",
    "DraftGenerationResult",
    "PipelineRequest",
    "PipelineResult",
    "PricingResult",
    "run_pipeline",
    "generate_draft",
]
