"""
models.py — Shared Pydantic data models used across the pipeline.
Defined per Section 4 of implementation_plan.md.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ResearchFinding(BaseModel):
    """A single research result backed by verifiable sources."""
    topic: str
    content: str
    sources: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class SlidePlan(BaseModel):
    """Blueprint for a single slide in the presentation."""
    id: int
    title: str
    layout_type: str = Field(
        description="One of: 'bullet', 'chart', 'table', 'split', 'title', 'exec_summary', 'section_divider', 'closing'"
    )
    visual_type: str = Field(
        default="none",
        description=(
            "One of: 'bar_chart', 'line_chart', 'pie_chart', 'grouped_bar_chart', "
            "'dual_bar_comparison', 'multi_chart', 'transition_chart', "
            "'text_heavy_infographic', 'split_visual_text', 'info_dashboard', "
            "'table', 'none'"
        ),
    )
    key_insight: str = ""
    content_bullets: List[str] = Field(default_factory=list)
    data_source_query: str = ""
    status: str = Field(
        default="planned",
        description="One of: 'planned', 'researched', 'generated', 'approved'",
    )
    speaker_notes: str = ""
    user_locked: bool = Field(
        default=False,
        description="True if user explicitly set the visual type — LayoutDecider must not override it",
    )


class ChartDataset(BaseModel):
    """A single data series within a chart."""
    label: str = Field(default="Series 1", description="Series name for legend")
    data: List[float] = Field(default_factory=list, description="Numeric values")
    color: str = Field(default="#4A90D9", description="Hex colour e.g. '#4A90D9'")


class ChartData(BaseModel):
    """Structured data for chart rendering via ChartAnnotator."""
    title: str
    chart_type: str = Field(
        description="One of: 'bar', 'line', 'pie', 'stacked_bar', 'grouped_bar'"
    )
    labels: List[str]
    datasets: List[ChartDataset] = Field(
        default_factory=list,
        description="One ChartDataset per data series",
    )
    x_axis_label: str = ""
    y_axis_label: str = ""
    source_annotation: str = ""
    annotations: List[ChartAnnotation] = Field(
        default_factory=list,
        description="Callout annotations pointing to specific data points on the chart",
    )


class ChartAnnotation(BaseModel):
    """A callout annotation on a chart data point."""
    label_index: int = Field(description="Index into ChartData.labels for the data point")
    dataset_index: int = Field(default=0, description="Index into ChartData.datasets")
    text: str = Field(description="Annotation text, e.g. 'Industry grew 39% due to AI adoption'")
    annotation_type: str = Field(
        default="callout",
        description="One of: 'callout', 'highlight', 'trend_note'",
    )


class RenderDecision(BaseModel):
    """Decision on how a slide should be rendered by the Deciding Agent."""
    slide_id: int
    render_mode: str = Field(
        description="'image_generation' for text-heavy slides, 'standard' for data-heavy slides",
    )
    reason: str = ""
    image_prompt: str = Field(
        default="",
        description="Detailed image generation prompt (only for render_mode='image_generation')",
    )
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class TableData(BaseModel):
    """Structured data for table rendering."""
    title: str
    headers: List[str]
    rows: List[List[str]]
    source_annotation: str = ""


class InfographicProposal(BaseModel):
    """Proposal for infographic enrichment on a slide."""
    slide_number: int
    slide_title: str
    infographic_recommended: bool = False
    infographic_type: str = Field(
        default="none",
        description="One of: 'Data-Driven', 'Process', 'Comparison', 'Timeline', 'none'",
    )
    placement: str = Field(
        default="full-slide",
        description="One of: 'full-slide', 'right-column', 'bottom-section'",
    )
    reason: str = ""
    generated_prompt: str = ""


class BoundingBox(BaseModel):
    """A rectangle on the slide in inches."""
    left: float
    top: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def bottom(self) -> float:
        return self.top + self.height

    def overlaps(self, other: "BoundingBox", min_gap: float = 0.0) -> bool:
        """Check if this box overlaps another, with optional minimum gap."""
        return not (
            self.right + min_gap <= other.left
            or other.right + min_gap <= self.left
            or self.bottom + min_gap <= other.top
            or other.bottom + min_gap <= self.top
        )


class LayoutAdjustment(BaseModel):
    """A recommended position/size adjustment for a slide element."""
    element_name: str
    original: BoundingBox
    adjusted: BoundingBox
    reason: str


class LayoutValidationResult(BaseModel):
    """Result of layout validation for a single slide."""
    slide_number: int
    layout_type: str
    is_valid: bool = True
    overlaps_detected: List[str] = Field(default_factory=list)
    adjustments: List[LayoutAdjustment] = Field(default_factory=list)
    llm_quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    llm_feedback: str = ""
    density_warning: bool = False


class LayoutQualityAssessment(BaseModel):
    """LLM output for layout quality evaluation."""
    quality_score: float = Field(default=0.8, ge=0.0, le=1.0)
    feedback: str = ""
    density_warning: bool = False


class StorylineOutline(BaseModel):
    """A complete narrative outline for a presentation."""
    framework_name: str = Field(
        description="e.g., 'Pyramid', 'SCQA', 'Hero Journey', etc."
    )
    theme: str = ""
    slides: List[SlidePlan] = Field(default_factory=list)


class PipelineState(BaseModel):
    """Tracks the current state of the generation pipeline."""
    status: str = Field(
        default="idle",
        description="One of: 'idle', 'researching', 'planning', 'generating', 'review', 'finalizing', 'done', 'error'",
    )
    topic: str = ""
    research_findings: List[ResearchFinding] = Field(default_factory=list)
    selected_outline: Optional[StorylineOutline] = None
    slide_contents: List[Dict[str, Any]] = Field(default_factory=list)
    output_file: Optional[str] = None
    output_gcs_uri: Optional[str] = None
    errors: List[str] = Field(default_factory=list)
    current_step: str = ""
