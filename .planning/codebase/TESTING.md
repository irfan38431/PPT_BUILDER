# Testing Patterns

**Analysis Date:** 2026-03-27

## Current Testing Status

**⚠️ No Tests Exist**

The PPT Builder codebase currently has **zero test files**. This is confirmed by:
- Absence of `pytest.ini`, `setup.cfg`, or test configuration files
- Glob search for `*test*.py` files returned no results
- CLAUDE.md explicitly states: "There are no tests in this codebase"

This represents a significant quality gap that should be addressed.

## Test Infrastructure Present

### No Test Framework Configured
- No `pytest.ini`
- No `conftest.py`
- No `setup.cfg` test sections
- No `tox.ini`

### Dependencies Available for Testing
The `requirements.txt` includes testing-relevant packages that are not yet utilized:
- `pydantic>=2.5.0` — Provides model validation (useful for testing Pydantic models)
- `tenacity>=8.2.0` — Retry logic (can be mocked)

### Recommended Test Framework
**pytest** is the standard Python testing framework and should be adopted:
```bash
# Required additions to requirements.txt
pytest>=8.0.0
pytest-asyncio>=0.23.0
pytest-mock>=3.12.0
```

## CI/CD Configuration

### GitHub Actions Workflow
Located at `.github/workflows/deploy.yml`

```yaml
name: Build & Deploy to Cloud Run

on:
  push:
    branches: [main]
  workflow_dispatch:

env:
  GCP_REGION: ${{ vars.GCP_REGION }}
  GCP_PROJECT_ID: ${{ vars.GCP_PROJECT_ID }}
  IMAGE: ${{ vars.GCP_REGION }}-docker.pkg.dev/${{ vars.GCP_PROJECT_ID }}/ppt-builder/app
```

### Pipeline Steps
1. Checkout code
2. Authenticate to Google Cloud
3. Configure Docker for Artifact Registry
4. Build and push Docker image
5. Deploy to Cloud Run
6. Print service URL

### CI/CD Gaps
- **No test execution** in CI pipeline
- **No lint check** before deployment
- **No security scanning** (e.g., `pip-audit`)
- **No Docker multi-stage hardening** visible

## Recommended Testing Approach

### Test File Organization
```
ppt_builder/
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Shared fixtures
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── test_research_agent.py
│   │   ├── test_slide_content_agent.py
│   │   └── test_layout_decider.py
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── test_llm_provider.py
│   │   └── test_pipeline_logger.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── test_models.py
│   └── generators/
│       ├── __init__.py
│       └── test_themes.py
```

### conftest.py Pattern
```python
# tests/conftest.py
import pytest
from unittest.mock import MagicMock

from config import Settings, get_settings
from engine.llm_provider import LLMProvider
from engine.pipeline_logger import PipelineLogger


@pytest.fixture
def mock_settings():
    """Test settings with dummy API key."""
    return Settings(
        gemini_api_key="test-key-123",
        gemini_flash_model="gemini-test",
        gemini_pro_model="gemini-test",
    )


@pytest.fixture
def mock_llm_provider(mock_settings, mocker):
    """Mock LLM provider for isolated agent testing."""
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value.text = "Test response"
    mocker.patch("google.genai.Client", return_value=mock_client)
    return LLMProvider(mock_settings)


@pytest.fixture
def agent_logger():
    """PipelineLogger for test context."""
    return PipelineLogger("TestAgent")
```

### Unit Test Patterns

#### Testing Agents with Mocked LLM
```python
# tests/agents/test_research_agent.py
import pytest
from unittest.mock import MagicMock, patch

from agents.research_agent import ResearchAgent, DecompositionResult, SubtopicItem
from engine.llm_provider import LLMProvider


class TestResearchAgent:
    """Test suite for ResearchAgent."""

    @pytest.fixture
    def mock_llm(self, mocker):
        """Create a mock LLM provider."""
        mock_llm = MagicMock(spec=LLMProvider)
        mock_llm.generate_structured.return_value = DecompositionResult(
            subtopics=[
                SubtopicItem(
                    title="Market Overview",
                    search_query="global market trends 2024",
                    data_type="text"
                ),
            ]
        )
        return mock_llm

    def test_decompose_topic_returns_subtopics(self, mock_llm):
        """Verify topic decomposition returns valid subtopics."""
        agent = ResearchAgent(llm=mock_llm)
        
        result = agent.decompose_topic(
            topic="Indian Mutual Funds",
            num_subtopics=6
        )
        
        assert len(result) > 0
        assert all(hasattr(item, "title") for item in result)
        assert all(hasattr(item, "search_query") for item in result)

    def test_decompose_topic_with_focus_areas(self, mock_llm):
        """Verify focus areas are prioritized in decomposition."""
        agent = ResearchAgent(llm=mock_llm)
        
        focus_areas = ["SIP performance", "Tax benefits"]
        result = agent.decompose_topic(
            topic="Mutual Funds",
            num_subtopics=6,
            focus_areas=focus_areas
        )
        
        # Verify LLM was called with focus instruction
        mock_llm.generate_structured.assert_called()
```

