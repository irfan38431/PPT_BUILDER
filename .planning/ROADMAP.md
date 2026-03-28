# Roadmap — v1.0 Advanced Multi-Level Table Agent

## Phase 1: Models

**Goal:** Add Pydantic models for table structure schema and data reference

**Requirements:** TABLE-01, TABLE-02

**Success criteria:**
1. `TableStructureSchema` with all sub-models (HeaderLevel, ColumnSpec, HeaderGroup, etc.) in `models.py`
2. `DataReference` model with store_key, source_file, sheet_name fields
3. `table_structure` and `data_reference` fields on `SlideContent` class
4. All models serialize/deserialize correctly

**Canonical refs:**
- `NEW_FEATURE_AGENT.md` §2.2 — Model specifications
- `ppt_builder/models.py` — Existing model patterns
- `ppt_builder/agents/slide_content_agent.py` — SlideContent class

---

## Phase 2: AdvancedTableRenderer

**Goal:** Implement native PPTX table renderer with multi-level headers and heatmap coloring

**Requirements:** TABLE-03, TABLE-04, TABLE-05, TABLE-06

**Success criteria:**
1. Header layout algorithm correctly computes colspan/rowspan for 1, 2, 3 level trees
2. Heatmap colors interpolate correctly (diverging centered at 0, sequential light→dark)
3. Theme-aware colors: super-header darker, row label tinted, heatmap uses theme colors
4. Row styles applied: totals bold with borders, alternating shading
5. Hardcoded test schema renders correctly to verify algorithm
6. Reference visual match: output resembles slides 5, 6, 9 of Kotak PPT

**Canonical refs:**
- `NEW_FEATURE_AGENT.md` §6 — Renderer implementation sketch
- `NEW_FEATURE_AGENT.md` §8 — Theme integration table
- `ppt_builder/generators/rich_table_generator.py` — Existing table patterns
- `ppt_builder/generators/themes.py` — Theme color properties

---

## Phase 3: TableStructureAgent

**Goal:** Implement LLM agent that analyzes DataFrames and produces table structure schemas

**Requirements:** TABLE-07, TABLE-08, TABLE-09

**Success criteria:**
1. Agent produces valid `TableStructureSchema` from sample DataFrames
2. Multi-period financial data → correct super-header grouping (Months, Abs Growth, Rel Growth)
3. Segment data → segment super-headers (Corporate, Retail, HNI)
4. Heatmap colors derived from theme's accent/error colors
5. Graceful fallback to flat schema when hierarchy unclear

**Canonical refs:**
- `NEW_FEATURE_AGENT.md` §5 — LLM prompt templates
- `NEW_FEATURE_AGENT.md` §2.1 — Agent behavior specification
- `ppt_builder/engine/llm_provider.py` — LLMProvider pattern

---

## Phase 4: Orchestrator Integration

**Goal:** Add DataStore and run_table_structuring() sub-phase to pipeline

**Requirements:** TABLE-10, TABLE-11, TABLE-12

**Success criteria:**
1. `self._data_store: Dict[str, pd.DataFrame]` exists on orchestrator
2. DataTableEngine/DuckDB populates DataStore with raw DataFrames
3. `run_table_structuring()` loops over table slides and calls agent
4. `DataReference` attached to SlideContent for each table slide
5. Agent failures logged and fall back to existing pipeline

**Canonical refs:**
- `NEW_FEATURE_AGENT.md` §2.4A — Orchestrator integration points
- `ppt_builder/orchestrator.py` — Existing pipeline methods
- `ppt_builder/orchestrator.py` `_enrich_slide_data_tables()` — DataTableEngine integration

---

## Phase 5: Generator Routing

**Goal:** Route AdvancedTableRenderer in ppt_generator when table_structure present

**Requirements:** TABLE-13

**Success criteria:**
1. `_render_data_table_slide()` checks for `table_structure` on content
2. When present, calls `AdvancedTableRenderer.render()` with schema + DataFrame
3. When absent, existing path (`TableGenerator`, `RichTableGenerator`) used unchanged
4. Backward compatibility: existing slides without `table_structure` render identically

**Canonical refs:**
- `NEW_FEATURE_AGENT.md` §2.4C — Generator routing specification
- `ppt_builder/generators/ppt_generator.py` — `_render_data_table_slide()` method

---

## Phase 6: LayoutDecider Updates

**Goal:** Recognize when data warrants multi-level grouped headers

**Requirements:** TABLE-14

**Success criteria:**
1. LayoutDecider detects: multiple time periods, growth metrics, segment breakdowns
2. Multi-level indicators: 2+ periods OR 2+ metrics OR 2+ segments
3. Flags slides for TableStructureAgent processing (add `requires_advanced_table` hint)

**Canonical refs:**
- `NEW_FEATURE_AGENT.md` §2.4D — LayoutDecider specification
- `ppt_builder/agents/layout_decider.py` — Existing layout decision logic

---

## Phase 7: Testing & Verification

**Goal:** Comprehensive testing and visual QA

**Requirements:** TABLE-15, TABLE-16, TABLE-17

**Success criteria:**
1. Unit tests: Header layout correctness (colspan, rowspan for all levels)
2. Unit tests: Heatmap computation (diverging, sequential, edge cases)
3. Unit tests: TableStructureAgent with mock DataFrames
4. Integration test: Full pipeline with DataStore
5. Fallback test: Agent failure → RichTableGenerator
6. Visual QA: Output matches reference PPT slides 5, 6, 9

**Canonical refs:**
- `NEW_FEATURE_AGENT.md` §10 — Testing strategy
- `Kotak_Comp__Analysis_-_FY26___Real___1_.pptx` — Reference visuals
