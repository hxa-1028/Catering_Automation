"""Bounded proposal-pipeline orchestration."""

from catering_agent.agent.menu_selection import MenuSelectionResult
from catering_agent.agent.pipeline import (
    PipelineRequest,
    PipelineResult,
    run_pipeline,
)

__all__ = ["MenuSelectionResult", "PipelineRequest", "PipelineResult", "run_pipeline"]
