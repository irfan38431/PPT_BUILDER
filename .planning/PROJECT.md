# PPT Builder

## What This Is

Streamlit-based AI agent pipeline that generates consultant-quality PowerPoint presentations using Google Gemini. Takes a topic, runs multi-source research, builds a narrative storyline, generates slide content, and renders a themed .pptx file with charts, tables, and infographics.

## Core Value

Generate boardroom-ready PowerPoint presentations that convey complex financial/analytical data with professional visual design and minimal manual effort.

## Current Milestone: v1.0 Advanced Multi-Level Table Agent

**Goal:** Add AI-powered multi-level grouped header tables with heatmap conditional formatting to the PPT Builder pipeline.

**Target features:**
- `TableStructureAgent` — LLM agent that analyzes DataFrames and produces table structure schemas with multi-level headers
- `AdvancedTableRenderer` — Native PPTX table renderer with merged cells, heatmap coloring, row styling
- `TableStructureSchema` models — Pydantic models for header hierarchy (super/sub/leaf), heatmap config, row styles
- DataStore architecture — Orchestrator-level DataFrame storage with lightweight DataReference on SlideContent
- Dedicated `run_table_structuring()` phase — Sub-phase between content generation and validation
- LayoutDecider updates — Recognize when data warrants multi-level headers
- Fail-open behavior — Existing `RichTableGenerator`/`TableGenerator` remain as fallback

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---

*Last updated: 2026-03-27 after v1.0 milestone started*
