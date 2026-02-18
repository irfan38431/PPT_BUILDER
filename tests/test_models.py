"""Smoke tests for core data models."""

import os

# Provide dummy key before any config import
os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key")

from models import PipelineState, SlidePlan, ResearchFinding, ChartData, ChartDataset


def test_pipeline_state_defaults():
    state = PipelineState()
    assert state.status == "idle"
    assert state.output_file is None
    assert state.output_gcs_uri is None
    assert state.errors == []


def test_pipeline_state_gcs_uri():
    state = PipelineState(output_gcs_uri="gs://my-bucket/presentations/test.pptx")
    assert state.output_gcs_uri == "gs://my-bucket/presentations/test.pptx"


def test_slide_plan_creation():
    plan = SlidePlan(id=1, title="Test", layout_type="bullet")
    assert plan.id == 1
    assert plan.status == "planned"
    assert plan.user_locked is False


def test_research_finding():
    finding = ResearchFinding(
        topic="AI Trends",
        content="AI is growing rapidly",
        sources=["https://example.com"],
        confidence=0.9,
    )
    assert finding.confidence == 0.9
    assert len(finding.sources) == 1


def test_chart_data_with_datasets():
    chart = ChartData(
        title="Revenue",
        chart_type="bar",
        labels=["Q1", "Q2"],
        datasets=[ChartDataset(label="2025", data=[100, 200])],
    )
    assert len(chart.datasets) == 1
    assert chart.datasets[0].data == [100, 200]
