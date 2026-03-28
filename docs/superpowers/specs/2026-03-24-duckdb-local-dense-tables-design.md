# DuckDB-Local Dense Table Pipeline

**Date:** 2026-03-24
**Status:** Draft
**Scope:** Replace the pandas-only DataTableEngine primary path with a DuckDB-in-memory SQL pipeline that produces dense, multi-segment, conditionally-formatted executive tables — matching the quality of `test_data_table.pptx`.

---

## Problem

When an Excel file is provided, `data_table` slides produce simple 5x3 tables instead of dense 13x22 tables like `test_data_table.pptx`. Root causes:

1. **Content prompt tells LLM to generate `table_data` for `data_table` slides** — produces trivial tables before the real engine runs.
2. **DataTableEngine (pandas-only) uses broad LLM heuristics** to decide grouping/pivoting — not slide-topic-aware SQL.
3. **The SQL path (`TableSchemaAgent` → `QueryAgent`) requires PostgreSQL** — the DuckDB connector only works via `pg.ppt_data.*` table references. No PG = no SQL path.
4. **Single table per slide** — no support for 2 tables (top/bottom) on one `data_table` slide.
5. **QueryAgent prompts hardcode `pg.ppt_data.*`** table references (and inconsistently: line 8 says `pg.ppt_data` while line 22 says `pg.public`) — incompatible with in-memory DuckDB.

## Solution: DuckDB In-Memory SQL Pipeline

Load Excel directly into DuckDB in-memory (zero infrastructure), then reuse the existing `TableSchemaAgent` → `QueryAgent` → `ConditionalFormatEngine` chain per slide. Support 1 or 2 tables per slide.

---

## Architecture

### Data Flow

```
Excel/CSV file (UploadedFileRef)
  │
  ▼
DuckDBLocalConnector.load_file(file_ref)      ← NEW
  │  Creates in-memory DuckDB, loads sheets/CSV as tables
  │  Returns schema_registry (same format as PGLoader)
  │
  ▼
Orchestrator._enrich_data_table_slides()      ← MODIFIED
  │  For each data_table slide:
  │
  ▼
TableSchemaAgent.run_multi(slide, registry)   ← MODIFIED (returns SlideTablePlan)
  │  LLM plans 1 or 2 TableSchema per slide based on topic
  │
  ▼
QueryAgent.run(schema, registry)              ← MODIFIED (parameterized table_prefix)
  │  LLM writes SQL, executes against in-memory DuckDB
  │  Returns DataFrame
  │
  ▼
ConditionalFormatEngine.compute(df, schema)   ← EXISTING (no changes)
  │  Computes per-cell colors
  │
  ▼
rich_table_to_table_data(rich_data, schema)   ← NEW helper
  │  Extracts headers, rows, header_groups, heatmap_columns, total_row_indices
  │  for native PPTX rendering
  │
  ▼
ppt_generator._render_data_table_slide()      ← MODIFIED
  │  If 2 tables: uses add_multiple_tables()
  │  If 1 table: uses add_table() (current path)
```

### Components

#### 1. `DuckDBLocalConnector` (NEW — `db/duckdb_local.py`)

Replaces the PG-dependent `DuckDBConnector` + `PGLoader` for the common case where users just upload Excel/CSV files. Implements context manager for safe resource cleanup.

```python
class DuckDBLocalConnector:
    """In-memory DuckDB for Excel/CSV-based table queries. No PostgreSQL needed."""

    def __init__(self) -> None:
        self._conn = duckdb.connect()  # in-memory
        self._tables: Dict[str, str] = {}  # table_name → sheet_name

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def load_file(self, file_ref: UploadedFileRef) -> Dict[str, Any]:
        """Load Excel sheets or CSV into DuckDB tables. Returns schema_registry.

        For Excel: reads all sheets via pd.read_excel(sheet_name=None).
        For CSV: reads single file via pd.read_csv().

        Sheet naming: slugified sheet name. On collision (e.g., "Sheet 1" and
        "Sheet_1" both → "sheet_1"), appends "_2", "_3" etc.

        Skips sheets with < 2 rows or < 2 columns (cover pages, notes).

        Registration: Uses CREATE TABLE AS SELECT * FROM df_view for each sheet,
        creating real tables (not views) for full SQL compatibility.

        Returns registry in same format as PGLoader.upload() — keyed by
        table_name with columns metadata (dtype, sample_values, min, max).
        """

    def run_query(self, sql: str) -> pd.DataFrame:
        """Execute SQL and return DataFrame."""
        return self._conn.execute(sql).fetchdf()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
```

