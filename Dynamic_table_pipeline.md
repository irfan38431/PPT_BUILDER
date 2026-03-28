# Dynamic Data-Heavy Table Pipeline — Full Implementation Specification

> **Purpose:** This document is a complete, self-contained specification for an AI coding agent to implement a dynamic, data-heavy, conditionally-formatted table generation pipeline inside an existing PPT Builder codebase. The agent should read this end-to-end before writing a single line of code.

> **Context7 Note:** Before installing any library, use `context7` to resolve the latest stable version of every package listed in this spec. Do not hardcode version numbers from memory.

---

## Table of Contents

1. [High-Level Summary of the Change](#1-high-level-summary)
2. [What Changes vs What Stays the Same](#2-what-changes-vs-what-stays-the-same)
3. [New File Tree](#3-new-file-tree)
4. [Stage-by-Stage Workflow](#4-stage-by-stage-workflow)
5. [Data Models (models.py additions)](#5-data-models)
6. [Agent 1 — TableSchemaAgent](#6-agent-1--tableschemaaagent)
7. [Agent 2 — QueryAgent](#7-agent-2--queryagent)
8. [Engine — ConditionalFormatEngine](#8-engine--conditionalformatengine)
9. [DB Layer — PGLoader](#9-db-layer--pgloader)
10. [DB Layer — DuckDBConnector](#10-db-layer--duckdbconnector)
11. [Generator — RichTableGenerator](#11-generator--richtablegenerator)
12. [Orchestrator Integration](#12-orchestrator-integration)
13. [PPT Generator Integration](#13-ppt-generator-integration)
14. [Streamlit Preview Integration](#14-streamlit-preview-integration)
15. [app.py Upload Hook](#15-apppy-upload-hook)
16. [Full Library List](#16-full-library-list)
17. [Edge Cases and Error Handling](#17-edge-cases-and-error-handling)
18. [Conditional Formatting Rules Reference](#18-conditional-formatting-rules-reference)
19. [Visual Output Specification](#19-visual-output-specification)
20. [Implementation Order for the Agent](#20-implementation-order-for-the-agent)

---

## 1. High-Level Summary

### What exists today
- User uploads an Excel/CSV file during the ingest stage.
- The pipeline generates slide content via `SlideContentAgent`.
- For data-heavy slides, `NanaBananaProIntegration` calls an external image API to render the table.
- The output is a styled but static image — no dynamic conditional formatting, no AI-decided column structure.

### What this spec builds
- Excel data is uploaded into **PostgreSQL** on ingest.
- A new **TableSchemaAgent** reads the slide's subtopic and the database schema registry, then decides the full table structure (columns, groups, CF rules) using Gemini.
- A new **QueryAgent** writes a DuckDB SQL query to fetch exactly the right rows and columns for that slide.
- A **ConditionalFormatEngine** computes per-cell background and text colours based on the data values.
- A **RichTableGenerator** renders the fully formatted table as a high-resolution PNG using Matplotlib.
- The PNG is embedded into the PPTX slide by python-pptx.
- **NanaBanana is bypassed entirely for `data_table` layout slides.**

### Output target
The rendered table must match the visual quality of the reference images: multi-level column group headers, diverging red/green conditional formatting on growth columns, bold "Grand Total" rows, source note footnotes, and full dynamic rows/columns decided per-slide by the AI.

---

## 2. What Changes vs What Stays the Same

| Component | Status | Notes |
|---|---|---|
| `app.py` | Modified | Add PGLoader call on Excel upload |
| `orchestrator.py` | Modified | Branch to table pipeline for `data_table` layout |
| `models.py` | Extended | Add 6 new Pydantic models |
| `agents/table_schema_agent.py` | **NEW** | Decides table structure |
| `agents/query_agent.py` | **NEW** | Writes + executes DuckDB SQL |
| `agents/conditional_format_engine.py` | **NEW** | Computes cell colours |
| `db/pg_loader.py` | **NEW** | Excel → PostgreSQL |
| `db/duckdb_connector.py` | **NEW** | DuckDB ↔ PostgreSQL bridge |
| `generators/rich_table_generator.py` | **NEW** | Matplotlib PNG renderer |
| `generators/ppt_generator.py` | Modified | Embed table PNG instead of NanaBanana |
| `generators/slide_previewer.py` | Modified | HTML table preview |
| `slide_render_decider.py` | Modified | Bypass NanaBanana for data_table |
| `layout_decider.py` | No change | Already emits `data_table` layout type |
| `nano_banana_pro.py` | No change | Still used for non-table slides |
| `themes.py` | No change | Consumed by RichTableGenerator |
| `research_agent.py` | No change | |
| `storyline_agent.py` | No change | |
| All other existing agents | No change | |

---

## 3. New File Tree

```
project_root/
├── agents/
│   ├── table_schema_agent.py         ← NEW
│   ├── query_agent.py                ← NEW
│   ├── conditional_format_engine.py  ← NEW
│   └── ... (existing agents unchanged)
│
├── db/
│   ├── __init__.py                   ← NEW (empty)
│   ├── pg_loader.py                  ← NEW
│   └── duckdb_connector.py           ← NEW
│
├── generators/
│   ├── rich_table_generator.py       ← NEW
│   └── ... (existing generators, some modified)
│
├── models.py                         ← EXTENDED
├── orchestrator.py                   ← MODIFIED
├── app.py                            ← MODIFIED
└── requirements.txt                  ← EXTENDED
```

---

## 4. Stage-by-Stage Workflow

### Stage 0 — User Uploads Excel (Ingest)

```
User uploads file in Streamlit UI
    ↓
app.py reads file with pandas (all sheets)
    ↓
PGLoader.upload(sheets_dict, session_id)
    ├── Creates one PG table per sheet: {session_id}_{sheet_name_slugified}
    └── Writes _schema_registry table with column metadata + sample values
    ↓
schema_registry stored in st.session_state.schema_registry
    ↓
DuckDBConnector initialised, stored in st.session_state.duckdb_conn
```

### Stage 1 — Layout Decision (existing, no change)

```
LayoutDecider runs per slide
    ↓
For slides where data is tabular/comparative → assigns layout_type = "data_table"
```

### Stage 2 — Table Structure Planning (NEW)

```
Orchestrator detects layout_type == "data_table"
    ↓
TableSchemaAgent.run(slide_plan, schema_registry)
    ├── Sends slide title + subtopic + schema_registry to Gemini
    ├── Gemini decides: which table, which columns, column groups, CF rules, sort order
    └── Returns: TableSchema (Pydantic model)
```

### Stage 3 — Data Fetching (NEW)

```
QueryAgent.run(table_schema, schema_registry, duckdb_conn)
    ├── Sends TableSchema + schema_registry to Gemini
    ├── Gemini writes DuckDB SQL query
    ├── QueryAgent executes SQL via DuckDBConnector
    ├── On failure: retry once with error message fed back to Gemini
    └── Returns: (pd.DataFrame, sql_string)
```

### Stage 4 — Conditional Formatting (NEW)

```
ConditionalFormatEngine.compute(dataframe, table_schema)
    ├── Iterates each column's CFRule list
    ├── Computes per-cell background colour (diverging / heatmap / threshold / top-n)
    ├── Computes per-cell text colour
    ├── Applies highlight_rows formatting (bold + darker bg)
    └── Returns: RichTableData (schema + rows + cell_colors + cell_text_colors)
```

### Stage 5 — PNG Rendering (NEW)

```
RichTableGenerator.render(rich_table_data, presentation_theme)
    ├── Computes figure dimensions from column count + row count
    ├── Renders multi-level group headers (FancyBboxPatch)
    ├── Renders column header row
    ├── Renders each data row with per-cell colour fills and formatted values
    ├── Renders Grand Total row (bold, heavier border)
    ├── Renders source note footnote
    └── Returns: bytes (PNG image)
```

### Stage 6 — PPTX Embedding (Modified)

```
ppt_generator.py detects slide.rich_table_data is set
    ↓
Calls RichTableGenerator.render() → gets PNG bytes
    ↓
slide.shapes.add_picture(BytesIO(png_bytes), left, top, width, height)
    ↓
NanaBanana call is SKIPPED entirely for this slide
```

### Stage 7 — Streamlit Preview (Modified)

```
SlidePreviewRenderer detects rich_table_data
    ↓
Renders HTML <table> with inline style="background-color: ..." per cell
    ↓
User sees live conditional-formatted preview before downloading PPTX
```

---

## 5. Data Models

Add all of the following to `models.py`. Do not modify existing models — only append.

### 5.1 CFRuleType

```python
from typing import Literal

CFRuleType = Literal[
    "diverging",
    "heatmap",
    "threshold",
    "highlight_top_n",
    "highlight_bottom_n",
    "text_match"
]
```

### 5.2 CFRule

```python
from pydantic import BaseModel
from typing import Optional

class CFRule(BaseModel):
    column: str
    # "diverging"  → green for positive, red for negative (used for growth/change cols)
    # "heatmap"    → single-direction gradient low→high (used for absolute value cols)
    # "threshold"  → above/below a fixed number
    # "highlight_top_n" / "highlight_bottom_n" → rank-based
    # "text_match" → colour text when string contains pattern
    rule_type: CFRuleType
    positive_color: str = "#4CAF50"       # hex, default green
    negative_color: str = "#F44336"       # hex, default red
    neutral_color: str = "#FFFFFF"        # hex, default white
    threshold: Optional[float] = None     # used for "threshold" rule_type
    top_n: Optional[int] = None           # used for top/bottom N
    text_pattern: Optional[str] = None   # used for "text_match"
    apply_to_text: bool = False           # True = colour text, False = colour background
    apply_to_background: bool = True
```

### 5.3 ColumnSpec

```python
from typing import Literal

class ColumnSpec(BaseModel):
    header: str                            # Display label shown in column header row
    data_key: str                          # Matches the SQL result column name exactly
    display_format: str = "{}"             # Python format string e.g. "{:,.0f}", "{:.1%}", "+{:,.0f}"
    width_ratio: float = 1.0              # Relative width weight; renderer normalises across all columns
    alignment: Literal["left", "center", "right"] = "right"
    is_row_header: bool = False           # True for the leftmost label column
    cf_rules: list[CFRule] = []
    bold: bool = False                    # Force bold for this entire column
```

### 5.4 RowGroup

```python
class RowGroup(BaseModel):
    label: str                            # e.g. "Corporate", "HNI", "Retail"
    column_span: int                      # How many ColumnSpec columns this group covers
    bg_color: str = "#C0392B"            # Header background colour (hex)
    text_color: str = "#FFFFFF"          # Header text colour (hex)
    border_color: str = "#FFFFFF"        # Border between groups
```

### 5.5 TableSchema

```python
from typing import Optional

class TableSchema(BaseModel):
    title: str
    subtitle: Optional[str] = None
    source_tables: list[str]             # PG table names to query (e.g. ["session_abc_sheet1"])
    row_header_column: str               # data_key of the leftmost label column
    column_groups: list[RowGroup] = []   # Multi-level headers; empty = single header row
    columns: list[ColumnSpec]            # Ordered list of all output columns
    sort_by: Optional[str] = None        # data_key to sort rows by
    sort_ascending: bool = False
    show_grand_total: bool = True
    grand_total_label: str = "Grand Total"
    highlight_rows: list[str] = []       # Row label values to bold (e.g. ["Grand Total"])
    source_note: Optional[str] = None
    duckdb_query_intent: str             # Human-readable brief for QueryAgent
    zebra_stripe: bool = True
    header_bg_color: str = "#1B2A4A"    # Dark navy default
    header_text_color: str = "#FFFFFF"
    stripe_color: str = "#F8F8F8"
    border_color: str = "#DDDDDD"
```

### 5.6 RichTableData

```python
from typing import Any, Dict, Tuple

class RichTableData(BaseModel):
    schema: TableSchema
    rows: list[Dict[str, Any]]                        # Query result as list of dicts
    cell_bg_colors: Dict[str, str] = {}               # Key: "row_idx,col_idx" → hex colour
    cell_text_colors: Dict[str, str] = {}             # Key: "row_idx,col_idx" → hex colour
    cell_bold: Dict[str, bool] = {}                   # Key: "row_idx,col_idx" → bool
    query_sql: str = ""                               # The actual SQL that was run (for debugging)
    row_count: int = 0
    col_count: int = 0

    class Config:
        # Use string keys for JSON serialisation compatibility
        pass
```

### 5.7 SlideContent extension

Find the existing `SlideContent` model in `models.py` and add one optional field:

```python
# ADD to existing SlideContent model:
rich_table_data: Optional[RichTableData] = None
```

---

## 6. Agent 1 — TableSchemaAgent

**File:** `agents/table_schema_agent.py`

### Purpose
Given a slide plan and the schema registry, decide the complete visual and structural layout of the table: which columns, which group headers, what conditional formatting, what sort order.

### Class interface

```python
class TableSchemaAgent:
    def __init__(self, llm_provider):
        self.llm = llm_provider  # existing engine/llm_provider.py wrapper

    def run(
        self,
        slide_plan: SlidePlan,
        schema_registry: dict,      # from st.session_state.schema_registry
        theme: PresentationTheme
    ) -> TableSchema:
        ...
```

### System prompt (encode verbatim)

```
You are a data table structure planner for executive PowerPoint presentations.

You receive:
1. A slide plan (title, subtopic, layout_type)
2. A schema registry listing all uploaded PostgreSQL tables with their columns, dtypes, and sample values

Your job is to output a JSON object conforming exactly to the TableSchema schema. No prose. No markdown fences. Pure JSON only.

Rules you must follow:
- Choose source_tables by matching the subtopic to the most relevant table(s) in the schema registry. If the subtopic mentions "corporate" vs "HNI" vs "retail" segments that live in separate sheets, include all relevant tables in source_tables and design the columns to support a JOIN or UNION in the query.
- The row_header_column must always map to the column that contains category labels (scheme names, fund names, asset classes, etc.) — never a numeric column.
- For any column that represents growth, change, or delta (absolute or relative), ALWAYS assign a "diverging" CF rule with positive_color="#27AE60" and negative_color="#E74C3C".
- For any column representing an absolute value (AUM, AUM in crores, etc.), assign a "heatmap" CF rule.
- If the data has multiple time periods (e.g. Mar-25, Jul-25, Aug-25), include all periods as separate columns and compute growth columns between them.
- column_groups are REQUIRED when the data has multiple investor segments (Corporate, HNI, Retail) spanning multiple columns. Set column_span accurately.
- Always set show_grand_total: true if the data is a financial or AUM table.
- Set highlight_rows to include the grand total row label exactly.
- The duckdb_query_intent field must be a single plain-English sentence describing what data to SELECT and how to group/order it. Example: "Select all debt scheme names with their Mar-25, Jul-25, Aug-25 AUM values and computed absolute and relative growth columns, ordered by Jul-25 AUM descending, with a Grand Total row."
- width_ratio for the row header column should be 2.0; for narrow numeric columns 0.8; for wider label columns 1.5.
- display_format: use "{:,.0f}" for crore values, "{:.0f}%" for percentages, "+{:,.0f}" for absolute growth columns, "{:+.0f}%" for relative growth columns.
- alignment: row header column → "left". All numeric columns → "right". Percentage columns → "center".
```

### Retry logic
Use the same retry pattern as `CriticAgent`. On JSON parse failure, send the raw output back to Gemini with the message: `"Your previous response was not valid JSON. The parse error was: {error}. Retry with valid JSON only."` Max 3 retries.

### Output validation
After parsing, validate:
- `sum(c.width_ratio for c in schema.columns)` is nonzero (do not enforce specific sum, just non-zero).
- Every `data_key` in `columns` contains only alphanumeric characters and underscores (no spaces — SQL column names).
- `len(column_groups) == 0` OR `sum(g.column_span for g in column_groups) == len(columns) - 1` (groups span all non-header columns).

---

## 7. Agent 2 — QueryAgent

**File:** `agents/query_agent.py`

### Purpose
Write a valid DuckDB SQL query that fetches exactly the data described by the `TableSchema`, execute it against PostgreSQL via DuckDB, and return a clean DataFrame.

### Class interface

```python
class DuckDBQuery(BaseModel):
    sql: str
    explanation: str   # One sentence for logging

class QueryAgent:
    def __init__(self, llm_provider, duckdb_connector):
        self.llm = llm_provider
        self.conn = duckdb_connector   # DuckDBConnector instance

    def run(
        self,
        schema: TableSchema,
        schema_registry: dict
    ) -> tuple[pd.DataFrame, str]:
        # Returns (dataframe, sql_string)
        ...
```

### System prompt (encode verbatim)

```
You are a DuckDB SQL query writer. You write analytical queries that run against PostgreSQL tables via DuckDB's postgres extension.

The tables are accessible as: pg.public.{table_name}

You receive:
1. A query_intent string describing what data to fetch
2. A TableSchema listing the exact output columns needed (data_key fields are the required SQL column aliases)
3. A schema_registry with the actual column names in the source table(s)

Your job is to output a JSON object with two fields:
  "sql": the complete DuckDB SQL query string
  "explanation": one sentence describing what it does

Rules you must follow:
- NEVER use SELECT *. Name every column explicitly.
- Every output column alias must match a data_key in the TableSchema.columns list exactly.
- Always prefix table references: pg.public.{table_name}
- For growth columns: compute inline. Example: (jul_25 - mar_25) AS abs_growth_mar_to_jul
- For percentage growth: ROUND((jul_25 - mar_25) * 100.0 / NULLIF(mar_25, 0), 0) AS rel_growth_mar_to_jul
- Wrap the main SELECT in a CTE: WITH base AS (SELECT ...) SELECT * FROM base
- If show_grand_total is true, append: UNION ALL SELECT 'Grand Total', SUM(col1), SUM(col2), ... FROM base
- ORDER BY must match TableSchema.sort_by if set; otherwise ORDER BY the row_header_column ASC. Grand Total row must always be last (use UNION ALL after ORDER BY, or use a sort key).
- To force Grand Total last: add a sort_key column: 0 for data rows, 1 for grand total, then ORDER BY sort_key, {sort_column}. Exclude sort_key from final SELECT.
- If multiple tables need to be JOINed or UNIONed (e.g. Corporate + HNI sheets), do it inside the CTE.
- Output ONLY the JSON object. No markdown. No explanation outside the JSON.
```

### Execution logic

```python
def _execute_with_retry(self, sql: str) -> pd.DataFrame:
    try:
        return self.conn.run_query(sql)
    except Exception as e:
        # Retry: feed error back to Gemini
        corrected = self._ask_for_correction(sql, str(e))
        return self.conn.run_query(corrected.sql)

def _ask_for_correction(self, failed_sql: str, error: str) -> DuckDBQuery:
    correction_prompt = f"""
    The following DuckDB SQL failed with error: {error}

    Failed SQL:
    {failed_sql}

    Fix the SQL and return the corrected JSON object with "sql" and "explanation" fields only.
    """
    # Call LLM with correction_prompt, parse DuckDBQuery
    ...
```

### Post-processing

After receiving the DataFrame:
- Strip any `sort_key` helper column if present.
- Convert all numeric columns to their appropriate Python types (`pd.to_numeric(errors='coerce')`).
- Fill NaN values: numeric columns → `0`, string columns → `""`.
- Validate that all `data_key` values from the schema appear as DataFrame columns. If any are missing, raise `QueryResultMismatchError`.

---

## 8. Engine — ConditionalFormatEngine

**File:** `agents/conditional_format_engine.py`

This is pure deterministic Python — no AI calls.

### Class interface

```python
class ConditionalFormatEngine:

    @staticmethod
    def compute(
        df: pd.DataFrame,
        schema: TableSchema
    ) -> RichTableData:
        ...
```

### Algorithm detail

```python
import numpy as np
import matplotlib.colors as mcolors

def _interpolate_color(value_norm: float, color_low: str, color_high: str) -> str:
    """value_norm is 0.0 to 1.0. Returns hex colour."""
    low = np.array(mcolors.to_rgb(color_low))
    high = np.array(mcolors.to_rgb(color_high))
    blended = low + (high - low) * value_norm
    return mcolors.to_hex(blended)

def _diverging(value: float, col_min: float, col_max: float, rule: CFRule) -> str:
    """Maps a value through a diverging red/white/green scale."""
    if value >= 0:
        # Normalise 0→col_max to 0→1
        norm = value / col_max if col_max != 0 else 0
        return _interpolate_color(norm, rule.neutral_color, rule.positive_color)
    else:
        # Normalise col_min→0 to 1→0
        norm = abs(value) / abs(col_min) if col_min != 0 else 0
        return _interpolate_color(norm, rule.neutral_color, rule.negative_color)

def _heatmap(value: float, col_min: float, col_max: float, rule: CFRule) -> str:
    rng = col_max - col_min
    norm = (value - col_min) / rng if rng != 0 else 0
    return _interpolate_color(norm, rule.neutral_color, rule.positive_color)
```

### Processing loop

```python
cell_bg_colors = {}
cell_text_colors = {}
cell_bold = {}

for col_idx, col_spec in enumerate(schema.columns):
    if col_spec.is_row_header:
        continue

    col_data = pd.to_numeric(df[col_spec.data_key], errors='coerce').fillna(0)
    col_min, col_max = col_data.min(), col_data.max()

    for rule in col_spec.cf_rules:
        for row_idx, value in enumerate(col_data):
            key = f"{row_idx},{col_idx}"

            if rule.rule_type == "diverging":
                color = _diverging(value, col_min, col_max, rule)
            elif rule.rule_type == "heatmap":
                color = _heatmap(value, col_min, col_max, rule)
            elif rule.rule_type == "threshold":
                color = rule.positive_color if value >= rule.threshold else rule.negative_color
            elif rule.rule_type == "highlight_top_n":
                top_vals = col_data.nlargest(rule.top_n or 3).values
                color = rule.positive_color if value in top_vals else rule.neutral_color
            elif rule.rule_type == "highlight_bottom_n":
                bot_vals = col_data.nsmallest(rule.top_n or 3).values
                color = rule.negative_color if value in bot_vals else rule.neutral_color
            else:
                color = rule.neutral_color

            if rule.apply_to_background:
                cell_bg_colors[key] = color
            if rule.apply_to_text:
                cell_text_colors[key] = color

# Apply highlight_rows (bold + slightly darker bg)
for row_idx, row in enumerate(df.to_dict('records')):
    row_label = str(row.get(schema.row_header_column, ""))
    if row_label in schema.highlight_rows:
        for col_idx in range(len(schema.columns)):
            key = f"{row_idx},{col_idx}"
            cell_bold[key] = True
            # Darken existing bg by 15%
            existing = cell_bg_colors.get(key, "#FFFFFF")
            rgb = np.array(mcolors.to_rgb(existing))
            darkened = rgb * 0.85
            cell_bg_colors[key] = mcolors.to_hex(darkened)
```

---

## 9. DB Layer — PGLoader

**File:** `db/pg_loader.py`

### Purpose
Upload all sheets from an Excel/CSV file into PostgreSQL. Write a schema registry table.

### Class interface

```python
from sqlalchemy import create_engine, text
import pandas as pd
import json
import re

class PGLoader:
    def __init__(self, connection_string: str):
        # connection_string = "postgresql+psycopg2://user:pass@host:port/dbname"
        self.engine = create_engine(connection_string)

    def upload(
        self,
        sheets: dict[str, pd.DataFrame],   # {sheet_name: dataframe}
        session_id: str
    ) -> dict:
        # Returns schema_registry dict for st.session_state
        ...
```

### Implementation

```python
def _slugify(self, name: str) -> str:
    return re.sub(r'[^a-z0-9_]', '_', name.lower().strip())[:50]

def upload(self, sheets, session_id):
    schema_registry = {}
    sid = self._slugify(session_id)

    with self.engine.begin() as conn:
        # Drop old session tables first (idempotent re-upload)
        existing = conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE tablename LIKE :prefix",
            {"prefix": f"{sid}_%"}
        )).fetchall()
        for (tname,) in existing:
            conn.execute(text(f'DROP TABLE IF EXISTS "{tname}"'))

    for sheet_name, df in sheets.items():
        table_name = f"{sid}_{self._slugify(sheet_name)}"

        # Coerce all object columns to string for PG compatibility
        for col in df.select_dtypes(include='object').columns:
            df[col] = df[col].astype(str)

        # Write to PG
        df.to_sql(table_name, self.engine, if_exists="replace", index=False)

        # Build schema registry entry
        columns_meta = {}
        for col in df.columns:
            sample = df[col].dropna().unique()[:5].tolist()
            col_meta = {
                "dtype": str(df[col].dtype),
                "sample_values": [str(v) for v in sample],
            }
            if pd.api.types.is_numeric_dtype(df[col]):
                col_meta["min"] = float(df[col].min())
                col_meta["max"] = float(df[col].max())
            columns_meta[col] = col_meta

        schema_registry[table_name] = {
            "sheet_name": sheet_name,
            "row_count": len(df),
            "columns": columns_meta
        }

    # Write schema registry to PG for agent access
    registry_df = pd.DataFrame([
        {"table_name": k, "metadata_json": json.dumps(v)}
        for k, v in schema_registry.items()
    ])
    registry_df.to_sql(
        f"{sid}_schema_registry",
        self.engine,
        if_exists="replace",
        index=False
    )

    return schema_registry
```

---

## 10. DB Layer — DuckDBConnector

**File:** `db/duckdb_connector.py`

### Purpose
Bridge DuckDB's analytical engine to the PostgreSQL database so QueryAgent can run fast analytical SQL against stored data.

### Class interface

```python
import duckdb
import pandas as pd

class DuckDBConnector:
    def __init__(self, pg_connection_string: str):
        # pg_connection_string format for DuckDB:
        # "dbname=mydb user=myuser password=mypass host=localhost port=5432"
        self.pg_conn_str = pg_connection_string
        self._conn = None

    def connect(self):
        self._conn = duckdb.connect()
        self._conn.execute("INSTALL postgres; LOAD postgres;")
        self._conn.execute(
            f"ATTACH '{self.pg_conn_str}' AS pg (TYPE POSTGRES, READ_ONLY);"
        )

    def run_query(self, sql: str) -> pd.DataFrame:
        if self._conn is None:
            self.connect()
        return self._conn.execute(sql).df()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
```

### Important notes for the agent
- DuckDB's PostgreSQL extension requires the postgres scanner to be installed. The `INSTALL postgres` call downloads it on first run — ensure the environment has internet access or the extension is pre-bundled.
- Table references in queries must use `pg.public.{table_name}` prefix.
- DuckDB in-process connections are not thread-safe. If Streamlit runs in multi-threaded mode, store one connection per session in `st.session_state.duckdb_conn` rather than a global singleton.

---

## 11. Generator — RichTableGenerator

**File:** `generators/rich_table_generator.py`

### Purpose
Render a `RichTableData` object into a high-resolution PNG image using Matplotlib. This image is then embedded into the PPTX slide.

### Class interface

```python
import matplotlib
matplotlib.use('Agg')   # MUST be set before any other matplotlib imports
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.font_manager import FontProperties
import numpy as np
import io
from typing import Optional

class RichTableGenerator:

    # Physical rendering constants
    DPI = 150
    ROW_HEIGHT_INCHES = 0.45      # Height per data row
    HEADER_ROW_HEIGHT = 0.55      # Height of the column header row
    GROUP_ROW_HEIGHT = 0.40       # Height of the column group header row
    CELL_PADDING_X = 0.08         # Inches of horizontal padding inside each cell
    MIN_FIGURE_WIDTH = 10.0       # Minimum figure width in inches
    MAX_FIGURE_WIDTH = 20.0       # Maximum figure width (wide tables)

    def __init__(self, theme=None):
        self.theme = theme   # PresentationTheme from themes.py; can be None

    def render(self, data: RichTableData) -> bytes:
        # Returns PNG bytes
        ...
```

### Layout computation

```python
def _compute_layout(self, data: RichTableData) -> dict:
    n_cols = len(data.schema.columns)
    n_rows = data.row_count
    has_groups = len(data.schema.column_groups) > 0

    # Normalise width ratios to actual column widths in inches
    total_ratio = sum(c.width_ratio for c in data.schema.columns)
    # Target total width based on column count
    target_width = min(max(n_cols * 1.4, self.MIN_FIGURE_WIDTH), self.MAX_FIGURE_WIDTH)
    col_widths = [(c.width_ratio / total_ratio) * target_width for c in data.schema.columns]

    # Figure height
    n_header_rows = 2 if has_groups else 1
    fig_height = (
        n_header_rows * self.HEADER_ROW_HEIGHT
        + n_rows * self.ROW_HEIGHT_INCHES
        + 0.4   # source note
        + 0.3   # title
    )

    return {
        "fig_width": target_width,
        "fig_height": fig_height,
        "col_widths": col_widths,
        "col_positions": [sum(col_widths[:i]) for i in range(n_cols)],
        "n_header_rows": n_header_rows,
        "has_groups": has_groups,
    }
```

### Rendering approach — DO NOT use ax.table()

Use `matplotlib.patches.FancyBboxPatch` for cells and `ax.text()` for content. All coordinates are in data units (inches), with the origin at bottom-left. Flip y-axis so rows render top-to-bottom.

```python
def _draw_cell(
    self,
    ax,
    x: float, y: float,          # bottom-left corner of cell
    w: float, h: float,           # width and height
    bg_color: str,
    text: str,
    text_color: str = "#1A1A1A",
    bold: bool = False,
    alignment: str = "right",
    font_size: float = 8.5,
    border_color: str = "#CCCCCC",
    border_width: float = 0.5,
):
    # Draw background rectangle
    rect = mpatches.FancyBboxPatch(
        (x, y), w, h,
        boxstyle="square,pad=0",
        facecolor=bg_color,
        edgecolor=border_color,
        linewidth=border_width,
        transform=ax.transData,
        clip_on=False,
    )
    ax.add_patch(rect)

    # Compute text x position based on alignment
    if alignment == "left":
        tx = x + self.CELL_PADDING_X
        ha = "left"
    elif alignment == "center":
        tx = x + w / 2
        ha = "center"
    else:  # right
        tx = x + w - self.CELL_PADDING_X
        ha = "right"

    ty = y + h / 2  # vertical centre

    fp = FontProperties(weight='bold' if bold else 'normal', size=font_size)
    ax.text(
        tx, ty, text,
        ha=ha, va='center',
        color=text_color,
        fontproperties=fp,
        clip_on=False,
    )
```

### Full render method

```python
def render(self, data: RichTableData) -> bytes:
    layout = self._compute_layout(data)

    fig, ax = plt.subplots(figsize=(layout["fig_width"], layout["fig_height"]))
    ax.set_xlim(0, layout["fig_width"])
    ax.set_ylim(0, layout["fig_height"])
    ax.axis('off')

    schema = data.schema
    col_positions = layout["col_positions"]
    col_widths = layout["col_widths"]

    # Current y cursor starts near the top
    y_cursor = layout["fig_height"] - 0.25  # leave room for title

    # --- Column Group Header Row (if any) ---
    if layout["has_groups"]:
        y_cursor -= layout["GROUP_ROW_HEIGHT"]
        x_cursor = col_positions[0]

        # First: draw a blank cell for the row header column
        rh_width = col_widths[0]
        self._draw_cell(ax, x_cursor, y_cursor, rh_width, self.GROUP_ROW_HEIGHT,
                        bg_color=schema.header_bg_color, text="",
                        border_color=schema.border_color)
        x_cursor += rh_width

        # Then: draw group header cells (spanning multiple columns)
        col_offset = 1  # skip row_header column
        for group in schema.column_groups:
            group_width = sum(col_widths[col_offset:col_offset + group.column_span])
            self._draw_cell(
                ax, x_cursor, y_cursor, group_width, self.GROUP_ROW_HEIGHT,
                bg_color=group.bg_color,
                text=group.label,
                text_color=group.text_color,
                bold=True,
                alignment="center",
                font_size=9.0,
                border_color=group.border_color,
            )
            x_cursor += group_width
            col_offset += group.column_span

    # --- Column Header Row ---
    y_cursor -= self.HEADER_ROW_HEIGHT
    for col_idx, col_spec in enumerate(schema.columns):
        self._draw_cell(
            ax,
            col_positions[col_idx], y_cursor,
            col_widths[col_idx], self.HEADER_ROW_HEIGHT,
            bg_color=schema.header_bg_color,
            text=col_spec.header,
            text_color=schema.header_text_color,
            bold=True,
            alignment="center",
            font_size=8.5,
            border_color=schema.border_color,
        )

    # --- Data Rows ---
    for row_idx, row_data in enumerate(data.rows):
        y_cursor -= self.ROW_HEIGHT_INCHES
        stripe_bg = schema.stripe_color if (row_idx % 2 == 1 and schema.zebra_stripe) else "#FFFFFF"

        for col_idx, col_spec in enumerate(schema.columns):
            cell_key = f"{row_idx},{col_idx}"
            bg_color = data.cell_bg_colors.get(cell_key, stripe_bg)
            text_color = data.cell_text_colors.get(cell_key, "#1A1A1A")
            is_bold = data.cell_bold.get(cell_key, col_spec.bold)

            # Format value
            raw_value = row_data.get(col_spec.data_key, "")
            try:
                if col_spec.is_row_header:
                    display_text = str(raw_value)
                elif col_spec.display_format and raw_value != "" and raw_value is not None:
                    numeric = float(raw_value)
                    display_text = col_spec.display_format.format(numeric)
                else:
                    display_text = str(raw_value) if raw_value is not None else ""
            except (ValueError, TypeError):
                display_text = str(raw_value) if raw_value is not None else ""

            self._draw_cell(
                ax,
                col_positions[col_idx], y_cursor,
                col_widths[col_idx], self.ROW_HEIGHT_INCHES,
                bg_color=bg_color,
                text=display_text,
                text_color=text_color,
                bold=is_bold,
                alignment=col_spec.alignment,
                font_size=8.0,
                border_color=schema.border_color,
            )

    # --- Source Note ---
    if schema.source_note:
        y_cursor -= 0.3
        ax.text(
            col_positions[0], y_cursor,
            f"Source: {schema.source_note}",
            ha='left', va='top',
            color='#666666',
            style='italic',
            fontsize=7.0,
        )

    plt.tight_layout(pad=0.1)

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=self.DPI, bbox_inches='tight', transparent=False, facecolor='white')
    plt.close(fig)
    buf.seek(0)
    return buf.read()
```

---

## 12. Orchestrator Integration

**File:** `orchestrator.py`

### Where to add the branch

Inside the content generation stage, find the section where `SlideContentAgent` is called per slide. Add a conditional branch before it:

```python
# In the generating stage, inside the per-slide loop:

from agents.table_schema_agent import TableSchemaAgent
from agents.query_agent import QueryAgent
from agents.conditional_format_engine import ConditionalFormatEngine
from generators.rich_table_generator import RichTableGenerator

for slide_plan in pipeline_state.slide_plans:

    if slide_plan.layout_type == "data_table":
        try:
            # 1. Decide table structure
            schema = TableSchemaAgent(self.llm).run(
                slide_plan=slide_plan,
                schema_registry=pipeline_state.schema_registry,
                theme=pipeline_state.theme
            )

            # 2. Fetch data
            df, sql = QueryAgent(self.llm, pipeline_state.duckdb_conn).run(
                schema=schema,
                schema_registry=pipeline_state.schema_registry
            )

            # 3. Compute conditional formatting
            rich_table_data = ConditionalFormatEngine.compute(df, schema)
            rich_table_data.query_sql = sql
            rich_table_data.row_count = len(df)
            rich_table_data.col_count = len(schema.columns)

            # 4. Attach to slide content
            slide_content = SlideContent(
                slide_id=slide_plan.slide_id,
                title=slide_plan.title,
                layout_type="data_table",
                rich_table_data=rich_table_data,
            )
            pipeline_state.slide_contents.append(slide_content)

        except Exception as e:
            logger.error(f"Table pipeline failed for slide {slide_plan.slide_id}: {e}")
            slide_content = SlideContent(
                slide_id=slide_plan.slide_id,
                title=slide_plan.title,
                layout_type="data_table",
                needs_manual_review=True,
                review_note=f"Table generation failed: {str(e)}"
            )
            pipeline_state.slide_contents.append(slide_content)

    else:
        # Existing SlideContentAgent path — no change
        slide_content = SlideContentAgent(self.llm).run(slide_plan, pipeline_state)
        pipeline_state.slide_contents.append(slide_content)
```

Also add `schema_registry` and `duckdb_conn` fields to `PipelineState` in `models.py`:

```python
# ADD to PipelineState:
schema_registry: dict = {}
duckdb_conn: Optional[Any] = None   # DuckDBConnector instance
```

---

## 13. PPT Generator Integration

**File:** `generators/ppt_generator.py`

### Where to add the branch

Inside `InteractivePPTGenerator`, find the per-slide rendering loop. Add a branch for `data_table`:

```python
from generators.rich_table_generator import RichTableGenerator
from pptx.util import Inches, Emu
import io

# Inside the per-slide loop in InteractivePPTGenerator:

if slide_content.layout_type == "data_table" and slide_content.rich_table_data:
    # Render table to PNG
    png_bytes = RichTableGenerator(theme=self.theme).render(slide_content.rich_table_data)

    # Define image position and size on slide
    # Typical slide is 13.33" × 7.5" (widescreen)
    # Leave top ~1.2" for slide title
    left = Inches(0.3)
    top = Inches(1.2)
    width = Inches(12.7)
    # Height is auto-calculated by add_picture when only width is specified
    slide.shapes.add_picture(io.BytesIO(png_bytes), left, top, width=width)

    # DO NOT call NanaBananaProIntegration for this slide
    continue   # skip to next slide in loop
```

### SlideRenderDecider bypass

**File:** `slide_render_decider.py` (or wherever `SlideRenderDecider` is defined)

At the top of the decision logic, add:

```python
def should_use_nano_banana(slide_content: SlideContent) -> bool:
    # NEVER use NanaBanana for data_table slides
    if slide_content.layout_type == "data_table":
        return False
    # ... existing logic follows
```

---

## 14. Streamlit Preview Integration

**File:** `generators/slide_previewer.py`

Find the HTML generation method for each slide. Add a branch for `data_table`:

```python
def _render_table_preview(self, data: RichTableData) -> str:
    schema = data.schema
    rows = data.rows

    html = ['<div style="overflow-x:auto; font-family: Arial, sans-serif; font-size: 11px;">']
    html.append('<table style="border-collapse: collapse; width: 100%;">')

    # Column group headers
    if schema.column_groups:
        html.append('<tr>')
        html.append(f'<th style="background:{schema.header_bg_color};color:{schema.header_text_color};padding:6px 8px;"></th>')
        for group in schema.column_groups:
            html.append(
                f'<th colspan="{group.column_span}" style="background:{group.bg_color};'
                f'color:{group.text_color};padding:6px 8px;text-align:center;'
                f'border:1px solid {schema.border_color};">{group.label}</th>'
            )
        html.append('</tr>')

    # Column headers
    html.append('<tr>')
    for col_spec in schema.columns:
        html.append(
            f'<th style="background:{schema.header_bg_color};color:{schema.header_text_color};'
            f'padding:6px 8px;text-align:center;border:1px solid {schema.border_color};'
            f'font-weight:bold;">{col_spec.header}</th>'
        )
    html.append('</tr>')

    # Data rows
    for row_idx, row_data in enumerate(rows):
        stripe = schema.stripe_color if row_idx % 2 == 1 and schema.zebra_stripe else "#FFFFFF"
        html.append('<tr>')
        for col_idx, col_spec in enumerate(schema.columns):
            cell_key = f"{row_idx},{col_idx}"
            bg = data.cell_bg_colors.get(cell_key, stripe)
            fg = data.cell_text_colors.get(cell_key, "#1A1A1A")
            bold = "font-weight:bold;" if data.cell_bold.get(cell_key, False) else ""
            raw = row_data.get(col_spec.data_key, "")
            try:
                if not col_spec.is_row_header and col_spec.display_format and raw != "":
                    display = col_spec.display_format.format(float(raw))
                else:
                    display = str(raw) if raw is not None else ""
            except (ValueError, TypeError):
                display = str(raw) if raw is not None else ""
            html.append(
                f'<td style="background:{bg};color:{fg};{bold}'
                f'padding:5px 8px;text-align:{col_spec.alignment};'
                f'border:1px solid {schema.border_color};">{display}</td>'
            )
        html.append('</tr>')

    html.append('</table>')
    if schema.source_note:
        html.append(f'<p style="font-size:9px;color:#888;font-style:italic;margin-top:4px;">Source: {schema.source_note}</p>')
    html.append('</div>')
    return "\n".join(html)
```

---

## 15. app.py Upload Hook

Find the ingest section in `app.py` where the user uploads files. After the existing Excel upload handling, add:

```python
from db.pg_loader import PGLoader
from db.duckdb_connector import DuckDBConnector
import os

# Get connection strings from environment variables or Streamlit secrets
PG_CONN_STR_SQLALCHEMY = os.environ.get("PG_CONN_STR_SQLALCHEMY")
# Format: "postgresql+psycopg2://user:pass@host:port/dbname"

PG_CONN_STR_DUCKDB = os.environ.get("PG_CONN_STR_DUCKDB")
# Format: "dbname=mydb user=myuser password=mypass host=localhost port=5432"

# --- In the file upload handler ---
if uploaded_excel_file is not None:
    import pandas as pd
    sheets = pd.read_excel(uploaded_excel_file, sheet_name=None)

    # Generate a stable session ID
    if "session_id" not in st.session_state:
        import uuid
        st.session_state.session_id = str(uuid.uuid4()).replace("-", "")[:12]

    with st.spinner("Uploading data to database..."):
        loader = PGLoader(PG_CONN_STR_SQLALCHEMY)
        schema_registry = loader.upload(sheets, st.session_state.session_id)
        st.session_state.schema_registry = schema_registry

    # Initialise DuckDB connector
    duckdb_conn = DuckDBConnector(PG_CONN_STR_DUCKDB)
    duckdb_conn.connect()
    st.session_state.duckdb_conn = duckdb_conn

    st.success(f"Uploaded {len(sheets)} sheet(s) to database.")
```

### Environment variables required

Add to `.env` or Streamlit secrets:
```
PG_CONN_STR_SQLALCHEMY=postgresql+psycopg2://user:password@localhost:5432/pptbuilder
PG_CONN_STR_DUCKDB=dbname=pptbuilder user=user password=password host=localhost port=5432
```

---

## 16. Full Library List

Use **context7** to resolve the latest stable version of each before adding to `requirements.txt`.

### New additions

| Library | Purpose |
|---|---|
| `duckdb` | Analytical SQL engine; queries PostgreSQL via postgres extension |
| `sqlalchemy` | ORM + connection engine for writing to PostgreSQL |
| `psycopg2-binary` | PostgreSQL driver (binary wheel; no system libpq required) |
| `numpy` | Colour interpolation math in CFEngine |
| `Pillow` | PNG export from Matplotlib BytesIO buffer |

### Already present (verify versions)

| Library | Purpose |
|---|---|
| `pandas` | DataFrame manipulation throughout |
| `openpyxl` | Excel file reading via `pd.read_excel` |
| `matplotlib` | Table rendering engine (`Agg` backend) |
| `pydantic` | Data model validation |
| `google-genai` | LLM calls in all agents |

### Context7 usage example

Before writing `requirements.txt`, the implementing agent should run:
```
# Use context7 to look up each library:
# - resolve library ID for "duckdb" → get latest docs + version
# - resolve library ID for "sqlalchemy" → get latest docs + version
# - resolve library ID for "psycopg2-binary" → get latest docs + version
# Then pin to the resolved latest stable versions.
```

---

## 17. Edge Cases and Error Handling

### 17.1 Zero-row query result

```python
# In QueryAgent.run():
if len(df) == 0:
    raise TableQueryError(
        f"Query returned 0 rows. SQL: {sql}"
    )
```

In the orchestrator catch block, set `needs_manual_review=True` and surface a warning in the Streamlit UI: `"No data found for this slide. Please check your uploaded Excel file."`.

### 17.2 Column mismatch between schema and query result

```python
# In QueryAgent, after executing:
required_keys = {c.data_key for c in schema.columns}
actual_cols = set(df.columns)
missing = required_keys - actual_cols
if missing:
    raise QueryResultMismatchError(
        f"Query result is missing expected columns: {missing}. "
        f"Got: {actual_cols}"
    )
```

### 17.3 Wide tables (more than 8 columns)

In `ppt_generator.py`, before calling `RichTableGenerator.render()`:

```python
from pptx.util import Inches
from pptx.oxml.ns import qn
from lxml import etree

# If table has > 8 columns, switch slide to landscape orientation
if data.col_count > 8:
    slide_layout = presentation.slide_layouts[6]  # blank layout
    # Swap width and height for landscape
    prs = presentation
    prs.slide_width, prs.slide_height = prs.slide_height, prs.slide_width
```

### 17.4 NaN / None values in data

All numeric columns must have NaN filled with `0` before CF computation. String columns must have NaN filled with `""`. Do this in `QueryAgent._post_process()`.

### 17.5 Division by zero in relative growth

In the SQL template for relative growth columns:
```sql
ROUND((jul_25 - mar_25) * 100.0 / NULLIF(mar_25, 0), 0) AS rel_growth
```
`NULLIF(mar_25, 0)` prevents division by zero. DuckDB returns NULL which pandas will fill to `0`.

### 17.6 Multi-user session isolation

Every table name is prefixed with a 12-character session ID derived from `uuid.uuid4()`. This prevents data from different users' uploads colliding. On session end or re-upload, old session tables are dropped first (see `PGLoader.upload()`).

### 17.7 DuckDB postgres extension not installed

Wrap `duckdb_connector.connect()` in a try/except. If the postgres extension is missing, catch the error and surface it as a `SetupError` with message: `"DuckDB postgres extension could not be installed. Ensure the container has outbound internet access for the first run, or pre-bundle the extension."`.

---

## 18. Conditional Formatting Rules Reference

| Column type | rule_type | positive_color | negative_color | neutral_color | Notes |
|---|---|---|---|---|---|
| Absolute growth (e.g. `+3,251`) | `diverging` | `#27AE60` | `#E74C3C` | `#FFFFFF` | Green if > 0, red if < 0 |
| Relative growth (e.g. `+27%`) | `diverging` | `#27AE60` | `#E74C3C` | `#FFFFFF` | Same as above |
| AUM / absolute value | `heatmap` | `#2196F3` | — | `#FFFFFF` | Low = white, high = blue |
| Rank / percentile | `highlight_top_n` | `#27AE60` | — | `#FFFFFF` | Top 3 green |
| Any threshold flag | `threshold` | `#27AE60` | `#E74C3C` | `#FFFFFF` | Set threshold from context |

### Colour intensity calibration
- For `diverging` and `heatmap` rules, the colour is interpolated linearly between `neutral_color` (at 0% of range) and `positive/negative_color` (at 100% of range).
- Very small values (close to 0% of range) will appear almost white — this is intentional, matching the reference images where cells near 0% show very light colouring.
- The Grand Total row uses the same CF colours as data rows, but with 15% darkening applied on top.

---

## 19. Visual Output Specification

The rendered PNG must match the following visual characteristics (as seen in the reference images):

### Header rows
- Outermost group header (e.g. "Corporate"): red background `#C0392B`, white text, bold, centred, full border.
- Column header row: dark navy background `#1B2A4A`, white text, bold, centred.
- Both header row heights are taller than data rows.

### Data rows
- Alternating zebra stripe: white / `#F8F9FA`.
- Row header column (scheme names): left-aligned, slightly larger font weight.
- Numeric columns: right-aligned.
- Percentage columns: centre-aligned.
- Positive growth cells: green background (interpolated), dark green text.
- Negative growth cells: red background (interpolated), dark red text.
- Near-zero cells: very light colouring, near-white.

### Grand Total row
- Bold text in all cells.
- Slightly darker background than the row's CF colour.
- Heavier bottom border (1.5px vs 0.5px for data rows).

### Typography
- Font: use the corporate font from `themes.py` if available; fall back to `DejaVu Sans`.
- Group header: 9pt bold.
- Column header: 8.5pt bold.
- Data rows: 8pt normal; bold for highlighted rows.
- Source note: 7pt italic grey.

### Image quality
- DPI: 150 (good balance of file size vs readability on slide).
- Background: solid white (no transparency) — PPTX embedding requires opaque PNG.
- `bbox_inches='tight'` in `savefig` to eliminate whitespace padding.

---

## 20. Implementation Order for the Agent

Follow this exact sequence to avoid import errors and circular dependencies:

1. **`models.py`** — Add all new Pydantic models first. Everything else depends on these.
2. **`db/__init__.py`** — Create empty file.
3. **`db/pg_loader.py`** — Implement `PGLoader`. Test with a sample Excel file.
4. **`db/duckdb_connector.py`** — Implement `DuckDBConnector`. Test by running a simple `SELECT 1`.
5. **`agents/conditional_format_engine.py`** — Implement `ConditionalFormatEngine`. Test with mock DataFrame and CFRules.
6. **`generators/rich_table_generator.py`** — Implement `RichTableGenerator`. Test by rendering a mock `RichTableData` to PNG and visually inspect.
7. **`agents/table_schema_agent.py`** — Implement `TableSchemaAgent`. Test with a sample `SlidePlan` and schema_registry.
8. **`agents/query_agent.py`** — Implement `QueryAgent`. Test end-to-end: agent writes SQL → DuckDB executes → DataFrame returned.
9. **`orchestrator.py`** — Add `data_table` branch. Test that a data_table slide produces a `RichTableData`.
10. **`generators/ppt_generator.py`** — Add PNG embedding. Test that the generated PPTX contains the table image.
11. **`slide_render_decider.py`** — Add NanaBanana bypass guard.
12. **`generators/slide_previewer.py`** — Add HTML table preview renderer.
13. **`app.py`** — Add PGLoader + DuckDBConnector initialisation on file upload.
14. **`requirements.txt`** — Add all new libraries (after resolving versions via context7).
15. **End-to-end test** — Upload a real Excel file, create a presentation with a data_table slide, verify the PNG table appears in the PPTX with conditional formatting applied.

---

*End of specification. The implementing agent has all information needed to build this pipeline without any further clarification.*