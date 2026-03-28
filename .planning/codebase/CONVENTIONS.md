# Coding Conventions

**Analysis Date:** 2026-03-27

## Python Version

- **Target:** Python 3.11 (`py311`)
- **Configuration:** `ppt_builder/ruff.toml` defines `target-version = "py311"`

## Code Style

### Tooling
- **Linter:** Ruff (configured in `ppt_builder/ruff.toml`)
- **Formatter:** Ruff (integrated)

### Ruff Configuration
```toml
# ppt_builder/ruff.toml
target-version = "py311"

[lint]
select = ["E", "F", "I"]
ignore = [
    "E501",  # line too long — handled separately
    "F401",  # unused imports — some are intentional re-exports
    "E711",  # comparison to None — style preference
    "E712",  # comparison to True/False — style preference
]

[lint.per-file-ignores]
"__init__.py" = ["F401"]  # re-exports are intentional

[format]
quote-style = "double"
indent-style = "space"
```

### Key Style Rules
- **Quotes:** Double quotes (`"`) for strings
- **Indentation:** Spaces (4 spaces standard, 2 spaces for nested/compact contexts)
- **Line length:** E501 ignored — prefer line-length < 120 chars where practical
- **None/bool comparisons:** E711/E712 ignored — use explicit `is None` / `== True`

## Naming Conventions

### Files
- **Modules:** `snake_case.py` (e.g., `llm_provider.py`, `pipeline_logger.py`)
- **Prompt modules:** `*_prompts.py` (e.g., `research_prompts.py`, `content_prompts.py`)

### Classes
- **PascalCase** for all class names
- Suffix patterns:
  - `*Agent` — AI agents (`ResearchAgent`, `SlideContentAgent`)
  - `*Engine` — Processing engines (`ConditionalFormatEngine`, `DataTableEngine`)
  - `*Provider` — Service providers (`LLMProvider`)
  - `*Logger` — Logging utilities (`PipelineLogger`)
  - `*Generator` — Output generators (`InteractivePPTGenerator`, `StorylineAgent`)
- Private classes prefixed with `_` (e.g., `_SlideContentLLM`, `_StepTimer`)

### Functions/Methods
- **snake_case** for all function names
- Private methods prefixed with `_` (e.g., `_call_api()`, `_sanitize_schema()`)
- Public API methods unprefixed (e.g., `generate()`, `generate_structured()`)
- Context managers for timed operations (e.g., `step_start()`)

### Variables
- **snake_case** for local variables and parameters
- Private instance variables prefixed with `_` (e.g., `self._settings`, `self._llm`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `BUILTIN_THEMES`)

### Type Names
- **PascalCase** for Pydantic models (`SlidePlan`, `ChartData`, `PipelineState`)
- **PascalCase** for dataclasses (`PresentationTheme`)
- **Literal[...]** for union type literals
- **Type aliases** at module level (e.g., `CFRuleType = Literal[...]`)

## Import Organization

### Standard Order
1. `from __future__ import annotations` (required first for type hints)
2. Standard library imports (`sys`, `time`, `pathlib`, `json`)
3. Third-party imports (pydantic, loguru, tenacity, google-genai)
4. Local imports (relative, `from config import`, `from engine import`)

### Example (`ppt_builder/engine/llm_provider.py`):
```python
from __future__ import annotations

import json
from typing import Any, Dict, Optional, Type

from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import Settings, get_settings
from engine.pipeline_logger import PipelineLogger
```

### Path Aliases
- No path aliases configured — use relative imports
- Import patterns: `from agents.slide_content_agent import SlideContent`

## Documentation Standards

### Module Docstrings
Required at top of every Python file:
```python
"""
engine/llm_provider.py — Gemini API wrapper with grounding and structured output.
Uses google-genai SDK, tenacity for retries, and PipelineLogger for audit.
"""
```

### Class Docstrings
Google-style with description:
```python
class LLMProvider:
    """Unified interface for Gemini API calls with grounding support."""
```

### Method/Function Docstrings
Google-style with Args, Returns, Description:
```python
def generate(
    self,
    prompt: str,
    *,
    model: Optional[str] = None,
) -> str:
    """Generate a plain-text response from Gemini.

    Args:
        prompt: The user prompt.
        model: Override model name (defaults to flash model).

    Returns:
        The model's text response.
    """
```

### Pydantic Model Docstrings
Field descriptions in the `description` parameter:
```python
class SlidePlan(BaseModel):
    """Blueprint for a single slide in the presentation."""
    id: int
    layout_type: str = Field(
        description="One of: 'bullet', 'chart', 'table', 'data_table', ..."
    )
```

