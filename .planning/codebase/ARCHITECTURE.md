# Architecture

**Analysis Date:** 2026-03-27

## Pattern Overview

**Overall:** Agent Pipeline with Linear State Machine

The PPT Builder uses an AI agent pipeline pattern driven by a `PipelineOrchestrator` that manages a sequential state machine. Each state transitions triggers specialized agents that produce structured data, which generators later render into a themed `.pptx` file.

**Key Characteristics:**
- Sequential pipeline phases with human-in-the-loop approval at key checkpoints
- All agents share a single `LLMProvider` instance for Gemini API calls
- Content-layout separation: agents produce structured data, generators handle pixel-level rendering
- Fail-open rendering: fallback to simpler layouts when specialized rendering fails

## Layers

**Orchestration Layer:**
- Purpose: Drive the pipeline state machine and coordinate all agents
- Location: `ppt_builder/orchestrator.py`
- Contains: `PipelineOrchestrator` class with `run_*` methods for each phase
- Depends on: All agents, `LLMProvider`, `PipelineLogger`
- Used by: `app.py` (Streamlit UI)

**Agent Layer:**
- Purpose: Specialized AI agents that perform discrete pipeline tasks
- Location: `ppt_builder/agents/`
- Contains: ResearchAgent, StorylineAgent, SlideContentAgent, CriticAgent, LayoutDecider, InfographicAgent, etc.
- Depends on: `LLMProvider`, `Settings`, `PipelineLogger`
- Used by: `PipelineOrchestrator`

**Data/Model Layer:**
- Purpose: Shared Pydantic models defining pipeline state and slide content
- Location: `ppt_builder/models.py`
- Contains: `PipelineState`, `SlidePlan`, `SlideContent`, `ChartData`, `TableData`, `ResearchFinding`, `StorylineOutline`, etc.
- Depends on: Pydantic
- Used by: All layers

**Generation Layer:**
- Purpose: Non-LLM rendering of slides into PPTX, charts, tables
- Location: `ppt_builder/generators/`
- Contains: `InteractivePPTGenerator`, `ChartAnnotator`, `TableGenerator`, `RichTableGenerator`, `SlidePreviewRenderer`, `ExecSummaryBuilder`
- Depends on: `PresentationTheme`, `models.py`
- Used by: `PipelineOrchestrator`

**Infrastructure Layer:**
- Purpose: Shared utilities for LLM calls and logging
- Location: `ppt_builder/engine/`
- Contains: `LLMProvider` (Gemini wrapper), `PipelineLogger` (audit logging), `research_engine.py`
- Depends on: google-genai SDK, loguru, tenacity
- Used by: All agents

**Presentation/Theme Layer:**
- Purpose: Centralized theme definitions ensuring visual consistency
- Location: `ppt_builder/generators/themes.py`
- Contains: `PresentationTheme` dataclass, `THEME_CORPORATE_BLUE`, `BUILTIN_THEMES`
- Depends on: python-pptx, matplotlib (for chart colors)
- Used by: All generators, orchestrator

**UI Layer:**
- Purpose: Streamlit interface with human-in-the-loop approval workflow
- Location: `ppt_builder/app.py`
- Contains: Phase-specific functions (`phase_idle`, `phase_researching`, etc.)
- Depends on: Streamlit, `PipelineOrchestrator`
- Used by: End users

## State Machine Flow

```
idle → ingesting → researching → planning → generating → review → finalizing → done
```

**State Transitions:**

| State | Method | What Happens |
|-------|--------|--------------|
| `idle` | User clicks "Start Research" | Initializes orchestrator |
| `ingesting` | `run_source_ingestion()` | Parallel processing of URLs, transcripts, data files |
| `researching` | `run_research()` | Topic decomposition, grounded search, source merging |
| `planning` | `run_framework_selection()` + `run_comparative_outlines()` | Framework selection, dual outline generation |
| `generating` | `run_content_generation()` + validation/infographic phases | Slide content, layout decisions, enrichment, image generation |
| `review` | `run_validation()` | CriticAgent validates all slides |
| `finalizing` | `run_pptx_generation()` | Final PPTX assembly and output |
| `done` | — | Pipeline complete |

**Human-in-the-Loop Points:**
1. **Outline Selection** (between planning and generating): User picks between two generated outlines (Outline A vs Outline B)
2. **Theme Selection** (after outline): User chooses from two contrasting themes
3. **Slide Review** (after generating): User can regenerate individual slides or approve content

## Data Flow Between Components

**Research → Planning → Generation → Rendering:**

