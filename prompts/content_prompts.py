"""
prompts/content_prompts.py — Prompt templates for SlideContentAgent.
"""

from config import CURRENT_DATE_STR, CURRENT_YEAR

# ── Slide Content Generation ────────────────────────────────
SLIDE_CONTENT_PROMPT = """You are a presentation content writer specializing in financial decks. Generate the final content for a single slide.

**Current Date:** """ + CURRENT_DATE_STR + """

**Slide Plan:**
- Title: {slide_title}
- Layout: {layout_type}
- Visual Type: {visual_type}
- Key Insight: {key_insight}
- Content Direction: {content_bullets}
- Visual Theme: {theme_description}

**Research Data:**
{research_data}

**Rules:**
- Title must be actionable (verb + insight), max 8 words,but layman understandable.
- Bullets must be concise (max 15 words each), max 5 bullets.
- NEVER repeat the same word or phrase in a bullet or title (e.g., "SIP & SIP" is WRONG).
- Each bullet must convey a UNIQUE, distinct point — no redundancy.
- DO NOT include placeholders like "[Visual]" or "[Chart]" or "[Image]" in the content bullets.
- If visual_type is a chart, you MUST provide exact data in chart_data.
- If visual_type is a table, you MUST provide structured table data.
- Include a speaker note with the full narrative context.
- Key insight must be a single, powerful sentence.
- For charts, include up to 3 annotations highlighting significant data points with research-backed insights.
- Each annotation label_index must be a valid index within the labels array.

**Output Format (JSON):**
{{
    "title": "Finalized slide title",
    "content_bullets": ["Bullet 1", "Bullet 2"],
    "key_insight": "The one-line takeaway",
    "speaker_notes": "Detailed narrative for presenter",
    "chart_data": {{
        "title": "Chart title",
        "chart_type": "bar|line|pie|stacked_bar|grouped_bar",
        "labels": ["Label1", "Label2"],
        "datasets": [
            {{"label": "Series 1", "data": [10, 20, 30], "color": "#4A90D9"}}
        ],
        "x_axis_label": "X Axis",
        "y_axis_label": "Y Axis",
        "source_annotation": "Source: ...",
        "annotations": [
            {{"label_index": 2, "dataset_index": 0, "text": "Key insight about this data point", "annotation_type": "callout"}}
        ]
    }},
    "table_data": {{
        "title": "Table title",
        "headers": ["Col1", "Col2"],
        "rows": [["val1", "val2"]],
        "source_annotation": "Source: ..."
    }}
}}

Note: Include chart_data ONLY if visual_type is a chart type. Include table_data ONLY if visual_type is "table". Otherwise omit them.
"""

# ── Layout Decision Override ────────────────────────────────
LAYOUT_DECISION_PROMPT = """You are a presentation design consultant. Given the slide content below, confirm or override the planned visual type.

**Slide Title:** {slide_title}
**Planned Layout:** {planned_layout}
**Planned Visual:** {planned_visual}
**Content Summary:** {content_summary}
**Available Data:** {available_data}

**Decision Criteria:**
- If data has 3+ comparable categories → bar/grouped_bar chart
- If data shows trend over time → line chart
- If data shows parts of a whole → pie chart
- If data is structured comparison → table
- If content is primarily textual insights → bullet layout
- If content mixes text and visual → split layout

**Output Format (JSON):**
{{
    "recommended_layout": "bullet|chart|table|split|exec_summary|section_divider|closing",
    "recommended_visual": "bar_chart|line_chart|pie_chart|table|none",
    "reason": "Why this layout/visual is optimal",
    "changed": true/false
}}
"""

# ── Text-Heavy Infographic ────────────────────────────────
TEXT_HEAVY_INFOGRAPHIC_PROMPT = """You are a presentation content writer specializing in infographic design. Generate content for a text-heavy infographic slide.

**Current Date:** """ + CURRENT_DATE_STR + """

**Slide Plan:**
- Title: {slide_title}
- Key Insight: {key_insight}
- Content Direction: {content_bullets}

**Research Data:**
{research_data}

**Rules:**
- Title must be actionable (verb + insight), max 8 words.
- Bullets must be concise (max 15 words each), max 5 bullets.
- Key insight must be a single, powerful sentence.
- Speaker notes should include the full narrative context.
- infographic_prompt MUST be a detailed image generation prompt describing a beautiful,
  professional infographic that visualizes the slide's data and insights.
  Include layout guidance (e.g., "horizontal flow", "radial diagram", "vertical timeline"),
  color palette notes, icon suggestions, and data visualization elements.
  The prompt should specify "professional business infographic, clean modern design, 16:9 widescreen format".

**Output Format (JSON):**
{{
    "title": "Finalized slide title",
    "content_bullets": ["Bullet 1", "Bullet 2"],
    "key_insight": "The one-line takeaway",
    "speaker_notes": "Detailed narrative for presenter",
    "infographic_prompt": "Detailed prompt to generate infographic image..."
}}
"""