## Error Handling

### Custom Exception Classes
Located in `models.py`:
```python
class TableQueryError(Exception):
    """Raised when a table query returns no rows or fails execution."""
    pass

class QueryResultMismatchError(Exception):
    """Raised when query result columns don't match the expected schema."""
    pass
```

### Exception Handling Patterns
- Chain exceptions with `from e` for debugging:
  ```python
  except (json.JSONDecodeError, Exception) as e:
      raise ValueError(
          f"LLM returned invalid JSON for {response_model.__name__}: {e}"
      ) from e
  ```
- Fail-open pattern for rendering:
  ```python
  except Exception as e:
      self._log.error(f"Content generation failed for slide {idx}: {e}")
      contents[idx] = SlideContent(
          title=slides[idx].title,
          content_bullets=["Content generation failed"],
      )
  ```

### Retry Logic
Use `tenacity` for transient failures:
```python
@retry(
    retry=retry_if_exception_type((APIError, TimeoutError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    reraise=True,
)
def _call_api(self, ...):
    ...
```

## Logging Conventions

### Logger Implementation
- **Library:** Loguru (configured in `engine/pipeline_logger.py`)
- **Pattern:** Agent-scoped `PipelineLogger` instances

### Logger Initialization
```python
class PipelineLogger:
    _initialized: bool = False

    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name
        self._ensure_global_setup()
```

### Logging Methods
- `info()` — General progress messages
- `debug()` — Detailed debugging information
- `warning()` — Non-fatal issues
- `error()` — Failures that don't stop execution
- `action(action, detail)` — Agent action with metadata
- `decision(decision, reason)` — Decision points with rationale
- `step_start(step_name)` — Context manager for timed steps

### Log Output
- **Console:** Human-readable, colored output
- **File:** Structured logs in `data/logs/pipeline_YYYY-MM-DD.log`
- **Format:** `{time} | {level} | {agent} | {message}`

### Example Usage
```python
self._log.action("LLM Call", f"model={model_name} grounding={use_grounding}")
self._log.info(f"Research complete: {len(findings)} findings")

with self._log.step_start("Full Topic Research"):
    subtopics = self.decompose_topic(...)
    findings = self._engine.search_multiple(...)
```

## Function Design

### Constructor Pattern
All agent classes follow this pattern:
```python
def __init__(
    self,
    llm: Optional[LLMProvider] = None,
    settings: Optional[Settings] = None,
) -> None:
    self._settings = settings or get_settings()
    self._llm = llm or LLMProvider(self._settings)
    self._log = PipelineLogger("ClassName")
```

### Parameter Patterns
- **Dependency injection:** Pass shared instances (`llm`, `settings`) or use factory defaults
- **Keyword-only args:** Use `*` for forced keyword arguments after positional
- **Type hints:** All parameters typed, return types specified

### Return Values
- Always specify return type annotation (`: str`, `: List[X]`, etc.)
- Use `Optional[X]` for nullable returns
- Pydantic models for structured returns

## Module Design

### Agent Modules (`agents/`)
- One file per agent
- Two class types per file:
  - Schema classes (prefixed `_`, for LLM output): `_SlideContentLLM`
  - Main agent class: `SlideContentAgent`
  - Extended runtime class: `SlideContent`

### Generator Modules (`generators/`)
- Non-LLM rendering logic
- Use `PresentationTheme` for consistent styling
- Fail-open patterns for graceful degradation

### Prompt Modules (`prompts/`)
- Template strings (uppercase `SLIDE_CONTENT_PROMPT`)
- Use `.format()` for variable substitution
- Organized by agent domain

### Engine Modules (`engine/`)
- Infrastructure: `llm_provider.py`, `pipeline_logger.py`
- Shared logic with no external dependencies on agents

## Configuration

### Settings Pattern
```python
class Settings(BaseSettings):
    gemini_api_key: str = Field(
        ..., description="Google Gemini API key"
    )
    gemini_flash_model: str = Field(
        default="gemini-3-flash-preview",
        description="Fast model for routine tasks",
    )
    
    model_config = {
        "env_file": str(ROOT_DIR / ".env"),
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }
```

### Environment Variables
- Loaded via `pydantic-settings` from `.env`
- Required: `GEMINI_API_KEY`
- Optional: `NANO_BANANA_API_KEY`, GCP storage settings

---

*Convention analysis: 2026-03-27*