Key design decisions:
- **Same schema_registry format** as `PGLoader` so `TableSchemaAgent` and `QueryAgent` work without changes to their core logic.
- **Table naming**: `{slugified_sheet_name}` with deduplication suffix on collision.
- **Table references in SQL**: Just `{table_name}` (bare, not `pg.ppt_data.{table_name}`).
- **Context manager** ensures DuckDB native resources are released even on exceptions.
- **`CREATE TABLE AS`** instead of `register()` for full SQL compatibility (DuckDB `register()` creates views, which limits DDL operations; `CREATE TABLE AS` creates real tables).
- **CSV support**: When `file_ref.file_type == "csv"`, loads as a single table named after the filename.
- **Security note**: This connector is strictly for in-memory analysis of the user's own uploaded files. The LLM-generated SQL is executed only against this ephemeral in-memory database.

#### 2. `QueryAgent` prompt adaptation

**Pre-existing bug:** The current system prompt has two contradictory prefix instructions:
- Line 8: `"The tables are accessible as: pg.ppt_data.{table_name}"`
- Line 22: `"Always prefix table references: pg.public.{table_name}"`

Fix both by parameterizing:

**System prompt changes** (`QUERY_AGENT_SYSTEM_PROMPT`):
- Remove both hardcoded prefix lines
- Add: `"Always prefix table references with the provided table_prefix. Example: {table_prefix}{table_name}"`

**User prompt changes** (`QUERY_AGENT_USER_PROMPT`):
- Add `table_prefix` field: `"Table Prefix: {table_prefix}"`

**`QueryAgent.run()` method changes:**
- Add `table_prefix: str = ""` parameter
- Pass `table_prefix` to `QUERY_AGENT_USER_PROMPT.format(...)` and `QUERY_AGENT_SYSTEM_PROMPT.format(...)`
- Also pass `table_prefix` in `_ask_for_correction()` so retry queries use the correct prefix

**Orchestrator routing:**
- When using `DuckDBLocalConnector` (in-memory): pass `table_prefix=""`
- When using `DuckDBConnector` (PG-attached): pass `table_prefix="pg.ppt_data."`

#### 3. `TableSchemaAgent` — dual-table support

Add a new model in `models.py` (alongside `TableSchema`):

```python
class SlideTablePlan(BaseModel):
    """1 or 2 table schemas for a single data_table slide."""
    tables: List[TableSchema] = Field(
        min_length=1, max_length=2,
        description="1 or 2 TableSchema objects for the slide"
    )
    layout_hint: Literal["single", "top_bottom"] = "single"
    rationale: str = ""
```

Note: `min_length`/`max_length` enforces exactly 1-2 tables at the Pydantic validation level.

Add `run_multi()` method to `TableSchemaAgent`:

```python
def run_multi(self, slide_plan, schema_registry, theme=None) -> SlideTablePlan:
    """Generate 1-2 table schemas for a slide. Falls back to single-table."""
    # Try structured output with SlideTablePlan response model
    # If it fails or returns empty, fall back to existing run() → wrap in SlideTablePlan
```

The prompt gets an additional instruction:
> "If the slide topic naturally splits into two complementary views (e.g., 'AUM by segment' + 'Growth by segment', or 'Equity funds' + 'Debt funds'), output TWO TableSchema objects in the tables array. Otherwise output ONE. Maximum 2 tables per slide. Set layout_hint to 'top_bottom' for 2 tables or 'single' for 1."

#### 4. Orchestrator `_enrich_data_table_slides()` — rewrite

