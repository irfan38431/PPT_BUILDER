# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Agent Instructions and Workflow Rules

### Workflow Orchestration

#### 1. Plan Node Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately - don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

#### 2. Subagent Strategy
- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

#### 3. Self-Improvement Loop
- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project

#### 4. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

#### 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes - don't over-engineer
- Challenge your own work before presenting it

#### 6. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests - then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how

### Task Management

1. **Plan First**: Write plan to `tasks/todo.md` with checkable items
2. **Verify Plan**: Check in before starting implementation
3. **Track Progress**: Mark items complete as you go
4. **Explain Changes**: High-level summary at each step
5. **Document Results**: Add review section to `tasks/todo.md`
6. **Capture Lessons**: Update `tasks/lessons.md` after corrections

### Core Principles

- **Simplicity First**: Make every change as simple as possible. Impact minimal code.
- **No Laziness**: Find root causes. No temporary fixes. Senior developer standards.
- **Minimal Impact**: Changes should only touch what's necessary. Avoid introducing bugs.

### Domain-Specific & Past Project Rules

#### 1. Data Processing, PDFs & Python Backends
- **Defensive Data Handling**: Specifically handle `IndexError`, missing dictionary keys, and unexpected nulls gracefully when working with iterative JSON/data processing (e.g., Equity reports, rendering engines).
- **Strict Encoding**: Always implement explicit `utf-8` encoding handling when loading models or processing data to avoid `UnicodeDecodeError`, especially during file reading/writing.
- **Modular Pipelines**: For heavy workflows (e.g., document summarization, PPT generation using FastAPI/Streamlit), maintain clear abstraction boundaries between agents and data parsers.

#### 2. Email Formatting & HTML Generation
- **Client Compatibility**: Ensure HTML email templates are robustly tested for platforms like Gmail. Use standard table properties (`border="1"`, plain colors) instead of complex CSS structures.
- **Functional Links**: Anchor tags ("Return to Top", "Go Back to Contents") must be perfectly structured for inside-email routing.
- **Styling Discipline**: Follow exact design system requests (e.g., pure white background, minimal section separators, specific multi-line headers without generic dash boarding aesthetics for institutional reports).

#### 3. Frontend UIs & Dashboards
- **Artifact Panes & Tooling**: Keep AI interactions user-friendly. Follow Claude-like interface paradigms for "Artifact Panes" (persistent views, simple download/copy functionality).
- **Premium Aesthetics**: Refine elements instead of using out-of-the-box defaults (e.g., refined modals, glassmorphism, coherent color scales).

#### 4. Documentation
- **Execution Context**: Always furnish modules with high-quality READMEs defining clear instructions on how to run scripts, supply parameters (e.g., for specific company generation in Equity models), and dependencies.

#### 5. PPT Generation & Formatting (Current PPT Builder Project)
- **Decouple Content from Layout**: Separate slide content generation mapping (e.g., `slide_content_agent.py`) from actual canvas rendering logic (`ppt_generator.py`). This prevents LLM hallucination in drawing constraints and makes the codebase easier to test.
- **Fail Open / Fallbacks**: Expect varying payload structures. If specialized structures fail (e.g., missing chart or table data for a data slide), gracefully fall back to alternative simpler rendering (e.g., `_render_bullet_content`) rather than throwing an exception.
- **Consultant-Quality Visuals**: Do not rely on default plain white slides. Programmatically enforce theme palettes via `PresentationTheme`, including two-stop gradient backgrounds, accent dividers, left-side alignment accent bars, and bottom accent strips to build premium visuals automatically.
- **Parallel Optimization**: Where operations take a significant amount of time (such as layout decision rendering or requesting images from Gemini Nano Banana APIs), run them concurrently (e.g., via `ThreadPoolExecutor`) while respecting state/index mappings.

---

## Project Overview

PPT Builder is a Streamlit-based application that generates consultant-quality PowerPoint presentations using an AI agent pipeline powered by Google Gemini. It takes a topic, runs multi-source research, builds a narrative storyline, generates slide content, and renders a themed `.pptx` file with charts, tables, and infographics.

## Commands

```bash
# Activate virtual environment (Windows)
cd ppt_builder
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the Streamlit app
streamlit run app.py

# Lint
ruff check .

# Format
ruff format .

# Docker build & run
docker build -t ppt-builder .
docker run -p 8501:8501 --env-file .env ppt-builder
```

There are no tests in this codebase. Deployment is via GitHub Actions (`.github/workflows/deploy.yml`) pushing to Google Cloud Run on merge to `main`.

## Architecture

### Pipeline State Machine

The `PipelineOrchestrator` (`orchestrator.py`) drives a linear state machine:

```
idle → ingesting → researching → planning → generating → review → finalizing → done
```

