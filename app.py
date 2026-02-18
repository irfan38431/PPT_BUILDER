"""
app.py — Streamlit interface for the Finance Research PPT Builder.
Provides a human-in-the-loop approval workflow for presentation generation.
"""

from __future__ import annotations

import json
import os
import random
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import streamlit as st
import streamlit.components.v1 as components

from agents.slide_content_agent import SlideContent
from config import get_settings, OUTPUT_DIR
from models import PipelineState, StorylineOutline
from orchestrator import PipelineOrchestrator
from generators.slide_previewer import SlidePreviewRenderer
from generators.themes import (
    PresentationTheme,
    BUILTIN_THEMES,
    THEME_CORPORATE_BLUE,
    pick_two_themes,
)


# ── Finance & Mutual Fund Facts (India) ────────────────────
FINANCE_FACTS = [
    "India's mutual fund industry AUM crossed ₹66 lakh crore in 2025, more than doubling in just 5 years.",
    "SIP contributions in India hit a record ₹26,000+ crore per month in late 2025 — that's nearly ₹870 crore every single day.",
    "The first mutual fund in India was Unit Trust of India (UTI), established in 1963 by an Act of Parliament.",
    "India has over 19 crore (190 million) mutual fund SIP accounts as of 2025 — roughly 1 in 7 Indians.",
    "SEBI mandates that every mutual fund scheme must disclose its portfolio holdings every month.",
    "The Sensex was at 100 in 1979. It crossed 80,000 in 2024 — an 800x return over 45 years.",
    "Nifty 50 has delivered ~12-13% CAGR since inception in 1996, beating most fixed-income instruments.",
    "India is the fastest-growing major mutual fund market in the world by new investor additions.",
    "ELSS (Equity Linked Savings Scheme) is the only mutual fund category that offers tax deduction under Section 80C.",
    "Liquid funds in India process redemptions within 24 hours — some even offer instant redemption up to ₹50,000.",
    "India's UPI processed over 14 billion transactions in a single month in 2024 — more than all card payments combined.",
    "The Bombay Stock Exchange (BSE), founded in 1875, is the oldest stock exchange in Asia.",
    "Gold ETFs in India saw massive inflows in 2024-25 as gold prices crossed ₹78,000 per 10 grams.",
    "India's National Pension System (NPS) has over 7.5 crore subscribers and manages ₹13 lakh crore+.",
    "Passive funds (index funds & ETFs) in India grew from ₹2 lakh crore to over ₹10 lakh crore in just 3 years.",
    "Smallcap mutual funds in India delivered over 25% CAGR in the 5-year period ending 2025.",
    "RBI's repo rate decisions directly impact debt mutual fund returns — a 25bps cut can rally bond prices significantly.",
    "India's GST collection crossed ₹2 lakh crore in a single month for the first time in April 2025.",
    "Direct plans of mutual funds save 0.5-1% annually in expense ratio compared to regular plans.",
    "Thematic & sectoral funds were the most launched new fund category in India during 2024-25.",
    "India's forex reserves crossed $700 billion in 2025, providing a strong buffer against currency volatility.",
    "The average holding period of equity mutual fund investors in India is still under 2 years — patience pays more.",
    "Multi-asset allocation funds must invest in at least 3 asset classes with minimum 10% in each, per SEBI rules.",
    "India's insurance penetration is just ~4% of GDP — significantly lower than the global average of 7%.",
    "Flexi-cap funds are the most popular equity mutual fund category by AUM in India.",
    "Zerodha, India's largest stockbroker, has over 1.5 crore active clients — all acquired without a single TV ad.",
    "India's corporate bond market is growing rapidly but still represents only ~18% of GDP vs 120%+ in the US.",
    "The new income tax regime in India makes ELSS less attractive for some, but long-term equity remains king.",
    "Mutual fund distributors in India must pass the NISM Series V-A certification exam to sell funds.",
    "India's fintech sector is valued at over $100 billion, driven largely by UPI and digital lending innovations.",
]


def get_random_fact() -> str:
    """Return a random finance/MF fact for loading screens."""
    return random.choice(FINANCE_FACTS)


# ── Visual Type Options for User Control ────────────────
VISUAL_TYPE_OPTIONS = {
    "Bar Chart (Full Slide)": ("chart", "bar_chart"),
    "Line Chart (Full Slide)": ("chart", "line_chart"),
    "Pie Chart (Full Slide)": ("chart", "pie_chart"),
    "Grouped Bar Comparison": ("chart", "grouped_bar_chart"),
    "Dual Bar Comparison": ("chart", "dual_bar_comparison"),
    "Multi Chart Slide": ("chart", "multi_chart"),
    "Transition Charts (Before/After)": ("chart", "transition_chart"),
    "Text Heavy (Infographics)": ("bullet", "text_heavy_infographic"),
    "Visual + Text (Split Layout)": ("split", "split_visual_text"),
    "Information Dashboard": ("exec_summary", "info_dashboard"),
    "Table (Full Slide)": ("table", "table"),
    "Bullet Points": ("bullet", "none"),
}


def _get_current_visual_option(slide) -> str:
    """Reverse-map a slide's (layout_type, visual_type) to a VISUAL_TYPE_OPTIONS key."""
    current = (slide.layout_type, slide.visual_type)
    for label, val in VISUAL_TYPE_OPTIONS.items():
        if val == current:
            return label
    return "Bullet Points"