Current flow: `DataTableEngine.run()` per slide → fallback to rich pipeline → fallback to LLM extraction.

New flow with proper per-slide error handling and resource cleanup:

```python
def _enrich_data_table_slides(self, slides, data_files):
    self._set_status("generating", "Extracting table data from Excel files")

    primary_file = data_files[0]
    # NOTE: Only first file is used. Multi-file support is out of scope.

    # Step 1: Load Excel into DuckDB in-memory (once)
    try:
        local_db = DuckDBLocalConnector()
        schema_registry = local_db.load_file(primary_file)
    except Exception as e:
        self._log.warning(f"DuckDB local load failed: {e}, falling back to DataTableEngine")
        self._enrich_data_table_slides_pandas_fallback(slides, primary_file)
        return

    try:
        for i, slide in enumerate(slides):
            if i >= len(self._slide_contents):
                continue
            if slide.visual_type not in ("data_table", "multi_class_table"):
                continue

            content = self._slide_contents[i]

            # ── Primary path: SQL pipeline ──
            try:
                # Step 2: Plan table schemas
                slide_table_plan = self._table_schema_agent.run_multi(
                    slide, schema_registry, theme=self._selected_theme
                )

                # Step 3: For each schema, query + format
                table_results = []
                for schema in slide_table_plan.tables:
                    query_agent = QueryAgent(
                        llm=self._llm,
                        duckdb_connector=local_db,
                        settings=self._settings,
                    )
                    df, sql = query_agent.run(
                        schema, schema_registry, table_prefix=""
                    )
                    rich_data = ConditionalFormatEngine.compute(df, schema)
                    table_data = rich_table_to_table_data(rich_data, schema)
                    table_results.append((table_data, rich_data))

                # Step 4: Assign to content
                if len(table_results) == 1:
                    content.table_data = table_results[0][0]
                    content.rich_table_data = table_results[0][1]
                    self._log.info(
                        f"Slide {slide.id}: SQL pipeline OK "
                        f"({len(table_results[0][0].rows)} rows, "
                        f"{len(table_results[0][0].headers)} cols)"
                    )
                elif len(table_results) == 2:
                    content.dual_tables = [r[0] for r in table_results]
                    content.rich_table_data = table_results[0][1]
                    self._log.info(
                        f"Slide {slide.id}: SQL pipeline OK (dual tables)"
                    )
                continue

            except Exception as e:
                self._log.warning(
                    f"Slide {slide.id}: SQL pipeline failed ({e}), "
                    f"falling back to DataTableEngine"
                )

            # ── Fallback: DataTableEngine (pandas) ──
            try:
                table_data, rich_data = self._data_table_engine.run(
                    file_ref=primary_file,
                    slide_plan=slide,
                    topic=self.state.topic,
                    theme=self._selected_theme,
                )
                if table_data and table_data.rows:
                    content.table_data = table_data
                    if rich_data:
                        content.rich_table_data = rich_data
                    self._log.info(
                        f"Slide {slide.id}: DataTableEngine fallback OK"
                    )
                    continue
            except Exception as e2:
                self._log.warning(
                    f"Slide {slide.id}: DataTableEngine also failed ({e2})"
                )

            # ── Last resort: basic LLM extraction ──
            if not (content.table_data and content.table_data.rows):
                extracted = self._data_agent.extract_table_data(
                    primary_file, topic=self.state.topic,
                )
                if extracted:
                    content.table_data = extracted
                    self._log.info(
                        f"Slide {slide.id}: basic extraction fallback"
                    )
    finally:
        local_db.close()
```

#### 5. `SlideContent` model — dual table field

Add to `SlideContent` (in `slide_content_agent.py`):

```python
dual_tables: Optional[List[TableData]] = None  # Exactly 2 tables for top/bottom layout
```

**Precedence rules (explicit):**
- `dual_tables` → used for `data_table` slides when SQL pipeline returns 2 schemas
- `multi_class_result.tables` → used for `multi_class_table` slides (segment-classified tables)
- `table_data` → used for single-table `data_table` or `table` slides
- These are mutually exclusive per rendering path; the renderer checks in priority order