Each phase has a `run_*` method. The full pipeline can be run end-to-end via `run_full_pipeline()`, or each phase can be invoked independently for human-in-the-loop approval (the Streamlit app does this).

### Agent Pipeline (execution order)

1. **Source Ingestion** — `URLResearchAgent`, `TranscriptAgent`, `DataAnalysisAgent` ingest user-provided URLs, audio/video/PDF files, and Excel/CSV data in parallel. `SourceMergerAgent` synthesizes all sources into a unified context.
2. **Research** — `ResearchAgent` + `DeepResearchAgent` use Gemini grounded search to gather facts.
3. **Storyline Planning** — `FrameworkSelectorAgent` picks two narrative frameworks (Pyramid, SCQA, Hero's Journey, etc.), `StorylineAgent` + `ComparativeStorylineGenerator` produce two competing outlines for user selection.
4. **Layout Decision** — `LayoutDecider` assigns visual types (chart, table, infographic, etc.) to each slide.
5. **Content Generation** — `SlideContentAgent` generates structured content per slide (bullets, chart data, table data). `CriticAgent` reviews and refines.
6. **Data Enrichment** — For `data_table` and `multi_class_table` slides, raw Excel data is extracted and passed through `DataAnalysisAgent` for executive table formatting.
7. **Render Decisions** — `SlideRenderDecider` decides which slides get AI-generated images vs. standard rendering. `InfographicAgent` proposes infographic enrichment.
8. **Image Generation** — `NanoBananaProIntegration` generates images via Gemini's image API for selected slides.
9. **Layout Validation** — `LayoutCriticAgent` checks element overlap and density, suggesting position adjustments.
10. **PPTX Output** — `InteractivePPTGenerator` renders the final `.pptx` file.

### Key Abstractions

- **`LLMProvider`** (`engine/llm_provider.py`): Single Gemini API wrapper. Supports `generate()` for plain text and `generate_structured()` for Pydantic-validated JSON output. All agents share one instance.
- **`PipelineLogger`** (`engine/pipeline_logger.py`): Loguru-based structured logger. Each agent gets a named instance. Logs to stderr (human-readable) and file (audit). Uses `step_start()` context manager for timing.
- **`PresentationTheme`** (`generators/themes.py`): Dataclass defining colors, fonts, and chart palettes. Used by both `ppt_generator.py` (pptx output) and `slide_previewer.py` (matplotlib preview) to stay in sync.
- **`SlideContent`** (`agents/slide_content_agent.py`): The central data object for a generated slide. Extends the LLM schema with runtime fields like `infographic_image` (bytes) and `multi_class_result`.
- **`PipelineState`** / **`SlidePlan`** / **`ChartData`** / **`TableData`** (`models.py`): Pydantic models shared across the entire pipeline.

### Module Layout

- `orchestrator.py` — Pipeline controller, wires all agents together
- `app.py` — Streamlit UI with human-in-the-loop approval workflow (~3k lines)
- `agents/` — One file per AI agent, each takes `LLMProvider` + `Settings` in constructor
- `prompts/` — LLM prompt templates, one file per agent domain (content, storyline, critic, etc.)
- `generators/` — Non-LLM rendering: `ppt_generator.py` (pptx), `chart_annotator.py` (matplotlib charts), `table_generator.py` (pptx tables), `slide_previewer.py` (matplotlib previews), `exec_summary_builder.py` (card layouts)
- `engine/` — Infrastructure: `llm_provider.py`, `pipeline_logger.py`, `research_engine.py`
- `models.py` — All shared Pydantic models
- `config.py` — Pydantic Settings from `.env`, project paths, date constants

### Design Principles

- **Content-layout separation**: Agents produce structured data (bullets, ChartData, TableData). Generators handle all pixel-level rendering. Never let LLM output dictate drawing coordinates.
- **Fail-open rendering**: If specialized rendering fails (missing chart data, malformed table), fall back to `_render_bullet_content` rather than crashing.
- **Theme-consistent**: All generators (`ppt_generator`, `chart_annotator`, `table_generator`, `slide_previewer`, `exec_summary_builder`) accept a `PresentationTheme` to keep colors in sync.
- **Parallel where possible**: Source ingestion, layout decisions, and image generation use `ThreadPoolExecutor`. Respect index mappings when collecting results.

## Configuration

Settings are loaded via `pydantic-settings` from `ppt_builder/.env`. Required: `GEMINI_API_KEY`. Optional: `NANO_BANANA_API_KEY`, GCP storage settings.

## Lint

Ruff is configured in `ruff.toml`: target Python 3.11, enforces `E`/`F`/`I` rules. `E501` (line length), `F401` (unused imports), `E711`/`E712` (None/bool comparisons) are ignored. `__init__.py` files allow `F401` for re-exports.
