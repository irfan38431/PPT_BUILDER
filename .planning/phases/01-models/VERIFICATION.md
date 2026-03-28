# Phase 1: Models — Verification

## Verification Checklist

- [x] All new models import without errors
- [x] Models serialize/deserialize correctly  
- [x] SlideContent accepts new fields
- [x] `ruff check .` passes

## Models Added

### Enums
- `HeaderLevel` (SUPER, SUB, LEAF)
- `ConditionalFormatType` (HEATMAP_DIVERGING, HEATMAP_SEQUENTIAL, THRESHOLD, NONE)
- `NumberFormat` (INTEGER, DECIMAL_1, DECIMAL_2, PERCENTAGE, PERCENTAGE_INT, CURRENCY_CR, RAW)

### Pydantic Models
- `TableColumnSpec` — Leaf-level column specification
- `HeaderGroup` — Group header spanning multiple columns
- `RowStyleRule` — Conditional row styling
- `HeatmapConfig` — Heatmap color configuration
- `TableStructureSchema` — Complete table structure definition
- `DataReference` — Lightweight DataFrame reference

### SlideContent Updates
- Added `table_structure: Optional[TableStructureSchema]`
- Added `data_reference: Optional[DataReference]`

## Test Commands

```bash
cd ppt_builder
python -c "from models import TableStructureSchema, DataReference; print('Import OK')"
ruff check models.py agents/slide_content_agent.py
```