#### Testing Pydantic Models
```python
# tests/models/test_models.py
import pytest
from pydantic import ValidationError

from models import SlidePlan, ChartData, ChartDataset, PipelineState


class TestSlidePlan:
    """Test suite for SlidePlan model validation."""

    def test_valid_slide_plan(self):
        """Verify valid SlidePlan creates successfully."""
        slide = SlidePlan(
            id=1,
            title="Market Overview",
            layout_type="bullet",
            visual_type="bar_chart"
        )
        
        assert slide.id == 1
        assert slide.title == "Market Overview"
        assert slide.status == "planned"

    def test_default_visual_type(self):
        """Verify default visual type is 'none'."""
        slide = SlidePlan(id=1, title="Title Slide")
        assert slide.visual_type == "none"

    def test_invalid_layout_type_raises(self):
        """Verify invalid layout type raises validation error."""
        with pytest.raises(ValidationError):
            SlidePlan(
                id=1,
                title="Test",
                layout_type="invalid_layout"
            )


class TestChartData:
    """Test suite for ChartData model."""

    def test_chart_with_multiple_datasets(self):
        """Verify chart data with multiple series."""
        chart = ChartData(
            title="Revenue by Region",
            chart_type="bar",
            labels=["Q1", "Q2", "Q3", "Q4"],
            datasets=[
                ChartDataset(label="North", data=[100, 120, 140, 160]),
                ChartDataset(label="South", data=[80, 90, 95, 110]),
            ]
        )
        
        assert len(chart.datasets) == 2
        assert chart.labels == ["Q1", "Q2", "Q3", "Q4"]
```

#### Testing Generators
```python
# tests/generators/test_themes.py
import pytest

from generators.themes import (
    PresentationTheme,
    THEME_CORPORATE_BLUE,
    get_theme,
    BUILTIN_THEMES
)


class TestPresentationTheme:
    """Test suite for theme dataclass."""

    def test_hex_to_rgbcolor_conversion(self):
        """Verify hex to RGBColor property conversion."""
        theme = THEME_CORPORATE_BLUE
        
        # Primary should be navy blue
        assert theme.primary.rgb == (0x1B, 0x2A, 0x4A)

    def test_hex_to_mpl_conversion(self):
        """Verify hex to matplotlib normalized tuple conversion."""
        theme = THEME_CORPORATE_BLUE
        
        # Primary normalized should be (0-1 range)
        r, g, b = theme.mpl_primary
        assert 0 <= r <= 1
        assert 0 <= g <= 1
        assert 0 <= b <= 1

    def test_is_dark_background_detection(self):
        """Verify dark background auto-detection."""
        # Light theme should not be dark
        assert THEME_CORPORATE_BLUE.is_dark_background is False
        
        # Dark theme should be dark
        from generators.themes import THEME_MODERN_EMERALD
        assert THEME_MODERN_EMERALD.is_dark_background is True

    def test_serialization_roundtrip(self):
        """Verify theme serializes and deserializes correctly."""
        original = THEME_CORPORATE_BLUE
        
        serialized = original.to_dict()
        restored = PresentationTheme.from_dict(serialized)
        
        assert restored.name == original.name
        assert restored.primary_hex == original.primary_hex


class TestThemeRegistry:
    """Test suite for theme registry functions."""

    def test_get_theme_valid_name(self):
        """Verify get_theme returns correct theme."""
        theme = get_theme("corporate_blue")
        assert theme.name == "corporate_blue"

    def test_get_theme_invalid_raises(self):
        """Verify get_theme raises ValueError for unknown theme."""
        with pytest.raises(ValueError) as exc_info:
            get_theme("nonexistent_theme")
        
        assert "Unknown theme" in str(exc_info.value)

    def test_all_builtin_themes_valid(self):
        """Verify all builtin themes pass validation."""
        for name, theme in BUILTIN_THEMES.items():
            assert theme.name == name
            assert theme.primary_hex.startswith("#")
            assert len(theme.chart_colors) > 0
```

