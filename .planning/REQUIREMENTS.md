# Requirements — v1.0 Advanced Multi-Level Table Agent

## Validated

(None yet — first milestone)

## Active

### Table Structure Models
- [ ] **TABLE-01:** Add `TableStructureSchema` Pydantic models to `models.py`
  - `HeaderLevel`, `ConditionalFormatType`, `NumberFormat` enums
  - `ColumnSpec`, `HeaderGroup`, `RowStyleRule`, `HeatmapConfig` models
  - `TableStructureSchema` main model with `header_tree`, `row_styles`, `heatmap_config`

- [ ] **TABLE-02:** Add `DataReference` model for lightweight DataFrame reference
  - `store_key`, `source_file`, `sheet_name` fields
  - Add `table_structure` and `data_reference` fields to `SlideContent`

### AdvancedTableRenderer
- [ ] **TABLE-03:** Create `generators/advanced_table_renderer.py`
  - Header layout algorithm with colspan/rowspan computation
  - Heatmap color computation (diverging + sequential modes)
  - Theme-aware color derivation (super-header darker, row label tint, theme heatmap)

- [ ] **TABLE-04:** Implement `_render_headers()` with merged cells
  - Support 1, 2, and 3-level header hierarchies
  - Apply theme colors to backgrounds and text

- [ ] **TABLE-05:** Implement `_render_data_rows()` with conditional formatting
  - Format values per `NumberFormat` enum
  - Apply heatmap colors per column configuration
  - Apply row styles (totals, subtotals, alternating shading)

- [ ] **TABLE-06:** Add hardcoded test schema for verification
  - Test with "Category Wise Break-Up" structure from reference PPT

### TableStructureAgent
- [ ] **TABLE-07:** Create `agents/table_structure_agent.py`
  - Constructor following standard pattern (LLMProvider, Settings)
  - `generate_structure()` method

- [ ] **TABLE-08:** Implement LLM prompts
  - System prompt: Financial table visualization expert
  - User prompt: DataFrame info + theme colors + analysis hint

- [ ] **TABLE-09:** Theme-aware heatmap colors
  - Derive positive/negative colors from theme's accent/error colors

### Orchestrator Integration
- [ ] **TABLE-10:** Add DataStore dict to orchestrator
  - Instance variable: `self._data_store: Dict[str, pd.DataFrame]`

- [ ] **TABLE-11:** Add `run_table_structuring()` method
  - Loop over table slides
  - Get DataFrame from DataStore
  - Call TableStructureAgent
  - Attach schema to SlideContent

- [ ] **TABLE-12:** Update data table processing to populate DataStore
  - Store raw DataFrame after DataTableEngine/DuckDB processing
  - Create DataReference on SlideContent

### Generator Routing
- [ ] **TABLE-13:** Update `ppt_generator.py` routing
  - Import AdvancedTableRenderer
  - Add route in `_render_data_table_slide()` for `table_structure` present
  - Fallback to existing path when `table_structure` is None

### LayoutDecider Updates
- [ ] **TABLE-14:** Add multi-level table recognition
  - Detect multiple time periods, growth metrics, segments
  - Flag slides for TableStructureAgent processing

### Testing
- [ ] **TABLE-15:** Unit tests for AdvancedTableRenderer
  - Header layout: 1, 2, 3 level tests
  - Heatmap: diverging, sequential, edge cases

- [ ] **TABLE-16:** Unit tests for TableStructureAgent
  - Simple DataFrame → flat schema
  - Multi-period data → grouped headers
  - Segment data → segment super-headers

- [ ] **TABLE-17:** Integration test
  - Full pipeline with DataStore
  - Fallback on agent failure

## Out of Scope

- New slide layout types beyond tables
- API changes to Gemini integration
- Database migrations beyond DuckDB
- Changes to existing `TableSchema`/`RichTableData` pipeline (deprecated later)
- Multi-slide table splitting (future enhancement)

## Traceability

| REQ | Phase | Status |
|-----|-------|--------|
| TABLE-01 | Phase 1 | — |
| TABLE-02 | Phase 1 | — |
| TABLE-03 | Phase 2 | — |
| TABLE-04 | Phase 2 | — |
| TABLE-05 | Phase 2 | — |
| TABLE-06 | Phase 2 | — |
| TABLE-07 | Phase 3 | — |
| TABLE-08 | Phase 3 | — |
| TABLE-09 | Phase 3 | — |
| TABLE-10 | Phase 4 | — |
| TABLE-11 | Phase 4 | — |
| TABLE-12 | Phase 4 | — |
| TABLE-13 | Phase 5 | — |
| TABLE-14 | Phase 6 | — |
| TABLE-15 | Phase 7 | — |
| TABLE-16 | Phase 7 | — |
| TABLE-17 | Phase 7 | — |