```
1. User Input (topic, sources, audience)
         ↓
2. Source Ingestion Agents (URLResearchAgent, TranscriptAgent, DataAnalysisAgent)
         ↓
3. ResearchAgent + DeepResearchAgent → ResearchFinding[]
         ↓
4. SourceMergerAgent → unified research synthesis string
         ↓
5. FrameworkSelectorAgent → FrameworkChoice[]
         ↓
6. ComparativeStorylineGenerator → StorylineOutline (A and B)
         ↓
7. User selects outline → StorylineOutline (selected)
         ↓
8. LayoutDecider → SlidePlan.layout_type confirmed per slide
         ↓
9. SlideContentAgent → SlideContent[] (with chart_data, table_data)
         ↓
10. Data Enrichment (for data_table slides):
    - DuckDB local → SQL pipeline → RichTableData
    - OR DataTableEngine (pandas fallback)
         ↓
11. CriticAgent → ValidationResult[]
         ↓
12. InfographicAgent → InfographicProposal[]
         ↓
13. Image Generation (if enabled):
    - InfographicAgent images
    - Full-slide images (text-to-image)
    - Universal refinement (image-to-image)
         ↓
14. LayoutCriticAgent → LayoutValidationResult[]
         ↓
15. InteractivePPTGenerator → .pptx file
```

## Key Abstractions

**LLMProvider** (`engine/llm_provider.py`):
- Single Gemini API wrapper shared by all agents
- `generate()`: Plain text responses
- `generate_structured()`: Pydantic-validated JSON output
- `generate_with_search()`: Grounded search with source extraction
- Built-in retry logic (exponential backoff on 429/500/503)
- 120s request timeout

**PipelineLogger** (`engine/pipeline_logger.py`):
- Loguru-based structured logger with agent scoping
- Console sink (human-readable) + File sink (JSON audit logs)
- `step_start()` context manager for timing pipeline phases
- `action()` and `decision()` methods for tracking key events

**PresentationTheme** (`generators/themes.py`):
- Dataclass defining colors, fonts, chart palettes
- Auto-derives gradient colors and matplotlib-compatible tuples
- Built-in themes: `corporate_blue`, `modern_emerald`, `warm_executive`, `midnight_violet`, `nippon_red`
- Used by: `ppt_generator.py`, `slide_previewer.py`, `chart_annotator.py`, `table_generator.py`, `exec_summary_builder.py`

**SlideContent** (`agents/slide_content_agent.py`):
- Central data object for a generated slide
- Extends `_SlideContentLLM` (LLM output schema) with runtime fields:
  - `infographic_image`: PNG bytes for infographic enrichment
  - `full_slide_image`: PNG bytes for full-slide AI generation
  - `rich_table_data`: Per-cell conditional formatting data
  - `dual_tables`: Two TableData objects for dual-table layout

**PipelineState** (`models.py`):
- Tracks current status, topic, research findings, selected outline
- Stores `active_agents` dict for UI dashboard
- Maintains errors list and current step description

**SlidePlan** (`models.py`):
- Blueprint for a single slide
- Defines `layout_type` (bullet, chart, table, data_table, etc.) and `visual_type` (bar_chart, pie_chart, etc.)
- Tracks status: planned → researched → generated → approved

## Entry Points

**app.py** — Streamlit UI entry point:
- `phase_idle()`: Landing page with topic input and demo presentations
- `phase_ingesting()`: Source ingestion UI with pipeline dashboard
- `phase_researching()`: Research progress UI
- `phase_storyline_approval()`: Outline selection UI
- `phase_generating()`: Content generation with slide previews
- `phase_review()`: Validation results and slide editing
- `phase_finalizing()`: PPTX download

**orchestrator.py** — Pipeline controller:
- `PipelineOrchestrator.__init__()`: Initializes all agents
- `run_full_pipeline()`: End-to-end execution (not used by UI, which calls phases individually)
- Phase methods: `run_source_ingestion()`, `run_research()`, `run_framework_selection()`, `run_comparative_outlines()`, `run_content_generation()`, `run_validation()`, `run_infographic_evaluation()`, `run_pptx_generation()`, etc.

## Error Handling

**Strategy:** Fail-open with graceful degradation

**Patterns:**
- Source ingestion failures: Log error, mark agent as "error", continue with available sources
- Content generation failures: Throw and propagate to UI for user notification
- Layout rendering failures: Fall back to `_render_bullet_content()` instead of crashing
- Image generation failures: Log warning, continue without image
- DuckDB failures: Fall back to `DataTableEngine` (pandas-based)
- LLM API failures: Retry 3x with exponential backoff, then propagate

**Validation:**
- `CriticAgent` checks content accuracy against research
- `LayoutCriticAgent` validates element overlap and density
- Results surfaced to user for manual approval or regeneration

---

*Architecture analysis: 2026-03-27*