#### Testing Error Handling
```python
# tests/test_error_handling.py
import pytest
from unittest.mock import MagicMock

from agents.slide_content_agent import SlideContentAgent
from models import SlidePlan


class TestSlideContentAgentErrorHandling:
    """Test suite for error handling patterns."""

    def test_llm_failure_returns_fallback_content(self, mocker):
        """Verify LLM failure returns graceful fallback."""
        mock_llm = MagicMock()
        mock_llm.generate_structured.side_effect = Exception("API Error")
        
        agent = SlideContentAgent(llm=mock_llm)
        slide = SlidePlan(id=1, title="Test Slide")
        
        # Should not raise, should return fallback
        result = agent.generate_content(
            slide=slide,
            research_data="test data"
        )
        
        assert result.title == "Test Slide"
        assert "failed" in result.content_bullets[0].lower()

    def test_invalid_research_data_handled(self, mocker):
        """Verify invalid research data is handled gracefully."""
        mock_llm = MagicMock()
        mock_llm.generate_structured.return_value = MagicMock(
            model_dump=lambda: {"title": "Test", "content_bullets": []}
        )
        
        agent = SlideContentAgent(llm=mock_llm)
        slide = SlidePlan(id=1, title="Test")
        
        # Empty research data should not crash
        result = agent.generate_content(slide, research_data="")
        
        assert result is not None
```

### Integration Test Patterns

#### Testing Agent Integration
```python
# tests/integration/test_pipeline_integration.py
import pytest
from unittest.mock import MagicMock, patch

from orchestrator import PipelineOrchestrator


class TestPipelineOrchestrator:
    """Integration tests for pipeline orchestration."""

    @pytest.fixture
    def orchestrator(self, mocker):
        """Create orchestrator with mocked agents."""
        with patch("orchestrator.LLMProvider"):
            return PipelineOrchestrator()

    def test_orchestrator_initialization(self, orchestrator):
        """Verify orchestrator initializes all agents."""
        assert orchestrator._research_agent is not None
        assert orchestrator._content_agent is not None
        assert orchestrator._llm is not None

    def test_pipeline_state_initialization(self, orchestrator):
        """Verify initial pipeline state."""
        assert orchestrator.state.status == "idle"
        assert orchestrator.state.topic == ""
        assert orchestrator.state.errors == []
```

### Mocking Patterns

#### Mocking External APIs
```python
# Mock Gemini API responses
@pytest.fixture
def mock_gemini_response():
    """Create a mock Gemini API response."""
    mock_response = MagicMock()
    mock_response.text = '{"title": "Test", "content_bullets": ["Point 1"]}'
    mock_response.candidates = []
    return mock_response


# Mock file I/O
@pytest.fixture
def mock_path(mocker):
    """Mock pathlib operations."""
    mock_path = mocker.MagicMock()
    mock_path.mkdir.return_value = None
    mock_path.write_bytes.return_value = None
    mock_path.read_bytes.return_value = b"test data"
    return mock_path
```

#### Mocking Pydantic Settings
```python
# Override settings for testing
@pytest.fixture
def test_settings():
    """Settings configured for testing environment."""
    return Settings(
        gemini_api_key="test-key",
        gemini_flash_model="test-model",
        gemini_pro_model="test-model",
        enable_grounding=False,  # Disable external calls
    )
```

## Coverage Requirements

### Recommended Coverage Targets
- **Initial goal:** 60% line coverage
- **Short-term goal:** 80% line coverage
- **Long-term goal:** 90%+ line coverage for critical paths

### Critical Paths to Cover
1. **LLM Provider** (`engine/llm_provider.py`) — 100%
2. **Models** (`models.py`) — 100%
3. **Pipeline Orchestrator** (`orchestrator.py`) — 80%
4. **Theme system** (`generators/themes.py`) — 100%
5. **Agent error handling** — 100%

## CI Integration

### Recommended GitHub Actions Addition
```yaml
# .github/workflows/test.yml
name: Test

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          
      - name: Install dependencies
        run: |
          pip install -r ppt_builder/requirements.txt
          pip install pytest pytest-mock pytest-asyncio
          
      - name: Run tests
        run: pytest tests/ --cov=ppt_builder --cov-report=xml
        
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
```

### Recommended Pre-Deployment Checks
1. Run `ruff check .` (lint)
2. Run `ruff format --check .` (format check)
3. Run `pytest tests/` (unit tests)
4. Build Docker image

---

*Testing analysis: 2026-03-27*
