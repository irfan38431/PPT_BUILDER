# Codebase Structure

**Analysis Date:** 2026-03-27

## Directory Layout

```
ppt_builder/
├── app.py                     # Streamlit UI entry point (~2800+ lines)
├── orchestrator.py            # Pipeline controller (~1400+ lines)
├── models.py                  # Pydantic shared models (~440 lines)
├── config.py                  # Settings from .env (~120 lines)
│
├── agents/                    # AI agent implementations
│   ├── research_agent.py      # Topic research with grounded search
│   ├── deep_research_agent.py # Per-slide deep research
│   ├── storyline_agent.py      # Framework selection & outline generation
│   ├── slide_content_agent.py  # Slide content generation
│   ├── critic_agent.py        # Content validation
│   ├── layout_decider.py      # Layout type assignment
│   ├── layout_critic_agent.py  # Layout quality validation
│   ├── infographic_agent.py    # Infographic enrichment proposals
│   ├── slide_render_decider.py # Render strategy decisions
│   ├── url_research_agent.py   # URL content extraction
│   ├── transcript_agent.py     # Audio/video/PDF transcription
│   ├── data_analysis_agent.py  # Excel/CSV data analysis
│   ├── source_merger_agent.py  # Multi-source synthesis
│   ├── table_schema_agent.py   # Rich table schema planning
│   ├── query_agent.py          # DuckDB SQL query execution
│   ├── data_table_engine.py    # Pandas-based table fallback
│   ├── conditional_format_engine.py # Per-cell table formatting
│   └── __init__.py
│
├── prompts/                    # LLM prompt templates
│   ├── research_prompts.py
│   ├── storyline_prompts.py
│   ├── content_prompts.py
│   ├── critic_prompts.py
│   ├── infographic_prompts.py
│   ├── render_decision_prompts.py
│   ├── layout_critic_prompts.py
│   ├── transcript_prompts.py
│   ├── data_analysis_prompts.py
│   ├── data_table_prompts.py
│   ├── table_schema_prompts.py
│   ├── query_prompts.py
│   ├── source_prompts.py
│   └── __init__.py
│
├── generators/                 # Non-LLM rendering
│   ├── ppt_generator.py         # Main PPTX assembly (~880+ lines)
│   ├── chart_annotator.py       # Matplotlib chart rendering
│   ├── table_generator.py       # PPTX table rendering
│   ├── rich_table_generator.py  # Advanced table with conditional formatting
│   ├── exec_summary_builder.py  # Card-based exec summary layouts
│   ├── slide_previewer.py       # Matplotlib preview renderer
│   ├── themes.py                # Theme definitions (~300 lines)
│   ├── nano_banana_pro.py       # Gemini image generation integration
│   └── __init__.py
│
├── engine/                     # Infrastructure
│   ├── llm_provider.py         # Gemini API wrapper (~285 lines)
│   ├── pipeline_logger.py       # Structured audit logging (~115 lines)
│   ├── research_engine.py      # Research utilities
│   └── __init__.py
│
├── db/                         # Database integrations
│   ├── duckdb_local.py          # DuckDB in-memory SQL for data tables
│   └── __init__.py
│
├── utils/                      # Utilities
│   ├── gcp_storage.py          # Google Cloud Storage integration
│   ├── email_sender.py          # Email notification utility
│   └── __init__.py
│
├── demo_ppts/                  # Demo generation
│   ├── generate_demos.py        # Script to generate demo PPTs
│   ├── scheduler.py             # Demo refresh scheduling
│   ├── __init__.py
│   └── demo_config.json         # Demo PPT configurations
│
└── data/
    ├── output/                  # Generated PPTX files
    ├── logs/                    # Pipeline audit logs
    └── cache/                   # Cached data
```

## Directory Purposes

**Root (`ppt_builder/`):**
- Purpose: Application root containing all Python modules
- Contains: Entry points (app.py, orchestrator.py), core models, configuration

**Agents (`agents/`):**
- Purpose: AI agent implementations for discrete pipeline tasks
- Contains: 18 agent files, each specializing in one aspect (research, content, validation, etc.)
- Key pattern: Each agent takes `LLMProvider` + `Settings` in constructor

**Prompts (`prompts/`):**
- Purpose: LLM prompt templates (string formatting with `.format()`)
- Contains: 13 prompt files, one per agent domain
- Key files: `content_prompts.py`, `research_prompts.py`, `storyline_prompts.py`

**Generators (`generators/`):**
- Purpose: All non-LLM rendering code
- Contains: PPTX generation, chart/table rendering, theme definitions
- Key files: `ppt_generator.py`, `chart_annotator.py`, `table_generator.py`, `themes.py`

**Engine (`engine/`):**
- Purpose: Shared infrastructure used by all agents
- Contains: `LLMProvider`, `PipelineLogger`, research utilities
- Key pattern: These modules have no dependencies on agents/generators (pure infrastructure)

**Database (`db/`):**
- Purpose: DuckDB local integration for data table queries
- Contains: `duckdb_local.py` with SQL pipeline for Excel/CSV analysis