#### 6. `ppt_generator._render_data_table_slide()` — dual table rendering

```python
def _render_data_table_slide(self, plan, content):
    slide = self._add_blank_slide()
    self._add_left_accent_bar(slide)
    self._add_bottom_accent_strip(slide)
    self._add_slide_header(slide, content.title, plan.id)

    if content.dual_tables and len(content.dual_tables) == 2:
        # Two tables stacked top/bottom
        self._table_gen.add_multiple_tables(
            slide, content.dual_tables,
            left=TABLE_LEFT, top_start=TABLE_TOP,
            width=TABLE_WIDTH, total_height=TABLE_HEIGHT,
        )
    elif content.table_data and content.table_data.rows:
        # Single dense table (primary path)
        self._table_gen.add_table(
            slide, content.table_data,
            left=TABLE_LEFT, top=TABLE_TOP,
            width=TABLE_WIDTH, height=TABLE_HEIGHT,
        )
    elif getattr(content, "rich_table_data", None):
        # PNG fallback via RichTableGenerator
        png_bytes = RichTableGenerator(theme=self._theme).render(content.rich_table_data)
        slide.shapes.add_picture(
            io.BytesIO(png_bytes),
            Inches(0.3), Inches(1.2), width=Inches(12.7),
        )
    else:
        self._log.warning(
            f"No table data for data_table slide {plan.id}, falling back to bullets"
        )
        self._render_bullet_content(slide, content)

    self._add_footer_accent_line(slide)
    self._add_footer(slide, plan.id)
```

#### 7. Content prompt fix

In `content_prompts.py`, two lines must be updated consistently:

**Line 33** — change from:
> "If visual_type is 'data_table', you MUST provide table_data with all executive fields..."

To:
> "If visual_type is 'data_table' or 'multi_class_table', do NOT generate table_data — the pipeline will extract real data from the uploaded Excel file. Only generate the title, subtitle, key_message, content_bullets, and speaker_notes for these slides."

**Line 75** — change from:
> "Include table_data ONLY if visual_type is 'table' or 'data_table'."

To:
> "Include table_data ONLY if visual_type is 'table'. Do NOT include table_data for 'data_table' or 'multi_class_table' — those are handled by the data pipeline."

#### 8. `rich_table_to_table_data()` converter (NEW — in `data_table_engine.py`)

Converts `RichTableData` → `TableData` for native PPTX rendering.

```python
def _format_cell_value(val: Any, display_format: str) -> str:
    """Format a cell value using the column's display_format string.

    Handles None, non-numeric values, and format string errors gracefully.
    """
    if val is None or val == "":
        return ""
    try:
        num = float(val)
        return display_format.format(num)
    except (ValueError, TypeError, KeyError):
        return str(val)


def rich_table_to_table_data(rich: RichTableData, schema: TableSchema) -> TableData:
    """Convert RichTableData to TableData for native PPTX table rendering.

    Only includes 'diverging' CF rule columns in heatmap_columns — not 'heatmap'
    CF rules, because table_generator.py's heatmap renderer uses sign-based
    red/green coloring which is incorrect for absolute-value heatmaps.
    """
    headers = [c.header for c in schema.columns]

    # Build header_groups from column_groups
    header_groups = []
    # Find if there's a row header column
    has_row_header = any(c.is_row_header for c in schema.columns)
    col_offset = 1 if has_row_header else 0

    for group in schema.column_groups:
        header_groups.append({
            "label": group.label,
            "start_col": col_offset,
            "end_col": col_offset + group.column_span - 1,
        })
        col_offset += group.column_span

    # Build rows as formatted strings
    rows = []
    for row_dict in rich.rows:
        row = []
        for col_spec in schema.columns:
            val = row_dict.get(col_spec.data_key, "")
            row.append(_format_cell_value(val, col_spec.display_format))
        rows.append(row)

    # Detect heatmap columns — ONLY diverging CF rules (sign-based red/green)
    # Exclude 'heatmap' CF rules which are for absolute values and would be
    # incorrectly rendered as red/green by table_generator.py
    heatmap_columns = [
        i for i, c in enumerate(schema.columns)
        if any(rule.rule_type == "diverging" for rule in c.cf_rules)
    ]

    # Detect total rows using schema's grand_total_label for exact matching
    grand_total_label = schema.grand_total_label.lower() if schema.grand_total_label else "grand total"
    total_row_indices = [
        i for i, row in enumerate(rich.rows)
        if str(row.get(schema.row_header_column, "")).lower() in (
            grand_total_label, "total"
        )
    ]

    return TableData(
        title=schema.title,
        headers=headers,
        rows=rows,
        header_groups=header_groups,
        heatmap_columns=heatmap_columns,
        total_row_indices=total_row_indices,
        source_annotation=schema.source_note or "",
    )
```

