# Phase 1: Models

**Requirements:** TABLE-01, TABLE-02

## Tasks

### 1. Add TableStructure models to models.py

**Task:** Add enums and models for advanced table structure schema

**Implementation:**
```python
# ── Advanced Table Structure Models ─────────────────────────

class HeaderLevel(str, Enum):
    """Header hierarchy level for multi-level grouped tables."""
    SUPER = "super"
    SUB = "sub"
    LEAF = "leaf"


class ConditionalFormatType(str, Enum):
    """Type of conditional formatting for a column."""
    HEATMAP_DIVERGING = "heatmap_diverging"
    HEATMAP_SEQUENTIAL = "heatmap_sequential"
    THRESHOLD = "threshold"
    NONE = "none"


class NumberFormat(str, Enum):
    """Number format for displaying values."""
    INTEGER = "integer"
    DECIMAL_1 = "decimal_1"
    DECIMAL_2 = "decimal_2"
    PERCENTAGE = "percentage"
    PERCENTAGE_INT = "percentage_int"
    CURRENCY_CR = "currency_cr"
    RAW = "raw"


class ColumnSpec(BaseModel):
    """Specification for a single data column (leaf-level)."""
    id: str = Field(description="Unique column identifier")
    display_name: str = Field(description="Display text for this column header")
    source_column: Optional[str] = Field(default=None, description="Column name in source DataFrame")
    computation: Optional[str] = Field(default=None, description="Formula for computed columns")
    number_format: NumberFormat = Field(default=NumberFormat.INTEGER)
    conditional_format: ConditionalFormatType = Field(default=ConditionalFormatType.NONE)
    width_weight: float = Field(default=1.0, description="Relative width weight")
    text_alignment: str = Field(default="center")


class HeaderGroup(BaseModel):
    """A group header that spans multiple sub-headers or leaf columns."""
    id: str
    display_name: str
    level: HeaderLevel
    children: list["HeaderGroup | ColumnSpec"] = Field(default_factory=list)
    background_color: Optional[str] = None
    text_color: Optional[str] = None


class RowStyleRule(BaseModel):
    """Conditional styling for specific rows."""
    match_type: str = Field(description="'total', 'subtotal', 'first_n', 'last_n', 'value_match'")
    match_value: Optional[str] = None
    match_column: Optional[str] = None
    bold: bool = False
    background_color: Optional[str] = None
    text_color: Optional[str] = None
    font_size_delta: int = Field(default=0)
    top_border: bool = False
    bottom_border: bool = False


class HeatmapConfig(BaseModel):
    """Configuration for heatmap conditional formatting."""
    min_color: str = Field(default="#FF6B6B", description="Color for minimum/most negative")
    mid_color: str = Field(default="#FFFFCC", description="Color for zero/middle")
    max_color: str = Field(default="#4CAF50", description="Color for maximum/most positive")
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    center_value: float = Field(default=0.0, description="Center point for diverging")


class TableStructureSchema(BaseModel):
    """Complete table structure definition from TableStructureAgent."""
    table_id: str = Field(description="Unique identifier for this table")
    title: Optional[str] = None
    header_tree: list["HeaderGroup | ColumnSpec"] = Field(
        description="Root-level header structure"
    )
    row_label_column: str
    row_label_display_name: str = ""
    sort_by: Optional[str] = None
    sort_descending: bool = True
    max_rows: Optional[int] = None
    row_styles: list[RowStyleRule] = Field(default_factory=list)
    heatmap_config: HeatmapConfig = Field(default_factory=HeatmapConfig)
    alternate_row_shading: bool = True
    header_height_pts: int = 36
    data_row_height_pts: int = 28
    font_size_header: int = 11
    font_size_data: int = 10
    table_width_inches: Optional[float] = None
    table_left_inches: Optional[float] = None
    table_top_inches: Optional[float] = None
```

### 2. Add DataReference model

**Task:** Add lightweight reference for DataFrame storage

**Implementation:**
```python
class DataReference(BaseModel):
    """Lightweight reference to a DataFrame stored in orchestrator DataStore."""
    store_key: str = Field(description="Unique key in orchestrator's DataStore dict")
    source_file: Optional[str] = Field(default=None, description="Original file path")
    sheet_name: Optional[str] = Field(default=None, description="Sheet name for Excel")
```

### 3. Update SlideContent class

**Task:** Add table_structure and data_reference fields to SlideContent

**Location:** `ppt_builder/agents/slide_content_agent.py`

**Implementation:**
```python
class SlideContent(_SlideContentLLM):
    # ... existing fields ...
    
    table_structure: Optional[TableStructureSchema] = Field(
        default=None,
        description="Advanced multi-level table structure from TableStructureAgent"
    )
    data_reference: Optional[DataReference] = Field(
        default=None,
        description="Reference to raw DataFrame in orchestrator DataStore"
    )
```

## Verification

1. All models import without errors
2. Models serialize/deserialize correctly
3. SlideContent accepts new fields
4. `ruff check .` passes