**Utilities (`utils/`):**
- Purpose: Cross-cutting concerns (GCP storage, email)
- Contains: Cloud storage for image persistence, email notifications

**Demo (`demo_ppts/`):**
- Purpose: Pre-generated demo presentations
- Contains: Generation scripts, configuration, status tracking

## Key File Locations

**Entry Points:**
- `ppt_builder/app.py`: Streamlit UI (~2800 lines)
- `ppt_builder/orchestrator.py`: Pipeline controller (~1400 lines)

**Configuration:**
- `ppt_builder/config.py`: Settings from `.env` using pydantic-settings
- `ppt_builder/.env`: Environment variables (API keys, etc.)

**Core Logic:**
- `ppt_builder/orchestrator.py`: PipelineOrchestrator class
- `ppt_builder/models.py`: All Pydantic models
- `ppt_builder/agents/slide_content_agent.py`: SlideContent class + agent

**Rendering:**
- `ppt_builder/generators/ppt_generator.py`: InteractivePPTGenerator class
- `ppt_builder/generators/chart_annotator.py`: ChartAnnotator class
- `ppt_builder/generators/table_generator.py`: TableGenerator class
- `ppt_builder/generators/themes.py`: PresentationTheme dataclass

**Infrastructure:**
- `ppt_builder/engine/llm_provider.py`: LLMProvider class
- `ppt_builder/engine/pipeline_logger.py`: PipelineLogger class

## Naming Conventions

**Files:**
- Python modules: `lowercase_with_underscores.py`
- Example: `slide_content_agent.py`, `pipeline_logger.py`

**Classes:**
- PascalCase for classes
- Example: `PipelineOrchestrator`, `SlideContentAgent`, `PresentationTheme`

**Functions/Methods:**
- snake_case
- Example: `run_source_ingestion()`, `generate_content()`, `_render_slide()`

**Constants:**
- UPPER_SNAKE_CASE
- Example: `SLIDE_WIDTH`, `HEADER_LEFT`

**Pydantic Models:**
- PascalCase class names
- Example: `SlideContent`, `ChartData`, `TableData`

## Where to Add New Code

**New Agent:**
- Primary code: `ppt_builder/agents/{new_agent_name}.py`
- Prompt template: `ppt_builder/prompts/{new_agent_name}_prompts.py`
- Initialize in `PipelineOrchestrator.__init__()`
- Add `run_*` method to orchestrator for UI integration

**New Generator/Renderer:**
- Primary code: `ppt_builder/generators/{new_generator}.py`
- Follow existing patterns (e.g., `ChartAnnotator`, `TableGenerator`)
- If theme-aware, accept `PresentationTheme` in constructor
- Register in `InteractivePPTGenerator` dispatcher

**New Pydantic Model:**
- Add to `ppt_builder/models.py`
- Follow existing patterns for field definitions
- Document with docstrings

**New LLM Prompt:**
- Add to appropriate file in `ppt_builder/prompts/`
- Use `.format()` string formatting
- Include source constraint patterns for anti-hallucination

**New Theme:**
- Add to `ppt_builder/generators/themes.py`
- Follow `PresentationTheme` dataclass structure
- Register in `BUILTIN_THEMES` dict

**New Utility:**
- Add to `ppt_builder/utils/{utility_name}.py`
- Follow existing patterns (e.g., GCP storage)

## Special Directories

**`data/output/`:**
- Purpose: Generated PPTX files
- Generated: Yes (at runtime)
- Committed: No (in .gitignore)

**`data/logs/`:**
- Purpose: Pipeline audit logs (JSON format)
- Generated: Yes (daily rotation)
- Committed: No (in .gitignore)

**`data/cache/`:**
- Purpose: Cached intermediate data
- Generated: Yes (at runtime)
- Committed: No (in .gitignore)

**`demo_ppts/`:**
- Purpose: Pre-generated demo presentations
- Generated: Via `generate_demos.py` script
- Committed: Yes (stored in repo)

## Module Dependencies

```
app.py
  └── orchestrator.py
        ├── models.py
        ├── config.py
        ├── engine/
        │     ├── llm_provider.py
        │     └── pipeline_logger.py
        ├── agents/
        │     ├── research_agent.py
        │     ├── storyline_agent.py
        │     ├── slide_content_agent.py
        │     ├── ...
        │     └── [agent].py
        ├── generators/
        │     ├── ppt_generator.py
        │     ├── chart_annotator.py
        │     ├── table_generator.py
        │     ├── themes.py
        │     └── ...
        ├── prompts/
        │     └── [domain]_prompts.py
        └── db/
              └── duckdb_local.py
```

**Dependency Rules:**
- `agents/` → `engine/` (LLMProvider, PipelineLogger, Settings)
- `generators/` → `models.py`, `themes.py`
- `orchestrator.py` → All layers
- `engine/` → Only standard library + config
- `app.py` → `orchestrator.py` only (no direct agent imports)

---

*Structure analysis: 2026-03-27*