---

## Files Changed

| File | Change | Type |
|------|--------|------|
| `db/duckdb_local.py` | New DuckDBLocalConnector class (context manager, Excel+CSV) | NEW |
| `orchestrator.py` | Rewrite `_enrich_data_table_slides()` with SQL primary + per-slide fallback | MODIFY |
| `agents/table_schema_agent.py` | Add `run_multi()` returning `SlideTablePlan` | MODIFY |
| `agents/query_agent.py` | Add `table_prefix` param to `run()`, `_ask_for_correction()` | MODIFY |
| `agents/data_table_engine.py` | Add `rich_table_to_table_data()` + `_format_cell_value()` | MODIFY |
| `agents/slide_content_agent.py` | Add `dual_tables` field to `SlideContent` | MODIFY |
| `models.py` | Add `SlideTablePlan` model (next to `TableSchema`) | MODIFY |
| `generators/ppt_generator.py` | Support `dual_tables` in `_render_data_table_slide()` | MODIFY |
| `prompts/content_prompts.py` | Lines 33+75: stop LLM generating table_data for data_table | MODIFY |
| `prompts/query_prompts.py` | Fix inconsistent prefixes, parameterize with `{table_prefix}` | MODIFY |
| `prompts/table_schema_prompts.py` | Add dual-table instruction to system prompt | MODIFY |

## What stays unchanged

- `table_generator.py` — Already supports header_groups, heatmap, totals, `add_multiple_tables()`
- `rich_table_generator.py` — PNG fallback path stays intact
- `conditional_format_engine.py` — No changes needed
- `DataTableEngine` — Kept as per-slide fallback if SQL pipeline fails for a specific slide
- `PGLoader` / `DuckDBConnector` — Not removed; still available for PG users (gets corrected table_prefix via orchestrator routing)

## Known limitations

- **Single-file only**: Only `data_files[0]` is loaded. Multi-file support is out of scope.
- **DuckDB version**: Uses `CREATE TABLE AS SELECT * FROM df` registration pattern (works in DuckDB 0.9+). Pin duckdb>=0.9.0 in requirements.txt.

## Error handling

All error handling is **per-slide with layered fallbacks**:

1. If `DuckDBLocalConnector.load_file()` fails entirely → `_enrich_data_table_slides_pandas_fallback()` runs the old `DataTableEngine` path for all slides
2. If SQL pipeline fails for a specific slide → that slide falls back to `DataTableEngine.run()`
3. If `DataTableEngine` also fails → falls back to `_data_agent.extract_table_data()` (basic LLM extraction)
4. If all fail → slide gets bullet-point rendering at render time
5. `DuckDBLocalConnector` is wrapped in `try/finally` for guaranteed resource cleanup
6. Each fallback is logged with the specific exception that triggered it

## Testing approach

No automated tests in this codebase. Manual verification:
1. Run with the Kotak Excel file → verify data_table slides have 10+ rows, multi-segment columns, conditional formatting
2. Compare output against `test_data_table.pptx` structure
3. Test dual-table slides by providing a topic that naturally splits
4. Test without Excel file → verify no regression on non-data-table slides
5. Test with CSV file → verify CSV loading works
6. Test PG path still works if PG is available (table_prefix="pg.ppt_data.")