# ── Page Config ─────────────────────────────────────────────
st.set_page_config(
    page_title="Finance PPT Builder",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ──────────────────────────────────────────────
st.markdown(
    """
<style>
    /* ── Global ── */
    .stApp {
        background: linear-gradient(135deg, #0F1B2D 0%, #1B2A4A 40%, #243B5E 70%, #1B2A4A 100%);
        color: #E8ECF1;
    }
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0D1728 0%, #162236 100%);
        border-right: 1px solid rgba(74,144,217,0.15);
    }
    section[data-testid="stSidebar"] * {
        color: #C8D6E5 !important;
    }
    section[data-testid="stSidebar"] .stSlider label,
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stTextArea label {
        color: #8FABC7 !important;
        font-weight: 600;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    section[data-testid="stSidebar"] hr {
        border-color: rgba(74,144,217,0.2);
    }
    /* ── Typography ── */
    .main-header {
        font-size: 2.4rem;
        font-weight: 800;
        background: linear-gradient(135deg, #4A90D9 0%, #67B8F0 50%, #A8D8FF 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.25rem;
        letter-spacing: -0.5px;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #7B9DBF;
        margin-bottom: 2rem;
        font-weight: 400;
    }
    .phase-title {
        font-size: 1.5rem;
        font-weight: 700;
        color: #67B8F0;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid rgba(74,144,217,0.3);
    }

    /* ── Progress Steps ── */
    .progress-bar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin: 1.5rem 0 2rem 0;
        padding: 0.75rem 1rem;
        background: rgba(15,27,45,0.5);
        border-radius: 12px;
        border: 1px solid rgba(74,144,217,0.15);
    }
    .progress-step {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
        flex: 1;
    }
    .step-dot {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.75rem;
        font-weight: 700;
        transition: all 0.3s;
    }
    .step-dot.done { background: #27AE60; color: white; }
    .step-dot.active { background: linear-gradient(135deg, #4A90D9, #67B8F0); color: white; box-shadow: 0 0 12px rgba(74,144,217,0.5); }
    .step-dot.pending { background: rgba(74,144,217,0.15); color: #5A7A9A; }
    .step-label {
        font-size: 0.65rem;
        color: #5A7A9A;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-weight: 600;
    }
    .step-label.active { color: #67B8F0; }
    .step-label.done { color: #27AE60; }

    /* ── Cards ── */
    .glass-card {
        padding: 1.5rem;
        border-radius: 12px;
        background: rgba(22,34,54,0.6);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(74,144,217,0.15);
        margin-bottom: 1rem;
        transition: border-color 0.3s, box-shadow 0.3s;
    }
    .glass-card:hover {
        border-color: rgba(74,144,217,0.35);
        box-shadow: 0 4px 20px rgba(74,144,217,0.1);
    }
    .feature-card {
        padding: 1.75rem 1.5rem;
        border-radius: 12px;
        background: linear-gradient(135deg, rgba(22,34,54,0.7) 0%, rgba(30,48,72,0.5) 100%);
        border: 1px solid rgba(74,144,217,0.12);
        text-align: center;
        height: 100%;
    }
    .feature-card .feature-icon {
        font-size: 2rem;
        margin-bottom: 0.75rem;
        display: block;
    }
    .feature-card h4 {
        color: #A8D8FF;
        font-size: 1rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    .feature-card p {
        color: #7B9DBF;
        font-size: 0.85rem;
        line-height: 1.5;
        margin: 0;
    }
    .outline-card {
        padding: 1.75rem;
        border-radius: 12px;
        background: rgba(22,34,54,0.6);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(74,144,217,0.15);
        margin-bottom: 1rem;
        transition: all 0.3s;
    }
    .outline-card:hover {
        border-color: rgba(74,144,217,0.4);
        box-shadow: 0 4px 24px rgba(74,144,217,0.12);
    }
    .outline-card .card-header {
        font-size: 1.1rem;
        font-weight: 700;
        color: #A8D8FF;
        margin-bottom: 0.25rem;
    }
    .outline-card .card-meta {
        font-size: 0.8rem;
        color: #5A7A9A;
        margin-bottom: 1rem;
    }
    .slide-row {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 6px 10px;
        border-radius: 6px;
        margin-bottom: 4px;
        font-size: 0.88rem;
        color: #C8D6E5;
        transition: background 0.2s;
    }
    .slide-row:hover {
        background: rgba(74,144,217,0.08);
    }
    .slide-row .slide-num {
        color: #4A90D9;
        font-weight: 700;
        min-width: 20px;
    }
    .slide-row .slide-icon {
        font-size: 0.9rem;
    }

    /* ── Approval Card ── */
    .approval-card {
        padding: 2rem;
        border-radius: 14px;
        background: linear-gradient(135deg, rgba(22,34,54,0.7) 0%, rgba(18,30,48,0.8) 100%);
        border: 1px solid rgba(74,144,217,0.2);
        margin-bottom: 1.5rem;
    }
    .approval-card .ap-header {
        font-size: 1.2rem;
        font-weight: 700;
        color: #A8D8FF;
        margin-bottom: 0.25rem;
    }
    .approval-card .ap-theme {
        color: #7B9DBF;
        font-size: 0.9rem;
        margin-bottom: 1.25rem;
        font-style: italic;
    }
    .slide-detail-card {
        padding: 1rem 1.25rem;
        border-radius: 10px;
        background: rgba(15,27,45,0.5);
        border: 1px solid rgba(74,144,217,0.1);
        margin-bottom: 0.75rem;
    }
    .slide-detail-card .sd-title {
        font-weight: 700;
        color: #C8D6E5;
        font-size: 0.95rem;
    }
    .slide-detail-card .sd-meta {
        font-size: 0.78rem;
        color: #5A7A9A;
    }
    .slide-detail-card .sd-insight {
        font-size: 0.85rem;
        color: #7B9DBF;
        margin-top: 0.4rem;
        padding-left: 0.75rem;
        border-left: 2px solid rgba(74,144,217,0.3);
    }

    /* ── Stat Badges ── */
    .stat-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        background: rgba(74,144,217,0.12);
        color: #67B8F0;
        border: 1px solid rgba(74,144,217,0.2);
    }

    /* ── Metric Cards ── */
    .metric-card {
        padding: 1.25rem;
        border-radius: 12px;
        background: rgba(22,34,54,0.6);
        border: 1px solid rgba(74,144,217,0.15);
        text-align: center;
    }
    .metric-card .metric-value {
        font-size: 1.8rem;
        font-weight: 800;
        background: linear-gradient(135deg, #4A90D9, #67B8F0);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .metric-card .metric-label {
        font-size: 0.75rem;
        color: #5A7A9A;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-weight: 600;
        margin-top: 2px;
    }

    /* ── Button overrides ── */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #4A90D9 0%, #3672B5 100%);
        border: none;
        border-radius: 8px;
        font-weight: 600;
        letter-spacing: 0.3px;
        transition: all 0.3s;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #5AA0E9 0%, #4682C5 100%);
        box-shadow: 0 4px 16px rgba(74,144,217,0.3);
    }
    .stButton > button[kind="secondary"] {
        background: rgba(74,144,217,0.1);
        border: 1px solid rgba(74,144,217,0.3);
        color: #67B8F0;
        border-radius: 8px;
        font-weight: 600;
    }
    .stButton > button[kind="secondary"]:hover {
        background: rgba(74,144,217,0.2);
        border-color: rgba(74,144,217,0.5);
    }

    /* ── Expander ── */
    .streamlit-expanderHeader {
        background: rgba(22,34,54,0.4);
        border-radius: 8px;
        color: #C8D6E5 !important;
        font-weight: 600;
    }

    /* ── Streamlit Info/Success/Warning/Error overrides ── */
    .stAlert {
        border-radius: 10px;
    }

    /* ── Animated Loading ── */
    @keyframes pulse-glow {
        0%, 100% { opacity: 0.4; transform: scale(0.95); }
        50% { opacity: 1; transform: scale(1); }
    }
    @keyframes shimmer-slide {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }
    @keyframes fade-in-up {
        0% { opacity: 0; transform: translateY(12px); }
        100% { opacity: 1; transform: translateY(0); }
    }
    @keyframes spin-ring {
        0% {transform: rotate(0deg);}
        100% {transform: rotate(360deg);}
    }

    .loading-container {
        text-align: center;
        padding: 2.5rem 2rem;
        animation: fade-in-up 0.5s ease-out;
    }
    .loading-spinner {
        width: 48px; height: 48px;
        border: 3px solid rgba(74,144,217,0.15);
        border-top-color: #4A90D9;
        border-radius: 50%;
        animation: spin-ring 0.9s linear infinite;
        margin: 0 auto 1.5rem auto;
    }
    .loading-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: #A8D8FF;
        margin-bottom: 0.4rem;
    }
    .loading-subtitle {
        font-size: 0.88rem;
        color: #5A7A9A;
        margin-bottom: 1.5rem;
    }
    .loading-steps {
        display: flex;
        flex-direction: column;
        gap: 12px;
        max-width: 420px;
        margin: 0 auto;
        text-align: left;
    }
    .loading-step {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 16px;
        border-radius: 10px;
        background: rgba(15,27,45,0.5);
        border: 1px solid rgba(74,144,217,0.1);
        font-size: 0.88rem;
        color: #5A7A9A;
        transition: all 0.3s;
    }
    .loading-step.active {
        background: rgba(74,144,217,0.1);
        border-color: rgba(74,144,217,0.3);
        color: #A8D8FF;
    }
    .loading-step.done {
        color: #27AE60;
        border-color: rgba(39,174,96,0.2);
    }
    .loading-step-icon {
        font-size: 1rem;
        min-width: 24px;
        text-align: center;
    }
    .loading-step.active .loading-step-icon {
        animation: pulse-glow 1.5s ease-in-out infinite;
    }
    .shimmer-bar {
        height: 4px;
        border-radius: 4px;
        background: linear-gradient(90deg,
            rgba(74,144,217,0.1) 0%,
            rgba(74,144,217,0.4) 50%,
            rgba(74,144,217,0.1) 100%);
        background-size: 200% 100%;
        animation: shimmer-slide 1.8s ease-in-out infinite;
        margin: 1rem auto;
        max-width: 300px;
    }
    .fact-box {
        margin-top: 1.5rem;
        padding: 12px 20px;
        border-radius: 10px;
        background: rgba(74,144,217,0.08);
        border: 1px solid rgba(74,144,217,0.18);
        font-size: 0.82rem;
        color: #A8D8FF;
        max-width: 480px;
        margin-left: auto;
        margin-right: auto;
    }
    .fact-box strong { color: #4A90D9; }
    /* ── Demo PPT Cards ── */
    .demo-section-title {
        font-size: 1.4rem;
        font-weight: 800;
        background: linear-gradient(135deg, #4A90D9 0%, #A8D8FF 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.25rem;
    }
    .demo-section-subtitle {
        font-size: 0.9rem;
        color: #5A7A9A;
        margin-bottom: 1.5rem;
    }
    .demo-card {
        padding: 1.4rem 1.3rem;
        border-radius: 14px;
        background: rgba(22,34,54,0.65);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(74,144,217,0.12);
        transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
        cursor: default;
        height: 100%;
        position: relative;
        overflow: hidden;
    }
    .demo-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
        border-radius: 14px 14px 0 0;
        transition: height 0.3s;
    }
    .demo-card:hover {
        border-color: rgba(74,144,217,0.35);
        box-shadow: 0 8px 32px rgba(74,144,217,0.12);
        transform: translateY(-3px);
    }
    .demo-card:hover::before {
        height: 4px;
    }
    .demo-card-icon {
        font-size: 1.6rem;
        margin-bottom: 0.5rem;
        display: block;
    }
    .demo-card-title {
        font-size: 0.95rem;
        font-weight: 700;
        color: #C8D6E5;
        margin-bottom: 0.35rem;
        line-height: 1.3;
    }
    .demo-card-desc {
        font-size: 0.78rem;
        color: #7B9DBF;
        line-height: 1.5;
        margin-bottom: 0.75rem;
    }
    .demo-card-meta {
        display: flex;
        gap: 6px;
        flex-wrap: wrap;
        margin-bottom: 0.6rem;
    }
    .demo-badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 3px 10px;
        border-radius: 14px;
        font-size: 0.68rem;
        font-weight: 600;
        background: rgba(74,144,217,0.1);
        color: #67B8F0;
        border: 1px solid rgba(74,144,217,0.15);
    }
    .demo-prompt-toggle {
        font-size: 0.72rem;
        color: #4A90D9;
        cursor: pointer;
        text-decoration: underline;
        text-underline-offset: 3px;
        margin-top: 0.3rem;
        display: inline-block;
    }
    .demo-updated {
        font-size: 0.68rem;
        color: #3D6A8F;
        margin-top: 0.5rem;
        display: flex;
        align-items: center;
        gap: 4px;
    }
    .demo-refresh-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        background: rgba(39,174,96,0.1);
        color: #27AE60;
        border: 1px solid rgba(39,174,96,0.2);
    }

    /* ── Mini Game Container ── */
    .minigame-wrapper {
        border-radius: 14px;
        background: rgba(15,27,45,0.6);
        border: 1px solid rgba(74,144,217,0.15);
        padding: 1rem;
        height: 100%;
    }
    .minigame-title {
        font-size: 0.85rem;
        font-weight: 700;
        color: #67B8F0;
        margin-bottom: 0.5rem;
        text-align: center;
    }
</style>
""",
    unsafe_allow_html=True,
)


# ── Progress Bar Helper ────────────────────────────────────
PIPELINE_STEPS = [
    ("idle", "Setup"),
    ("researching", "Research"),
    ("framework_selection", "Frameworks"),
    ("storyline_approval", "Storyline"),
    ("theme_selection", "Theme"),
    ("generating", "Generate"),
    ("review", "Review"),
    ("finalizing", "Build"),
    ("done", "Done"),
]


def render_progress_bar(current_phase: str) -> None:
    """Render a visual pipeline progress bar."""
    step_order = [s[0] for s in PIPELINE_STEPS]
    current_idx = step_order.index(current_phase) if current_phase in step_order else 0

    html_parts = []
    for i, (phase_key, label) in enumerate(PIPELINE_STEPS):
        if i < current_idx:
            dot_class = "done"
            label_class = "done"
            content = "&#10003;"
        elif i == current_idx:
            dot_class = "active"
            label_class = "active"
            content = str(i + 1)
        else:
            dot_class = "pending"
            label_class = ""
            content = str(i + 1)

        html_parts.append(
            f'<div class="progress-step">'
            f'<div class="step-dot {dot_class}">{content}</div>'
            f'<span class="step-label {label_class}">{label}</span>'
            f"</div>"
        )

    st.markdown(
        f'<div class="progress-bar">{"".join(html_parts)}</div>',
        unsafe_allow_html=True,
    )


# ── Session State Initialization ────────────────────────────
def init_session_state() -> None:
    """Initialize all session state variables."""
    defaults = {
        "orchestrator": None,
        "pipeline_phase": "idle",
        "research_findings": None,
        "framework_choices": None,
        "outline_a": None,
        "outline_b": None,
        "selected_outline": None,
        "slide_contents": None,
        "validation_results": None,
        "output_path": None,
        "output_gcs_uri": None,
        "error_message": None,
        "status_log": [],
        "slide_previews": None,
        "review_slide_idx": 0,
        "slide_approvals": {},
        "selected_theme": None,
        "theme_previews": None,
        "infographic_proposals": [],
        "render_decisions": [],
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


def get_orchestrator() -> PipelineOrchestrator:
    """Get or create the pipeline orchestrator."""
    if st.session_state.orchestrator is None:

        def on_status(status: str, step: str) -> None:
            st.session_state.status_log.append(f"[{status}] {step}")

        st.session_state.orchestrator = PipelineOrchestrator(
            on_status_change=on_status,
        )
    return st.session_state.orchestrator


# ── Sidebar ─────────────────────────────────────────────────
def render_sidebar() -> Dict[str, Any]:
    """Render the configuration sidebar."""
    with st.sidebar:
        st.markdown(
            '<p style="font-size:1.3rem;font-weight:800;'
            "background:linear-gradient(135deg,#4A90D9,#67B8F0);"
            "-webkit-background-clip:text;-webkit-text-fill-color:transparent;"
            'background-clip:text;margin-bottom:0.25rem;">PPT Builder</p>',
            unsafe_allow_html=True,
        )
        st.caption("AI-powered presentation engine")
        st.markdown("---")

        topic = st.text_area(
            "Presentation Topic",
            placeholder="e.g., 'The Rise of AI in Financial Services: Market Impact and Investment Opportunities'",
            height=100,
        )

        subtopics_input = st.text_area(
            "Key Subtopics (Optional)",
            placeholder="List specific areas to prioritize (one per line)...",
            height=80,
            help="These topics will be given priority in the research phase.",
        )

        audience = st.selectbox(
            "Target Audience",
            [
                "Business Executives",
                "Investors",
                "Technical Team",
                "Board of Directors",
                "General Audience",
            ],
            index=0,
        )

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            num_subtopics = st.slider(
                "Research Depth",
                min_value=3,
                max_value=10,
                value=6,
                help="More subtopics = deeper research but longer generation time",
            )
        with col_s2:
            target_slides = st.slider(
                "Target Slides",
                min_value=6,
                max_value=30,
                value=12,
                help="Target number of slides in the presentation",
            )

        st.markdown("---")

        enhanced_visuals = st.toggle(
            "Enhanced Visuals",
            value=False,
            help="Requires Nano Banana Pro API key in .env",
        )

        st.markdown("---")

        # Pipeline status
        phase = st.session_state.pipeline_phase
        phase_labels = {
            "idle": ("Setup", "#5A7A9A"),
            "researching": ("Researching", "#4A90D9"),
            "framework_selection": ("Planning", "#8E44AD"),
            "storyline_approval": ("Storyline Review", "#E67E22"),
            "generating": ("Generating", "#E67E22"),
            "review": ("Review", "#E74C3C"),
            "finalizing": ("Building", "#27AE60"),
            "done": ("Complete", "#27AE60"),
            "error": ("Error", "#E74C3C"),
        }
        label, color = phase_labels.get(phase, ("Unknown", "#5A7A9A"))
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;">'
            f'<span style="width:8px;height:8px;border-radius:50%;background:{color};'
            f'box-shadow:0 0 6px {color};display:inline-block;"></span>'
            f'<span style="font-weight:600;color:{color};font-size:0.85rem;">{label}</span>'
            f"</div>",
            unsafe_allow_html=True,
        )

        if st.session_state.status_log:
            with st.expander("Activity Log", expanded=False):
                for entry in st.session_state.status_log[-10:]:
                    st.text(entry)

        return {
            "topic": topic,
            "subtopics_input": subtopics_input,
            "audience": audience.lower(),
            "num_subtopics": num_subtopics,
            "target_slides": target_slides,
            "enhanced_visuals": enhanced_visuals,
        }


# ── Main Phases ─────────────────────────────────────────────


def _load_demo_config() -> list:
    """Load demo PPT configurations from demo_config.json."""
    demo_config_path = (
        Path(__file__).resolve().parent / "demo_ppts" / "demo_config.json"
    )
    if demo_config_path.exists():
        with open(demo_config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("demo_ppts", [])
    return []


def _load_demo_status() -> dict:
    """Load demo PPT generation status."""
    status_path = Path(__file__).resolve().parent / "demo_ppts" / "demo_status.json"
    if status_path.exists():
        with open(status_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"demos": {}, "last_full_run": None}


def _get_snake_game_html() -> str:
    """Return HTML/JS/CSS for an embedded Snake mini-game."""
    return """
    <div style="text-align:center;font-family:'Segoe UI',sans-serif;">
      <div style="font-size:13px;font-weight:700;color:#67B8F0;margin-bottom:6px;">🐍 Snake Game</div>
      <div style="font-size:11px;color:#5A7A9A;margin-bottom:8px;">Use arrow keys or swipe to play!</div>
      <canvas id="snakeCanvas" width="280" height="280"
        style="border:2px solid rgba(74,144,217,0.3);border-radius:10px;background:#0D1728;display:block;margin:0 auto;"></canvas>
      <div id="scoreDisplay" style="font-size:12px;color:#A8D8FF;margin-top:8px;font-weight:600;">Score: 0</div>
      <div style="margin-top:6px;">
        <button onclick="resetGame()" style="
          padding:5px 16px;border-radius:8px;border:1px solid rgba(74,144,217,0.3);
          background:rgba(74,144,217,0.15);color:#67B8F0;font-size:11px;font-weight:600;
          cursor:pointer;transition:all 0.2s;
        ">🔄 Restart</button>
      </div>
      <script>
        const canvas = document.getElementById('snakeCanvas');
        const ctx = canvas.getContext('2d');
        const gridSize = 14;
        const tileCount = canvas.width / gridSize;
        let snake = [{x:10,y:10}];
        let food = {x:15,y:15};
        let dx = 0, dy = 0;
        let score = 0;
        let gameOver = false;
        let speed = 120;
        let gameInterval;

        function placeFood() {
          food.x = Math.floor(Math.random() * tileCount);
          food.y = Math.floor(Math.random() * tileCount);
          for (let s of snake) {
            if (s.x === food.x && s.y === food.y) { placeFood(); return; }
          }
        }

        function drawGame() {
          if (gameOver) return;
          // Move
          const head = {x: snake[0].x + dx, y: snake[0].y + dy};
          // Wall wrap
          if (head.x < 0) head.x = tileCount - 1;
          if (head.x >= tileCount) head.x = 0;
          if (head.y < 0) head.y = tileCount - 1;
          if (head.y >= tileCount) head.y = 0;
          // Self collision - only check if snake is moving
          if (dx !== 0 || dy !== 0) {
            for (let s of snake) {
              if (s.x === head.x && s.y === head.y) { gameOver = true; break; }
            }
          }
          if (gameOver) {
            ctx.fillStyle = 'rgba(13,23,40,0.85)';
            ctx.fillRect(0,0,canvas.width,canvas.height);
            ctx.fillStyle = '#E74C3C';
            ctx.font = 'bold 18px Segoe UI';
            ctx.textAlign = 'center';
            ctx.fillText('Game Over!', canvas.width/2, canvas.height/2 - 5);
            ctx.fillStyle = '#A8D8FF';
            ctx.font = '13px Segoe UI';
            ctx.fillText('Click Restart to play again', canvas.width/2, canvas.height/2 + 20);
            return;
          }
          snake.unshift(head);
          if (head.x === food.x && head.y === food.y) {
            score += 10;
            document.getElementById('scoreDisplay').textContent = 'Score: ' + score;
            placeFood();
            if (speed > 60) speed -= 2;
          } else {
            snake.pop();
          }
          // Draw
          ctx.fillStyle = '#0D1728';
          ctx.fillRect(0,0,canvas.width,canvas.height);
          // Grid lines (subtle)
          ctx.strokeStyle = 'rgba(74,144,217,0.05)';
          for (let i = 0; i < tileCount; i++) {
            ctx.beginPath();
            ctx.moveTo(i*gridSize,0); ctx.lineTo(i*gridSize,canvas.height);
            ctx.moveTo(0,i*gridSize); ctx.lineTo(canvas.width,i*gridSize);
            ctx.stroke();
          }
          // Food
          ctx.fillStyle = '#E74C3C';
          ctx.shadowBlur = 8; ctx.shadowColor = '#E74C3C';
          ctx.beginPath();
          ctx.arc(food.x*gridSize+gridSize/2, food.y*gridSize+gridSize/2, gridSize/2-2, 0, Math.PI*2);
          ctx.fill();
          ctx.shadowBlur = 0;
          // Snake
          for (let i = 0; i < snake.length; i++) {
            const ratio = 1 - (i / snake.length) * 0.6;
            const r = Math.round(74 * ratio); const g = Math.round(144 + (111-144)*ratio); const b = Math.round(217 + (96-217)*ratio);
            ctx.fillStyle = i === 0 ? '#67B8F0' : `rgba(${74+i*3},${144+i*2},${217-i*4},${ratio})`;
            ctx.shadowBlur = i === 0 ? 6 : 0;
            ctx.shadowColor = '#67B8F0';
            const pad = i === 0 ? 1 : 2;
            ctx.beginPath();
            ctx.roundRect(snake[i].x*gridSize+pad, snake[i].y*gridSize+pad, gridSize-pad*2, gridSize-pad*2, 3);
            ctx.fill();
            ctx.shadowBlur = 0;
          }
        }

        function resetGame() {
          snake = [{x:10,y:10}];
          dx = 0; dy = 0;
          score = 0; gameOver = false; speed = 120;
          document.getElementById('scoreDisplay').textContent = 'Score: 0';
          placeFood();
          if (gameInterval) clearInterval(gameInterval);
          gameInterval = setInterval(drawGame, speed);
        }

        document.addEventListener('keydown', (e) => {
          switch(e.key) {
            case 'ArrowUp':    if (dy !== 1) {dx=0;dy=-1;} break;
            case 'ArrowDown':  if (dy !== -1){dx=0;dy=1;}  break;
            case 'ArrowLeft':  if (dx !== 1) {dx=-1;dy=0;} break;
            case 'ArrowRight': if (dx !== -1){dx=1;dy=0;}  break;
          }
          e.preventDefault();
        });

        // Touch support
        let touchStartX, touchStartY;
        canvas.addEventListener('touchstart', (e) => {
          touchStartX = e.touches[0].clientX;
          touchStartY = e.touches[0].clientY;
        });
        canvas.addEventListener('touchend', (e) => {
          const diffX = e.changedTouches[0].clientX - touchStartX;
          const diffY = e.changedTouches[0].clientY - touchStartY;
          if (Math.abs(diffX) > Math.abs(diffY)) {
            if (diffX > 0 && dx !== -1) {dx=1;dy=0;}
            else if (diffX < 0 && dx !== 1) {dx=-1;dy=0;}
          } else {
            if (diffY > 0 && dy !== -1) {dx=0;dy=1;}
            else if (diffY < 0 && dy !== 1) {dx=0;dy=-1;}
          }
        });

        placeFood();
        gameInterval = setInterval(drawGame, speed);
      </script>
    </div>
    """


def _render_demo_ppts_section() -> None:
    """Render the Demo PPTs section on the idle page."""
    demo_configs = _load_demo_config()
    demo_status = _load_demo_status()

    if not demo_configs:
        return

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<p class="demo-section-title">📂 Demo Presentations</p>',
        unsafe_allow_html=True,
    )

    # Status info
    last_run = demo_status.get("last_full_run")
    if last_run:
        try:
            last_dt = datetime.fromisoformat(last_run)
            age_str = last_dt.strftime("%b %d, %Y at %I:%M %p")
        except (ValueError, TypeError):
            age_str = "Unknown"
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:1.25rem;">'
            f'<span class="demo-section-subtitle" style="margin-bottom:0;">'
            f"Explore AI-generated presentations — auto-refreshed weekly with the latest data</span>"
            f'<span class="demo-refresh-badge">🔄 Updated: {age_str}</span>'
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<p class="demo-section-subtitle">'
            "Explore what this engine can create — run <code>python demo_ppts/generate_demos.py</code> to generate demos"
            "</p>",
            unsafe_allow_html=True,
        )

    # Render demo cards — 3 + 2 layout
    demos_status = demo_status.get("demos", {})

    row1_configs = demo_configs[:3]
    row2_configs = demo_configs[3:]

    for row_configs in [row1_configs, row2_configs]:
        cols = st.columns(len(row_configs))
        for col, dcfg in zip(cols, row_configs):
            with col:
                d_id = dcfg["id"]
                d_status = demos_status.get(d_id, {})
                accent = dcfg.get("color_accent", "#4A90D9")
                icon = dcfg.get("icon", "📄")
                title = dcfg["title"]
                desc = dcfg.get("description", "")[:140]
                audience = dcfg.get("audience", "business executives").title()
                slides_n = dcfg.get("target_slides", 12)
                subtopics = dcfg.get("subtopics", [])

                gen_at = d_status.get("generated_at", "")
                file_size = d_status.get("file_size_kb", 0)
                status_ok = d_status.get("status") == "success"
                file_path = d_status.get("file_path", "")

                # Timestamp formatting
                time_info = ""
                if gen_at:
                    try:
                        dt = datetime.fromisoformat(gen_at)
                        time_info = dt.strftime("%b %d, %Y")
                    except (ValueError, TypeError):
                        time_info = ""

                # Subtopics preview
                subtopics_html = ""
                if subtopics:
                    items = "".join(
                        f'<div style="font-size:0.7rem;color:#5A7A9A;padding:2px 0;">• {st_name}</div>'
                        for st_name in subtopics[:4]
                    )
                    if len(subtopics) > 4:
                        items += f'<div style="font-size:0.68rem;color:#3D6A8F;">+{len(subtopics) - 4} more...</div>'
                    subtopics_html = f'<div style="margin-top:0.4rem;">{items}</div>'

                updated_html = ""
                if time_info:
                    updated_html = (
                        f'<div class="demo-updated">'
                        f"<span>🕐</span> Generated: {time_info}"
                        f"{' · ' + str(file_size) + ' KB' if file_size else ''}"
                        f"</div>"
                    )

                st.markdown(
                    f'<div class="demo-card" style="--accent:{accent};">'
                    f'<div style="position:absolute;top:0;left:0;right:0;height:3px;'
                    f'background:{accent};border-radius:14px 14px 0 0;"></div>'
                    f'<span class="demo-card-icon">{icon}</span>'
                    f'<div class="demo-card-title">{title}</div>'
                    f'<div class="demo-card-desc">{desc}</div>'
                    f'<div class="demo-card-meta">'
                    f'<span class="demo-badge">📄 {slides_n} slides</span>'
                    f'<span class="demo-badge">👥 {audience}</span>'
                    f"{'<span class=demo-badge style=color:#27AE60;border-color:rgba(39,174,96,0.2)>✅ Ready</span>' if status_ok else '<span class=demo-badge style=color:#F39C12;border-color:rgba(243,156,18,0.2)>⏳ Pending</span>'}"
                    f"</div>"
                    f"{updated_html}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

                # Show prompt details in an expander
                with st.expander(f"📋 View Prompt & Config", expanded=False):
                    st.markdown(
                        f"**Topic:**\n> {dcfg['topic']}\n\n"
                        f"**Audience:** {audience}\n\n"
                        f"**Research Depth:** {dcfg.get('num_subtopics', 6)} subtopics\n\n"
                        f"**Target Slides:** {slides_n}"
                    )
                    if subtopics:
                        st.markdown("**Key Subtopics:**")
                        for st_name in subtopics:
                            st.markdown(f"- {st_name}")

                # Download button if file exists
                if status_ok and file_path:
                    fp = Path(file_path)
                    if fp.exists():
                        with open(fp, "rb") as f:
                            st.download_button(
                                "⬇️ Download PPTX",
                                data=f.read(),
                                file_name=fp.name,
                                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                key=f"demo_dl_{d_id}",
                                use_container_width=True,
                            )


def phase_idle(config: Dict[str, Any]) -> None:
    """Idle phase: waiting for user to start."""
    st.markdown(
        '<p class="main-header">Finance Research PPT Builder</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="sub-header">AI-powered presentation generator with grounded financial research</p>',
        unsafe_allow_html=True,
    )

    render_progress_bar("idle")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            '<div class="feature-card">'
            '<span class="feature-icon">🔍</span>'
            "<h4>Deep Research</h4>"
            "<p>Grounded search with source verification and confidence scoring</p>"
            "</div>",
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            '<div class="feature-card">'
            '<span class="feature-icon">📐</span>'
            "<h4>Smart Planning</h4>"
            "<p>Framework-based narrative with storyline approval workflow</p>"
            "</div>",
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            '<div class="feature-card">'
            '<span class="feature-icon">📊</span>'
            "<h4>Pro Generation</h4>"
            "<p>Professional charts, tables, and layouts — ready to present</p>"
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    if not config["topic"]:
        st.markdown(
            '<div class="glass-card" style="text-align:center;padding:2rem;">'
            '<p style="color:#7B9DBF;font-size:1rem;margin:0;">'
            "Enter a topic in the sidebar to begin</p></div>",
            unsafe_allow_html=True,
        )
        # Show demo PPTs section even when no topic is entered
        _render_demo_ppts_section()
        return

    st.markdown(
        f'<div class="glass-card">'
        f'<div style="font-size:0.75rem;color:#5A7A9A;text-transform:uppercase;'
        f'letter-spacing:0.5px;font-weight:600;margin-bottom:4px;">Ready to Build</div>'
        f'<div style="color:#C8D6E5;font-size:1rem;">{config["topic"]}</div>'
        f'<div style="margin-top:0.75rem;display:flex;gap:12px;">'
        f'<span class="stat-badge">📚 {config["num_subtopics"]} subtopics</span>'
        f'<span class="stat-badge">📄 {config["target_slides"]} slides</span>'
        f'<span class="stat-badge">👥 {config["audience"].title()}</span>'
        f"</div></div>",
        unsafe_allow_html=True,
    )

    st.markdown("")
    if st.button("🚀  Start Research", type="primary", use_container_width=True):
        st.session_state.pipeline_phase = "researching"
        st.rerun()

    # Show demo PPTs section below the start button
    _render_demo_ppts_section()


def phase_researching(config: Dict[str, Any]) -> None:
    """Research phase: topic decomposition and grounded search."""
    st.markdown('<p class="phase-title">Phase 1 — Research</p>', unsafe_allow_html=True)
    render_progress_bar("researching")

    orchestrator = get_orchestrator()

    # Rich loading UI — split layout: loading info (left) + mini game (right)
    col_loading, col_game = st.columns([3, 2])
    with col_loading:
        st.markdown(
            '<div class="glass-card loading-container">'
            '<div class="loading-spinner"></div>'
            '<div class="loading-title">Researching Your Topic</div>'
            '<div class="loading-subtitle">AI agents are working in parallel to gather data</div>'
            '<div class="shimmer-bar"></div>'
            '<div class="loading-steps">'
            '<div class="loading-step active"><span class="loading-step-icon">🔍</span> Decomposing topic into subtopics</div>'
            '<div class="loading-step active"><span class="loading-step-icon">🌐</span> Running grounded searches (concurrent)</div>'
            '<div class="loading-step"><span class="loading-step-icon">🧠</span> Synthesizing research findings</div>'
            "</div>"
            f'<div class="fact-box"><strong>📈 Did you know?</strong> {get_random_fact()}</div>'
            "</div>",
            unsafe_allow_html=True,
        )
    with col_game:
        st.markdown('<div class="minigame-wrapper">', unsafe_allow_html=True)
        components.html(_get_snake_game_html(), height=440)
        st.markdown("</div>", unsafe_allow_html=True)

    try:
        focus_subtopics = None
        if config.get("subtopics_input"):
            focus_subtopics = [
                s.strip() for s in config["subtopics_input"].split("\n") if s.strip()
            ]

        findings = orchestrator.run_research(
            topic=config["topic"],
            num_subtopics=config["num_subtopics"],
            focus_subtopics=focus_subtopics,
        )
        st.session_state.research_findings = findings
        st.session_state.pipeline_phase = "framework_selection"
        st.rerun()

    except Exception as e:
        st.session_state.error_message = str(e)
        st.session_state.pipeline_phase = "error"
        st.rerun()


def phase_framework_selection(config: Dict[str, Any]) -> None:
    """Framework selection and outline generation."""
    st.markdown(
        '<p class="phase-title">Phase 2 — Choose Your Structure</p>',
        unsafe_allow_html=True,
    )
    render_progress_bar("framework_selection")

    orchestrator = get_orchestrator()

    # Show research findings summary
    findings = st.session_state.research_findings
    if findings:
        with st.expander(
            f"📚 Research Findings ({len(findings)} topics)", expanded=False
        ):
            for f in findings:
                confidence_color = (
                    "#27AE60"
                    if f.confidence > 0.7
                    else "#F39C12"
                    if f.confidence > 0.4
                    else "#E74C3C"
                )
                st.markdown(
                    f'<div class="glass-card" style="padding:0.75rem 1rem;">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                    f'<span style="font-weight:600;color:#C8D6E5;">{f.topic}</span>'
                    f'<span style="color:{confidence_color};font-weight:700;font-size:0.85rem;">'
                    f"{f.confidence:.0%}</span></div>"
                    f'<div style="color:#7B9DBF;font-size:0.85rem;margin-top:4px;">'
                    f"{f.content[:200]}...</div></div>",
                    unsafe_allow_html=True,
                )
                if f.sources:
                    st.caption(f"Sources: {', '.join(f.sources[:3])}")

    # Generate frameworks + outlines
    if st.session_state.outline_a is None:
        col_loading, col_game = st.columns([3, 2])
        with col_loading:
            st.markdown(
                '<div class="glass-card loading-container">'
                '<div class="loading-spinner"></div>'
                '<div class="loading-title">Analyzing Frameworks</div>'
                '<div class="loading-subtitle">Selecting the best narrative structures for your topic</div>'
                '<div class="shimmer-bar"></div>'
                '<div class="loading-steps">'
                '<div class="loading-step active"><span class="loading-step-icon">🎯</span> Evaluating 7 framework options</div>'
                '<div class="loading-step active"><span class="loading-step-icon">📋</span> Generating two competing outlines</div>'
                "</div>"
                f'<div class="fact-box"><strong>📈 Did you know?</strong> {get_random_fact()}</div>'
                "</div>",
                unsafe_allow_html=True,
            )
        with col_game:
            st.markdown('<div class="minigame-wrapper">', unsafe_allow_html=True)
            components.html(_get_snake_game_html(), height=440)
            st.markdown("</div>", unsafe_allow_html=True)

        try:
            choices = orchestrator.run_framework_selection(config["audience"])
            st.session_state.framework_choices = choices

            outline_a, outline_b = orchestrator.run_comparative_outlines(
                target_slides=config["target_slides"],
            )
            st.session_state.outline_a = outline_a
            st.session_state.outline_b = outline_b
            st.rerun()

        except Exception as e:
            st.session_state.error_message = str(e)
            st.session_state.pipeline_phase = "error"
            st.rerun()
    else:
        _render_outline_comparison()


def _render_outline_comparison() -> None:
    """Render two outlines side-by-side for user selection."""
    outline_a = st.session_state.outline_a
    outline_b = st.session_state.outline_b
    choices = st.session_state.framework_choices

    st.markdown(
        '<div style="color:#C8D6E5;font-size:0.95rem;margin-bottom:1rem;">'
        "Two outlines have been generated. Select the one that best fits your needs.</div>",
        unsafe_allow_html=True,
    )

    col_a, col_b = st.columns(2)

    layout_icons = {
        "title": "🎯",
        "bullet": "📝",
        "chart": "📊",
        "table": "📋",
        "split": "↔️",
        "exec_summary": "📈",
        "section_divider": "📌",
        "closing": "🏁",
    }

    for col, outline, choice_idx, key_suffix, label in [
        (col_a, outline_a, 0, "a", "A"),
        (col_b, outline_b, 1, "b", "B"),
    ]:
        with col:
            angle_text = ""
            if choices and len(choices) > choice_idx:
                angle_text = choices[choice_idx].narrative_angle

            slide_rows = ""
            for slide in outline.slides:
                icon = layout_icons.get(slide.layout_type, "📄")
                slide_rows += (
                    f'<div class="slide-row">'
                    f'<span class="slide-num">{slide.id}</span>'
                    f'<span class="slide-icon">{icon}</span>'
                    f"{slide.title}</div>"
                )

            st.markdown(
                f'<div class="outline-card">'
                f'<div class="card-header">Option {label}: {outline.framework_name}</div>'
                f'<div class="card-meta">{angle_text}</div>'
                f'<div style="display:flex;gap:8px;margin-bottom:1rem;">'
                f'<span class="stat-badge">🎨 {outline.theme}</span>'
                f'<span class="stat-badge">📄 {len(outline.slides)} slides</span></div>'
                f"{slide_rows}</div>",
                unsafe_allow_html=True,
            )

            if st.button(
                f"Select Option {label}",
                key=f"select_{key_suffix}",
                type="primary",
                width="stretch",
            ):
                orchestrator = get_orchestrator()
                orchestrator.select_outline(key_suffix)
                st.session_state.selected_outline = outline
                st.session_state.pipeline_phase = "storyline_approval"
                st.rerun()


def phase_storyline_approval(config: Dict[str, Any]) -> None:
    """Storyline approval: user reviews the selected outline before generation."""
    st.markdown(
        '<p class="phase-title">Phase 3 — Storyline Approval</p>',
        unsafe_allow_html=True,
    )
    render_progress_bar("storyline_approval")

    outline = st.session_state.selected_outline
    if not outline:
        st.session_state.pipeline_phase = "framework_selection"
        st.rerun()
        return

    layout_icons = {
        "title": "🎯",
        "bullet": "📝",
        "chart": "📊",
        "table": "📋",
        "split": "↔️",
        "exec_summary": "📈",
        "section_divider": "📌",
        "closing": "🏁",
    }

    # Summary badges
    chart_count = sum(1 for s in outline.slides if s.visual_type != "none")
    text_count = len(outline.slides) - chart_count

    st.markdown(
        f'<div class="approval-card">'
        f'<div class="ap-header">{outline.framework_name}</div>'
        f'<div class="ap-theme">"{outline.theme}"</div>'
        f'<div style="display:flex;gap:10px;flex-wrap:wrap;">'
        f'<span class="stat-badge">📄 {len(outline.slides)} slides</span>'
        f'<span class="stat-badge">📊 {chart_count} visuals</span>'
        f'<span class="stat-badge">📝 {text_count} text</span>'
        f"</div></div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div style="color:#7B9DBF;font-size:0.9rem;margin-bottom:1rem;">'
        "Review the storyline below. Approve to proceed with content generation, "
        "or go back to choose a different structure.</div>",
        unsafe_allow_html=True,
    )

    # Show each slide in detail
    for slide in outline.slides:
        icon = layout_icons.get(slide.layout_type, "📄")
        visual_badge = ""
        if slide.visual_type and slide.visual_type != "none":
            visual_badge = (
                f'<span style="background:rgba(39,174,96,0.15);color:#27AE60;'
                f'padding:2px 8px;border-radius:10px;font-size:0.72rem;font-weight:600;">'
                f"{slide.visual_type.replace('_', ' ').title()}</span>"
            )
        layout_badge = (
            f'<span style="background:rgba(74,144,217,0.15);color:#67B8F0;'
            f'padding:2px 8px;border-radius:10px;font-size:0.72rem;font-weight:600;">'
            f"{slide.layout_type.replace('_', ' ').title()}</span>"
        )
        insight_html = ""
        if slide.key_insight:
            insight_html = f'<div class="sd-insight">{slide.key_insight}</div>'

        st.markdown(
            f'<div class="slide-detail-card">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<div class="sd-title">{icon} Slide {slide.id}: {slide.title}</div>'
            f'<div class="sd-meta" style="display:flex;gap:6px;">{layout_badge}{visual_badge}</div>'
            f"</div>"
            f"{insight_html}</div>",
            unsafe_allow_html=True,
        )

        # Visual type dropdown for non-title and non-closing slides
        if slide.layout_type not in ("title", "closing"):
            current_option = _get_current_visual_option(slide)
            options_list = list(VISUAL_TYPE_OPTIONS.keys())
            current_idx = (
                options_list.index(current_option)
                if current_option in options_list
                else len(options_list) - 1
            )
            selected = st.selectbox(
                "Visual Type",
                options=options_list,
                index=current_idx,
                key=f"visual_type_{slide.id}",
            )
            if selected != current_option:
                new_layout, new_visual = VISUAL_TYPE_OPTIONS[selected]
                slide.layout_type = new_layout
                slide.visual_type = new_visual
                slide.user_locked = True  # Prevent LayoutDecider from overriding

    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        if st.button(
            "✅  Approve & Select Theme", type="primary", width="stretch"
        ):
            st.session_state.pipeline_phase = "theme_selection"
            st.rerun()
    with col2:
        if st.button("↩  Choose Different Structure", width="stretch"):
            st.session_state.selected_outline = None
            st.session_state.pipeline_phase = "framework_selection"
            st.rerun()
    with col3:
        if st.button("🔄  Regenerate", width="stretch"):
            st.session_state.outline_a = None
            st.session_state.outline_b = None
            st.session_state.selected_outline = None
            st.session_state.framework_choices = None
            st.session_state.pipeline_phase = "framework_selection"
            st.rerun()


def phase_generating(config: Dict[str, Any]) -> None:
    """Content generation phase."""
    st.markdown(
        '<p class="phase-title">Phase 4 — Generating Content</p>',
        unsafe_allow_html=True,
    )
    render_progress_bar("generating")

    orchestrator = get_orchestrator()
    outline = st.session_state.selected_outline

    col_loading, col_game = st.columns([3, 2])
    with col_loading:
        st.markdown(
            f'<div class="glass-card loading-container">'
            f'<div class="loading-spinner"></div>'
            f'<div class="loading-title">Building {len(outline.slides)} Slides</div>'
            f'<div class="loading-subtitle">Using <strong>{outline.framework_name}</strong> framework</div>'
            f'<div class="shimmer-bar"></div>'
            f'<div class="loading-steps">'
            f'<div class="loading-step active"><span class="loading-step-icon">🔬</span> Deep research for data-heavy slides (parallel)</div>'
            f'<div class="loading-step active"><span class="loading-step-icon">📐</span> Confirming optimal layouts (parallel)</div>'
            f'<div class="loading-step active"><span class="loading-step-icon">✍️</span> Writing slide content (parallel)</div>'
            f'<div class="loading-step active"><span class="loading-step-icon">🧠</span> AI deciding slide render strategies (parallel)</div>'
            f'<div class="loading-step active"><span class="loading-step-icon">🖼️</span> Generating full-slide images for text-heavy slides</div>'
            f'<div class="loading-step active"><span class="loading-step-icon">🎨</span> Generating infographics for visual slides</div>'
            f'<div class="loading-step active"><span class="loading-step-icon">✨</span> AI polishing ALL slides via Nano Banana Pro</div>'
            f"</div>"
            f'<div class="fact-box"><strong>📈 Did you know?</strong> {get_random_fact()}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )
    with col_game:
        st.markdown('<div class="minigame-wrapper">', unsafe_allow_html=True)
        components.html(_get_snake_game_html(), height=440)
        st.markdown("</div>", unsafe_allow_html=True)

    try:
        contents = orchestrator.run_content_generation()
        st.session_state.slide_contents = contents

        # Render decisions (parallel) — decide image vs standard for each slide
        decisions = orchestrator.run_render_decisions()
        st.session_state.render_decisions = decisions

        # Generate full-slide images for text-heavy slides (parallel)
        image_count = orchestrator.run_slide_image_generation()
        if image_count > 0:
            st.session_state.slide_contents = orchestrator.slide_contents

        # Run infographic evaluation and generation
        proposals = orchestrator.run_infographic_evaluation()
        st.session_state.infographic_proposals = proposals

        if proposals and any(p.infographic_recommended for p in proposals):
            orchestrator.run_infographic_generation()
            st.session_state.slide_contents = orchestrator.slide_contents

        # Universal AI refinement: polish ALL remaining slides via nano banana pro
        # (slides already generated by nano banana skip this step)
        refined_count = orchestrator.run_universal_refinement()
        if refined_count > 0:
            st.session_state.slide_contents = orchestrator.slide_contents

        # Run layout validation (non-blocking)
        orchestrator.run_layout_validation()

        st.session_state.pipeline_phase = "review"
        st.rerun()

    except Exception as e:
        st.session_state.error_message = str(e)
        st.session_state.pipeline_phase = "error"
        st.rerun()


def phase_theme_selection(config: Dict[str, Any]) -> None:
    """Theme selection: show 2 themed sample slides side-by-side using outline content."""
    st.markdown(
        '<p class="phase-title">Phase 4 — Choose Your Theme</p>', unsafe_allow_html=True
    )
    render_progress_bar("theme_selection")

    outline = st.session_state.selected_outline

    if not outline:
        st.session_state.pipeline_phase = "storyline_approval"
        st.rerun()
        return

    # ── Pick a representative slide for preview ──
    # We use the SlidePlan itself as "content" for the preview since generation hasn't happened yet.
    # SlidePlan has title, key_insight, and content_bullets which is enough for a basic preview.
    preview_idx = 0
    for i, s in enumerate(outline.slides):
        if s.layout_type in ("bullet", "split", "chart"):
            preview_idx = i
            break

    preview_plan = outline.slides[preview_idx]
    # Use plan as content proxy
    preview_content = SlideContent(
        title=preview_plan.title, 
        content_bullets=preview_plan.content_bullets,
        key_insight=preview_plan.key_insight
    )

    title_idx = 0
    for i, s in enumerate(outline.slides):
        if s.layout_type == "title":
            title_idx = i
            break
    title_plan = outline.slides[title_idx]
    title_content = SlideContent(
        title=title_plan.title,
        content_bullets=[],
        key_insight=""
    )

    # ── Generate theme previews (once) ──
    if st.session_state.theme_previews is None:
        theme_a, theme_b = pick_two_themes()
        previewer_a = SlidePreviewRenderer(theme=theme_a)
        previewer_b = SlidePreviewRenderer(theme=theme_b)

        st.session_state.theme_previews = {
            "theme_a": theme_a,
            "theme_b": theme_b,
            "preview_a_title": previewer_a.render_slide(title_plan, title_content),
            "preview_a_body": previewer_a.render_slide(preview_plan, preview_content),
            "preview_b_title": previewer_b.render_slide(title_plan, title_content),
            "preview_b_body": previewer_b.render_slide(preview_plan, preview_content),
        }
        st.rerun()
        return

    tp = st.session_state.theme_previews
    theme_a: PresentationTheme = tp["theme_a"]
    theme_b: PresentationTheme = tp["theme_b"]

    st.markdown(
        '<div style="color:#C8D6E5;font-size:0.95rem;margin-bottom:1rem;">'
        "Two visual themes have been generated. Select the one that best matches "
        "your presentation style. Determining the theme now helps the AI generate content with the right tone.</div>",
        unsafe_allow_html=True,
    )

    # ── Side-by-side theme comparison ──
    col_a, col_b = st.columns(2)

    for col, theme, prefix, label in [
        (col_a, theme_a, "a", "A"),
        (col_b, theme_b, "b", "B"),
    ]:
        with col:
            swatch_primary = theme.primary_hex
            swatch_accent = theme.accent_hex

            st.markdown(
                f'<div class="outline-card">'
                f'<div class="card-header">Option {label}: {theme.display_name}</div>'
                f'<div class="card-meta">{theme.description}</div>'
                f'<div style="display:flex;gap:10px;margin-bottom:1rem;">'
                f'<div style="display:flex;align-items:center;gap:6px;">'
                f'<div style="width:18px;height:18px;border-radius:50%;background:{swatch_primary};'
                f'border:1px solid rgba(255,255,255,0.2);"></div>'
                f'<span style="font-size:0.75rem;color:#7B9DBF;">Primary</span></div>'
                f'<div style="display:flex;align-items:center;gap:6px;">'
                f'<div style="width:18px;height:18px;border-radius:50%;background:{swatch_accent};'
                f'border:1px solid rgba(255,255,255,0.2);"></div>'
                f'<span style="font-size:0.75rem;color:#7B9DBF;">Accent</span></div>'
                f'<span class="stat-badge">{theme.font_family}</span>'
                f"</div></div>",
                unsafe_allow_html=True,
            )

            st.markdown(
                '<div style="font-size:0.75rem;color:#5A7A9A;font-weight:600;'
                'text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px;">'
                "Title Slide</div>",
                unsafe_allow_html=True,
            )
            st.image(tp[f"preview_{prefix}_title"], width="stretch")

            st.markdown(
                '<div style="font-size:0.75rem;color:#5A7A9A;font-weight:600;'
                'text-transform:uppercase;letter-spacing:0.5px;margin:8px 0 4px 0;">'
                "Content Slide</div>",
                unsafe_allow_html=True,
            )
            st.image(tp[f"preview_{prefix}_body"], width="stretch")

            if st.button(
                f"✅ Select Theme {label}",
                key=f"select_theme_{prefix}",
                type="primary",
                width="stretch",
            ):
                orchestrator = get_orchestrator()
                selected = theme_a if prefix == "a" else theme_b
                st.session_state.selected_theme = selected
                orchestrator.set_theme(selected)
                st.session_state.slide_previews = None
                # Transition to CONTENT GENERATION instead of REVIEW
                st.session_state.pipeline_phase = "generating"
                st.rerun()

    # ── Or pick from all themes ──
    st.markdown("<br>", unsafe_allow_html=True)

    with st.expander("🎨 Or choose from all available themes", expanded=False):
        all_themes = list(BUILTIN_THEMES.values())
        theme_cols = st.columns(len(all_themes))
        for i, (tc, theme) in enumerate(zip(theme_cols, all_themes)):
            with tc:
                st.markdown(
                    f'<div class="glass-card" style="text-align:center;padding:1rem;">'
                    f'<div style="display:flex;justify-content:center;gap:6px;margin-bottom:8px;">'
                    f'<div style="width:24px;height:24px;border-radius:50%;background:{theme.primary_hex};'
                    f'border:2px solid rgba(255,255,255,0.2);"></div>'
                    f'<div style="width:24px;height:24px;border-radius:50%;background:{theme.accent_hex};'
                    f'border:2px solid rgba(255,255,255,0.2);"></div></div>'
                    f'<div style="font-weight:700;color:#C8D6E5;font-size:0.85rem;margin-bottom:4px;">'
                    f"{theme.display_name}</div>"
                    f'<div style="color:#5A7A9A;font-size:0.7rem;">{theme.description}</div>'
                    f"</div>",
                    unsafe_allow_html=True,
                )
                if st.button(
                    "Select",
                    key=f"select_all_{theme.name}",
                    width="stretch",
                ):
                    orchestrator = get_orchestrator()
                    st.session_state.selected_theme = theme
                    orchestrator.set_theme(theme)
                    st.session_state.slide_previews = None
                    st.session_state.pipeline_phase = "generating"
                    st.rerun()

    # ── Re-shuffle themes ──
    st.markdown("<br>", unsafe_allow_html=True)
    col_regen, _, _ = st.columns([2, 2, 1])
    with col_regen:
        if st.button("🔄  Show Different Themes", width="stretch"):
            st.session_state.theme_previews = None
            st.rerun()


def phase_review(config: Dict[str, Any]) -> None:
    """Review phase: slide-by-slide visual preview with approval workflow."""
    st.markdown(
        '<p class="phase-title">Phase 6 — Review & Approve</p>', unsafe_allow_html=True
    )
    render_progress_bar("review")

    orchestrator = get_orchestrator()
    contents = st.session_state.slide_contents
    outline = st.session_state.selected_outline
    total_slides = len(outline.slides)

    # ── Generate slide previews (once) ──
    if st.session_state.slide_previews is None:
        selected_theme = st.session_state.selected_theme or THEME_CORPORATE_BLUE
        with st.spinner("Rendering slide previews..."):
            try:
                previewer = SlidePreviewRenderer(theme=selected_theme)
                previews = previewer.render_all(outline.slides, contents)
                st.session_state.slide_previews = previews
                # Initialize approvals
                st.session_state.slide_approvals = {
                    i: None for i in range(total_slides)
                }
                st.rerun()
            except Exception as e:
                st.error(f"Preview rendering failed: {e}")
                st.session_state.slide_previews = []

    previews = st.session_state.slide_previews or []
    approvals = st.session_state.slide_approvals
    idx = st.session_state.review_slide_idx

    # Clamp index
    idx = max(0, min(idx, total_slides - 1))

    # ── Approval progress bar ──
    approved_count = sum(1 for v in approvals.values() if v == "approved")
    rejected_count = sum(1 for v in approvals.values() if v == "rejected")
    pending_count = total_slides - approved_count - rejected_count

    st.markdown(
        f'<div class="glass-card" style="padding:1rem 1.5rem;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<div style="display:flex;gap:12px;">'
        f'<span class="stat-badge" style="background:rgba(39,174,96,0.15);color:#27AE60;border-color:rgba(39,174,96,0.3);">✅ {approved_count} Approved</span>'
        f'<span class="stat-badge" style="background:rgba(231,76,60,0.15);color:#E74C3C;border-color:rgba(231,76,60,0.3);">❌ {rejected_count} Rejected</span>'
        f'<span class="stat-badge">⏳ {pending_count} Pending</span>'
        f"</div>"
        f'<span style="color:#7B9DBF;font-size:0.9rem;">Slide {idx + 1} of {total_slides}</span>'
        f"</div></div>",
        unsafe_allow_html=True,
    )

    # ── Slide thumbnail strip ──
    thumb_cols = st.columns(min(total_slides, 12))
    for i in range(min(total_slides, 12)):
        with thumb_cols[i]:
            status = approvals.get(i)
            border_color = (
                "rgba(39,174,96,0.8)"
                if status == "approved"
                else "rgba(231,76,60,0.8)"
                if status == "rejected"
                else "rgba(74,144,217,0.5)"
                if i == idx
                else "rgba(74,144,217,0.15)"
            )
            bg = (
                "rgba(39,174,96,0.1)"
                if status == "approved"
                else "rgba(231,76,60,0.1)"
                if status == "rejected"
                else "rgba(74,144,217,0.15)"
                if i == idx
                else "rgba(22,34,54,0.4)"
            )
            icon = (
                "✅"
                if status == "approved"
                else "❌"
                if status == "rejected"
                else "▸"
                if i == idx
                else str(i + 1)
            )
            if st.button(icon, key=f"thumb_{i}", width="stretch"):
                st.session_state.review_slide_idx = i
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Main slide preview ──
    if idx < len(previews) and previews[idx]:
        slide = outline.slides[idx]
        content = contents[idx]
        approval_status = approvals.get(idx)

        # Status banner
        if approval_status == "approved":
            st.success(f"✅ Slide {idx + 1} is approved")
        elif approval_status == "rejected":
            st.error(f"❌ Slide {idx + 1} is rejected")

        # Slide preview image
        col_preview, col_details = st.columns([3, 1])

        with col_preview:
            st.image(
                previews[idx],
                width="stretch",
                caption=f"Slide {slide.id}: {content.title}",
            )

        with col_details:
            st.markdown(
                f'<div class="glass-card">'
                f'<div style="font-size:0.75rem;color:#5A7A9A;text-transform:uppercase;'
                f'letter-spacing:0.5px;font-weight:600;margin-bottom:8px;">Slide Details</div>'
                f'<div style="color:#C8D6E5;font-size:0.9rem;font-weight:600;margin-bottom:4px;">{content.title}</div>'
                f'<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px;">'
                f'<span class="stat-badge" style="font-size:0.7rem;padding:3px 8px;">{slide.layout_type}</span>'
                f'<span class="stat-badge" style="font-size:0.7rem;padding:3px 8px;">{slide.visual_type}</span>'
                f"</div></div>",
                unsafe_allow_html=True,
            )

            # ── Visual Type Switcher (skip title/closing) ──
            if slide.layout_type not in ("title", "closing"):
                current_option = _get_current_visual_option(slide)
                options_list = list(VISUAL_TYPE_OPTIONS.keys())
                current_vis_idx = (
                    options_list.index(current_option)
                    if current_option in options_list
                    else len(options_list) - 1
                )
                selected_visual = st.selectbox(
                    "Visual Type",
                    options=options_list,
                    index=current_vis_idx,
                    key=f"review_visual_{idx}",
                )
                if selected_visual != current_option:
                    new_layout, new_visual = VISUAL_TYPE_OPTIONS[selected_visual]
                    slide.layout_type = new_layout
                    slide.visual_type = new_visual
                    st.session_state.slide_previews = None
                    st.rerun()

            if content.key_insight:
                st.markdown(
                    f'<div class="glass-card" style="padding:1rem;">'
                    f'<div style="font-size:0.72rem;color:#4A90D9;font-weight:700;'
                    f'text-transform:uppercase;margin-bottom:4px;">Key Insight</div>'
                    f'<div style="color:#C8D6E5;font-size:0.85rem;">{content.key_insight}</div>'
                    f"</div>",
                    unsafe_allow_html=True,
                )

            # Content bullets
            with st.expander("📝 Content Bullets", expanded=False):
                for bullet in content.content_bullets:
                    st.markdown(f"- {bullet}")

            if content.speaker_notes:
                with st.expander("🎤 Speaker Notes", expanded=False):
                    st.markdown(content.speaker_notes)

            if content.chart_data:
                with st.expander("📊 Chart Data", expanded=False):
                    st.json(content.chart_data.model_dump(), expanded=False)

            if content.table_data:
                with st.expander("📋 Table Data", expanded=False):
                    st.json(content.table_data.model_dump(), expanded=False)

            # ── AI Regeneration Section ──
            if slide.layout_type not in ("title", "closing"):
                with st.expander("🤖 AI Regeneration", expanded=False):
                    regen_prompt = st.text_area(
                        "Custom Instructions",
                        placeholder="Enter custom instructions for regeneration (e.g., 'Focus on growth metrics' or 'Make it more data-driven')...",
                        height=80,
                        key=f"regen_prompt_{idx}",
                    )
                    if st.button(
                        "🔄 Regenerate with AI",
                        key=f"regen_btn_{idx}",
                        width="stretch",
                    ):
                        regen_orchestrator = get_orchestrator()
                        with st.spinner("Regenerating slide content..."):
                            new_content = regen_orchestrator.regenerate_single_slide(
                                slide_index=idx,
                                custom_prompt=regen_prompt,
                            )
                        if new_content:
                            st.session_state.slide_contents[idx] = new_content
                            st.session_state.slide_previews = None
                            st.success("Slide regenerated successfully!")
                            st.rerun()
                        else:
                            st.error("Regeneration failed. Please try again.")

            # ── Universal Infographic Section ──
            if slide.layout_type not in ("title", "closing"):
                proposals = st.session_state.get("infographic_proposals", [])
                current_proposal = None
                for p in proposals:
                    if p.slide_number == slide.id and p.infographic_recommended:
                        current_proposal = p
                        break

                with st.expander(
                    "🎨 Infographic",
                    expanded=bool(getattr(content, "infographic_image", None)),
                ):
                    if getattr(content, "infographic_image", None):
                        st.image(
                            content.infographic_image,
                            caption="Generated Infographic",
                            use_container_width=True,
                        )
                    else:
                        st.info(
                            "No infographic image generated yet. Use the button below to generate one."
                        )

                    # Use existing proposal prompt or generate default
                    default_prompt = (
                        current_proposal.generated_prompt
                        if current_proposal and current_proposal.generated_prompt
                        else f"Professional infographic about {content.title}: {content.key_insight}. "
                        f"Clean modern design, 16:9 widescreen format."
                    )
                    default_placement = (
                        current_proposal.placement if current_proposal else "full-slide"
                    )

                    edited_prompt = st.text_area(
                        "Infographic Prompt",
                        value=default_prompt,
                        height=120,
                        key=f"infographic_prompt_{idx}",
                        help="Edit the prompt and click Generate/Regenerate to create an infographic",
                    )

                    placement_options = ["full-slide", "right-column", "bottom-section"]
                    new_placement = st.selectbox(
                        "Placement",
                        placement_options,
                        index=placement_options.index(default_placement)
                        if default_placement in placement_options
                        else 0,
                        key=f"infographic_placement_{idx}",
                    )

                    btn_label = (
                        "🔄 Regenerate Infographic"
                        if getattr(content, "infographic_image", None)
                        else "🎨 Generate Infographic"
                    )
                    if st.button(
                        btn_label,
                        key=f"regen_infographic_{idx}",
                        width="stretch",
                    ):
                        regen_orchestrator = get_orchestrator()
                        # Create proposal on the fly if none exists
                        if not current_proposal:
                            from models import InfographicProposal

                            current_proposal = InfographicProposal(
                                slide_number=slide.id,
                                slide_title=content.title,
                                infographic_recommended=True,
                                infographic_type="Data-Driven",
                                placement=new_placement,
                                generated_prompt=edited_prompt,
                            )
                            proposals.append(current_proposal)
                            st.session_state.infographic_proposals = proposals

                        with st.spinner("Generating infographic..."):
                            new_image = regen_orchestrator.regenerate_infographic(
                                slide_number=slide.id,
                                new_prompt=edited_prompt,
                                placement=new_placement,
                            )
                        if new_image:
                            contents[idx].infographic_image = new_image
                            # Clear stale full_slide_image so the new infographic
                            # is actually used during PPTX rendering (ppt_generator
                            # skips layout-specific rendering when full_slide_image exists)
                            contents[idx].full_slide_image = None
                            st.session_state.slide_contents = contents
                            current_proposal.generated_prompt = edited_prompt
                            current_proposal.placement = new_placement
                            st.session_state.slide_previews = None
                            st.rerun()
                        else:
                            st.error(
                                "Failed to generate infographic. Check API and try again."
                            )

    # ── Action buttons ──
    st.markdown("<br>", unsafe_allow_html=True)

    col_prev, col_approve, col_reject, col_next = st.columns([1, 2, 2, 1])

    with col_prev:
        if st.button("⬅ Prev", width="stretch", disabled=(idx == 0)):
            st.session_state.review_slide_idx = idx - 1
            st.rerun()

    with col_approve:
        if st.button("✅  Approve Slide", type="primary", width="stretch"):
            st.session_state.slide_approvals[idx] = "approved"
            # Auto-advance to next pending slide
            next_idx = _find_next_pending(idx, total_slides, approvals)
            st.session_state.review_slide_idx = next_idx
            st.rerun()

    with col_reject:
        if st.button("❌  Reject Slide", width="stretch"):
            st.session_state.slide_approvals[idx] = "rejected"
            next_idx = _find_next_pending(idx, total_slides, approvals)
            st.session_state.review_slide_idx = next_idx
            st.rerun()

    with col_next:
        if st.button("Next ➡", width="stretch", disabled=(idx >= total_slides - 1)):
            st.session_state.review_slide_idx = idx + 1
            st.rerun()

    # ── Final actions ──
    st.markdown("---")

    all_reviewed = all(v is not None for v in approvals.values())
    has_approved = approved_count > 0

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        btn_label = (
            f"✅  Generate PPTX ({approved_count} slides)"
            if has_approved
            else "✅  Approve All & Generate"
        )
        if st.button(
            btn_label,
            type="primary",
            width="stretch",
            disabled=(not has_approved and not all_reviewed),
        ):
            if not has_approved:
                # Approve all if none reviewed yet
                st.session_state.slide_approvals = {
                    i: "approved" for i in range(total_slides)
                }
            st.session_state.pipeline_phase = "finalizing"
            st.rerun()
    with col2:
        if st.button("🔄  Regenerate All Content", width="stretch"):
            st.session_state.slide_contents = None
            st.session_state.validation_results = None
            st.session_state.slide_previews = None
            st.session_state.infographic_proposals = []
            st.session_state.review_slide_idx = 0
            st.session_state.slide_approvals = {}
            st.session_state.pipeline_phase = "generating"
            st.rerun()
    with col3:
        if st.button("✅ All", width="stretch", help="Approve all slides at once"):
            st.session_state.slide_approvals = {
                i: "approved" for i in range(total_slides)
            }
            st.rerun()


def _find_next_pending(current: int, total: int, approvals: dict) -> int:
    """Find the next pending (unreviewed) slide, wrapping around."""
    for offset in range(1, total):
        candidate = (current + offset) % total
        if approvals.get(candidate) is None:
            return candidate
    return min(current + 1, total - 1)


def phase_finalizing(config: Dict[str, Any]) -> None:
    """Final PPTX generation phase."""
    st.markdown(
        '<p class="phase-title">Phase 7 — Building Presentation</p>',
        unsafe_allow_html=True,
    )
    render_progress_bar("finalizing")

    orchestrator = get_orchestrator()

    # Ensure the selected theme is applied
    selected_theme = st.session_state.selected_theme
    if selected_theme:
        orchestrator.set_theme(selected_theme)

    st.markdown(
        '<div class="glass-card loading-container">'
        '<div class="loading-spinner"></div>'
        '<div class="loading-title">Assembling Your Presentation</div>'
        '<div class="loading-subtitle">Rendering slides, charts, and tables into a PPTX file</div>'
        '<div class="shimmer-bar"></div>'
        '<div class="loading-steps">'
        '<div class="loading-step active"><span class="loading-step-icon">📊</span> Rendering charts, tables, and infographics</div>'
        '<div class="loading-step active"><span class="loading-step-icon">📦</span> Packaging into PowerPoint file</div>'
        "</div>"
        f'<div class="fact-box"><strong>📈 Did you know?</strong> {get_random_fact()}</div>'
        "</div>",
        unsafe_allow_html=True,
    )

    try:
        output_path = orchestrator.run_pptx_generation()
        st.session_state.output_path = output_path
        st.session_state.output_gcs_uri = orchestrator.state.output_gcs_uri
        st.session_state.pipeline_phase = "done"
        st.rerun()

    except Exception as e:
        st.session_state.error_message = str(e)
        st.session_state.pipeline_phase = "error"
        st.rerun()


def _get_pptx_bytes() -> Optional[Tuple[bytes, str]]:
    """Get PPTX file bytes and filename. Tries local file first, falls back to GCS.

    Returns:
        Tuple of (file_bytes, filename) or None if unavailable.
    """
    output_path = st.session_state.get("output_path")
    gcs_uri = st.session_state.get("output_gcs_uri")

    # Try local file first
    if output_path and Path(output_path).exists():
        with open(output_path, "rb") as f:
            return f.read(), Path(output_path).name

    # Fall back to GCS
    if gcs_uri:
        from utils.gcp_storage import get_storage_manager
        storage = get_storage_manager()
        if storage.enabled:
            # Parse gs://bucket-name/path/to/blob
            parts = gcs_uri.split("/", 3)
            if len(parts) == 4:
                blob_name = parts[3]
            else:
                blob_name = gcs_uri
            data = storage.download_file(blob_name)
            if data:
                filename = Path(blob_name).name if output_path is None else Path(output_path).name
                return data, filename

    return None


def phase_present_slide(config: Dict[str, Any]) -> None:
    """Presentation Mode: Full-screen immersive slideshow."""
    
    # ── Immersive CSS ──
    st.markdown(
        """
        <style>
            /* Hide Streamlit UI elements */
            [data-testid="stSidebar"] {display: none;}
            [data-testid="stHeader"] {display: none;}
            footer {display: none;}
            
            /* Maximize content area */
            .main .block-container {
                padding-top: 1rem !important;
                padding-bottom: 1rem !important;
                padding-left: 1rem !important;
                padding-right: 1rem !important;
                max-width: 100% !important;
            }
            
            /* Black background for immersive feel */
            .stApp {
                background-color: #0E1117;
            }
            
            /* Custom button styling for presentation controls */
            div.stButton > button {
                background-color: rgba(255, 255, 255, 0.1);
                color: #FAFAFA;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            div.stButton > button:hover {
                background-color: rgba(255, 255, 255, 0.2);
                border-color: rgba(255, 255, 255, 0.5);
                color: #FFFFFF;
            }
        </style>
        """,
        unsafe_allow_html=True
    )

    contents = st.session_state.slide_contents
    outline = st.session_state.selected_outline
    selected_theme = st.session_state.selected_theme

    if not contents or not outline:
        st.session_state.pipeline_phase = "done"
        st.rerun()
        return

    # Use session state for current slide index
    if "present_idx" not in st.session_state:
        st.session_state.present_idx = 0
    
    idx = st.session_state.present_idx
    total = len(contents)
    
    # ── Render Slide Image (use cached previews from review phase) ──
    previews = st.session_state.get("slide_previews") or []
    if previews and idx < len(previews) and previews[idx]:
        image_bytes = previews[idx]
    else:
        # Fallback: render on demand and cache for subsequent navigation
        from generators.slide_previewer import SlidePreviewRenderer
        renderer = SlidePreviewRenderer(theme=selected_theme)
        renderer._total_slides = total
        renderer._topic = st.session_state.get("topic", "")
        image_bytes = renderer.render_slide(outline.slides[idx], contents[idx])
        # Cache in session state to avoid re-rendering on navigation
        if not previews:
            previews = [None] * total
            st.session_state.slide_previews = previews
        previews[idx] = image_bytes
    
    # ── Top Navigation Bar ──
    # [ Slide X/Y ] [ Prev ] [ Next ] [ Exit ]
    
    col_info, col_prev, col_next, col_exit = st.columns([4, 1, 1, 1])
    
    with col_info:
        st.markdown(
            f"<div style='font-size:1.2rem; color:#DDD; font-weight:600; padding-top:5px;'>"
            f"Slide {idx + 1} / {total} — <span style='color:#AAA; font-weight:400;'>{contents[idx].title}</span>"
            f"</div>",
            unsafe_allow_html=True
        )

    with col_prev:
        if st.button("⬅ Previous", key="pres_prev", disabled=(idx == 0), use_container_width=True):
            st.session_state.present_idx = max(0, idx - 1)
            st.rerun()
            
    with col_next:
        if st.button("Next ➡", key="pres_next", disabled=(idx == total - 1), use_container_width=True):
            st.session_state.present_idx = min(total - 1, idx + 1)
            st.rerun()
            
    with col_exit:
        if st.button("❌ Exit", key="pres_exit", type="primary", use_container_width=True):
            st.session_state.pipeline_phase = "done"
            st.rerun()

    # ── Main Slide Display ──
    # Full width image
    st.image(image_bytes, use_container_width=True)
    
    # ── Fullscreen Toggle Script ──
    # This renders a hidden component that executes JS to request fullscreen on load if not already.
    # Note: Browsers block auto-fullscreen without user interaction.
    # So we provide a manual button below the image as a fallback/primary method.
    
    st.markdown(
        """
        <script>
        function toggleFullScreen() {
            var doc = window.parent.document;
            if (!doc.fullscreenElement) {
                doc.documentElement.requestFullscreen();
            } else {
                if (doc.exitFullscreen) {
                    doc.exitFullscreen();
                }
            }
        }
        </script>
        """, 
        unsafe_allow_html=True
    )
    
    # Centered "Enter Fullscreen" button (optional helper), using Streamlit component for JS trigger is hard.
    # We'll stick to making the viewport "feel" fullscreen via CSS above.
    # The user can press F11 for browser fullscreen.
    
    st.markdown(
        "<div style='text-align:center; color:#555; font-size:0.8rem; margin-top:10px;'>"
        "Tip: Press <strong>F11</strong> for browser fullscreen experience."
        "</div>",
        unsafe_allow_html=True
    )


def phase_done(config: Dict[str, Any]) -> None:
    """Done: show download, email, and present options."""
    st.markdown(
        '<p class="phase-title">Presentation Complete</p>', unsafe_allow_html=True
    )
    render_progress_bar("done")

    pptx_result = _get_pptx_bytes()
    output_path = st.session_state.output_path

    if pptx_result:
        pptx_bytes, pptx_filename = pptx_result
        st.markdown(
            f'<div class="glass-card" style="text-align:center;padding:2rem;">'
            f'<div style="font-size:1.5rem;margin-bottom:0.5rem;">🎉</div>'
            f'<div style="color:#C8D6E5;font-size:1.05rem;font-weight:600;">'
            f"Your presentation is ready</div>"
            f'<div style="color:#5A7A9A;font-size:0.85rem;margin-top:4px;">'
            f"{pptx_filename}</div></div>",
            unsafe_allow_html=True,
        )

        col_dl, col_mail, col_pres = st.columns(3)

        with col_dl:
            st.download_button(
                label="📥  Download PPTX",
                data=pptx_bytes,
                file_name=pptx_filename,
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                type="primary",
                use_container_width=True,
            )

        with col_pres:
            if st.button("📺 Present Online", width="stretch"):
                st.session_state.pipeline_phase = "present"
                st.rerun()

        st.markdown("### 📧 Email Presentation")
        with st.expander("Send Copy via Email", expanded=False):
            email_to = st.text_input("Recipient Email")
            email_subject = st.text_input("Subject", value=f"Presentation: {pptx_filename}")

            st.caption("Requires SMTP credentials (e.g. Gmail App Password)")
            col_cr1, col_cr2 = st.columns(2)
            with col_cr1:
                email_user = st.text_input("Your Email", value=os.environ.get("SMTP_EMAIL", ""))
            with col_cr2:
                email_pass = st.text_input("App Password", type="password", value=os.environ.get("SMTP_PASSWORD", ""))

            if st.button("Send Email 📤", disabled=not (email_to and email_user and email_pass)):
                from utils.email_sender import send_email_with_attachment, send_email_with_attachment_bytes
                with st.spinner("Sending email..."):
                    success = send_email_with_attachment_bytes(
                        to_email=email_to,
                        subject=email_subject,
                        body="Please find the attached presentation.",
                        attachment_bytes=pptx_bytes,
                        filename=pptx_filename,
                        sender_email=email_user,
                        sender_password=email_pass,
                    )
                    if success:
                        st.success("Email sent successfully!")
                    else:
                        st.error("Failed to send email. Check credentials.")

        # Summary stats
        outline = st.session_state.selected_outline
        if outline:
            findings = st.session_state.research_findings or []
            charts_tables = sum(
                1
                for c in (st.session_state.slide_contents or [])
                if c.chart_data or c.table_data
            )
            source_count = 0
            if findings:
                source_count = sum(len(f.sources) for f in findings)

            cols = st.columns(4)
            metrics = [
                (str(len(outline.slides)), "Total Slides"),
                (outline.framework_name, "Framework"),
                (str(source_count), "Sources"),
                (str(charts_tables), "Charts & Tables"),
            ]
            for col, (value, label) in zip(cols, metrics):
                with col:
                    st.markdown(
                        f'<div class="metric-card">'
                        f'<div class="metric-value">{value}</div>'
                        f'<div class="metric-label">{label}</div></div>',
                        unsafe_allow_html=True,
                    )

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄  Start New Presentation", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


def phase_error(config: Dict[str, Any]) -> None:
    """Error state: show error and retry option."""
    st.markdown('<p class="phase-title">An Error Occurred</p>', unsafe_allow_html=True)

    error_msg = st.session_state.error_message or "Unknown error"
    st.error(f"**Error:** {error_msg}")

    st.markdown(
        '<div class="glass-card">'
        '<div style="color:#C8D6E5;font-weight:600;margin-bottom:0.5rem;">Possible causes:</div>'
        '<div style="color:#7B9DBF;font-size:0.9rem;">'
        "• Invalid or missing <code>GEMINI_API_KEY</code> in <code>.env</code><br>"
        "• API rate limiting (wait a moment and retry)<br>"
        "• Network connectivity issues</div></div>",
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄  Retry Last Step", width="stretch"):
            st.session_state.error_message = None
            orchestrator = get_orchestrator()
            status = orchestrator.state.status
            if status == "error":
                st.session_state.pipeline_phase = "idle"
            else:
                st.session_state.pipeline_phase = status
            st.rerun()
    with col2:
        if st.button("🏠  Start Over", width="stretch"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


# ── Main App ────────────────────────────────────────────────
def main() -> None:
    """Main application entry point."""
    init_session_state()
    config = render_sidebar()

    # Phase dispatcher
    phase = st.session_state.pipeline_phase
    phases = {
        "idle": phase_idle,
        "researching": phase_researching,
        "framework_selection": phase_framework_selection,
        "storyline_approval": phase_storyline_approval,
        "theme_selection": phase_theme_selection,
        "generating": phase_generating,
        "review": phase_review,
        "finalizing": phase_finalizing,
        "done": phase_done,
        "present": phase_present_slide,
        "error": phase_error,
    }

    handler = phases.get(phase, phase_idle)
    handler(config)



if __name__ == "__main__":
    main()
