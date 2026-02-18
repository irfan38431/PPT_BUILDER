"""
generators/slide_previewer.py — Renders individual slides to PNG images.
Uses matplotlib to render slide layouts that match the final PPTX output.
Now theme-aware with consultant-quality visuals matching ppt_generator.py.
"""

from __future__ import annotations

import io
import logging
import textwrap
from typing import List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import numpy as np

from agents.slide_content_agent import SlideContent
from generators.chart_annotator import ChartAnnotator
from generators.themes import PresentationTheme, THEME_CORPORATE_BLUE
from models import SlidePlan
from utils.gcp_storage import get_storage_manager

logger = logging.getLogger(__name__)

# Slide dimensions (13.333 x 7.5 aspect = 16:9)
FIG_W = 13.333
FIG_H = 7.5


class SlidePreviewRenderer:
    """Renders slide plans + content as PNG images for in-browser preview."""

    def __init__(self, theme: Optional[PresentationTheme] = None) -> None:
        self._theme = theme or THEME_CORPORATE_BLUE
        self._chart_gen = ChartAnnotator(theme=self._theme)
        self._total_slides: int = 0
        self._topic: str = ""

    @property
    def theme(self) -> PresentationTheme:
        return self._theme

    @theme.setter
    def theme(self, t: PresentationTheme) -> None:
        self._theme = t
        self._chart_gen.theme = t

    def render_slide(self, plan: SlidePlan, content: SlideContent) -> bytes:
        """Render a single slide to a PNG image (bytes)."""
        # Full-slide image takes priority (already a PNG from Render Deciding Agent)
        if getattr(content, "full_slide_image", None):
            res_bytes = content.full_slide_image
        else:
            layout_type = plan.layout_type.lower()
            dispatch = {
                "title": self._render_title,
                "bullet": self._render_bullet,
                "chart": self._render_chart,
                "table": self._render_table,
                "split": self._render_split,
                "exec_summary": self._render_exec_summary,
                "section_divider": self._render_section_divider,
                "closing": self._render_closing,
            }
            renderer = dispatch.get(layout_type, self._render_bullet)
            res_bytes = renderer(plan, content)

        # Upload to GCS if configured
        try:
            storage = get_storage_manager()
            if storage.enabled:
                filename = storage.generate_unique_filename("images/previews", ".png")
                storage.upload_file(res_bytes, filename, content_type="image/png")
        except Exception as e:
            logger.warning(f"Failed to upload slide preview to GCS: {e}")

        return res_bytes

    def render_all(
        self,
        slides: List[SlidePlan],
        contents: List[SlideContent],
        topic: str = "",
    ) -> List[bytes]:
        """Render all slides to PNG images."""
        self._total_slides = len(slides)
        self._topic = topic
        return [
            self.render_slide(plan, content)
            for plan, content in zip(slides, contents)
        ]

    # ── Figure Helpers ───────────────────────────────────────

    def _new_figure(self, bg_color=None):
        """Create a new matplotlib figure with slide proportions."""
        if bg_color is None:
            bg_color = self._theme.mpl_bg_white
        fig, ax = plt.subplots(1, 1, figsize=(FIG_W, FIG_H), dpi=120)
        fig.patch.set_facecolor(bg_color)
        ax.set_xlim(0, FIG_W)
        ax.set_ylim(0, FIG_H)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.invert_yaxis()
        return fig, ax

    def _new_gradient_figure(self):
        """Create a figure with gradient background matching PPTX title/section slides."""
        t = self._theme
        fig, ax = plt.subplots(1, 1, figsize=(FIG_W, FIG_H), dpi=120)
        fig.patch.set_facecolor(t.mpl_primary)
        ax.set_xlim(0, FIG_W)
        ax.set_ylim(0, FIG_H)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.invert_yaxis()

        # Render gradient background via imshow
        gradient = np.linspace(0, 1, 256).reshape(1, -1)
        gradient = np.vstack([gradient] * 50)
        cmap = mcolors.LinearSegmentedColormap.from_list(
            "slide_grad", [t.mpl_primary, t.mpl_gradient_end]
        )
        ax.imshow(
            gradient, aspect="auto", cmap=cmap,
            extent=[0, FIG_W, FIG_H, 0], zorder=-1,
        )
        return fig, ax

    def _fig_to_bytes(self, fig) -> bytes:
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0.1, dpi=120)
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    # ── Decorative Helpers ───────────────────────────────────

    def _add_left_accent_bar(self, ax) -> None:
        """Thin vertical accent bar on left edge."""
        t = self._theme
        rect = mpatches.Rectangle(
            (0, 0), 0.15, FIG_H,
            facecolor=t.mpl_accent, edgecolor="none", zorder=2,
        )
        ax.add_patch(rect)

    def _add_bottom_accent_strip(self, ax) -> None:
        """Thin primary-colored strip at the bottom."""
        t = self._theme
        rect = mpatches.Rectangle(
            (0, FIG_H - 0.12), FIG_W, 0.12,
            facecolor=t.mpl_primary, edgecolor="none", zorder=2,
        )
        ax.add_patch(rect)

    def _add_footer_accent_line(self, ax) -> None:
        """Thin line above footer area."""
        t = self._theme
        ax.plot(
            [0.7, FIG_W - 0.7], [FIG_H - 0.6, FIG_H - 0.6],
            color=t.mpl_text_muted, linewidth=0.5, zorder=2,
        )

    def _add_header(self, ax, title: str, slide_id: int) -> None:
        """Add title and accent line (matching ppt_generator 28pt header)."""
        t = self._theme
        ax.text(
            0.7, 0.5, title,
            fontsize=22, fontweight="bold", color=t.mpl_primary,
            ha="left", va="top",
            fontfamily=t.font_family,
        )
        ax.plot(
            [0.7, 3.7], [1.15, 1.15],
            color=t.mpl_accent, linewidth=3, solid_capstyle="round",
        )

    def _add_footer(self, ax, slide_id: int) -> None:
        t = self._theme

        # Topic name on the left
        if self._topic:
            display_topic = self._topic[:50] + "..." if len(self._topic) > 50 else self._topic
            ax.text(
                0.7, FIG_H - 0.3, display_topic,
                fontsize=7, color=t.mpl_text_muted, ha="left", va="bottom",
                fontfamily=t.font_family,
            )

        # "Slide X of Y" on the right
        total = self._total_slides if self._total_slides > 0 else slide_id
        ax.text(
            FIG_W - 0.5, FIG_H - 0.3, f"Slide {slide_id} of {total}",
            fontsize=7, color=t.mpl_text_muted, ha="right", va="bottom",
            fontfamily=t.font_family,
        )

    def _add_insight_bar(self, ax, insight: str) -> None:
        t = self._theme
        rect = mpatches.FancyBboxPatch(
            (0.4, FIG_H - 1.55), FIG_W - 0.8, 0.65,
            boxstyle="round,pad=0.1",
            facecolor=t.mpl_insight_bg,
            edgecolor=t.mpl_accent,
            linewidth=1.5,
        )
        ax.add_patch(rect)
        ax.text(
            0.7, FIG_H - 1.23,
            f"\u2605 KEY INSIGHT:  {insight}",
            fontsize=9, color=t.mpl_text_dark, ha="left", va="center",
            fontweight="bold",
        )

    # ── Title Slide ─────────────────────────────────────────

    def _render_title(self, plan: SlidePlan, content: SlideContent) -> bytes:
        t = self._theme
        fig, ax = self._new_gradient_figure()

        white = (1.0, 1.0, 1.0)

        # Top accent bar
        rect = mpatches.Rectangle(
            (0, 0), FIG_W, 0.06,
            facecolor=t.mpl_accent, edgecolor="none", zorder=2,
        )
        ax.add_patch(rect)

        # Title (large, centered)
        ax.text(
            FIG_W / 2, 2.5, content.title,
            fontsize=32, fontweight="bold", color=white,
            ha="center", va="center", wrap=True,
            fontfamily=t.heading_font,
        )

        # Accent divider
        ax.plot(
            [FIG_W / 2 - 2.0, FIG_W / 2 + 2.0], [3.8, 3.8],
            color=t.mpl_accent, linewidth=4, solid_capstyle="round",
        )

        # Subtitle
        if content.key_insight:
            ax.text(
                FIG_W / 2, 4.5, content.key_insight,
                fontsize=15, color=white,
                ha="center", va="center",
                fontfamily=t.body_font,
            )

        # Bottom accent strip
        rect = mpatches.Rectangle(
            (0, FIG_H - 0.12), FIG_W, 0.12,
            facecolor=t.mpl_accent, edgecolor="none", zorder=2,
        )
        ax.add_patch(rect)

        return self._fig_to_bytes(fig)

    # ── Bullet Slide ────────────────────────────────────────

    def _render_bullet(self, plan: SlidePlan, content: SlideContent) -> bytes:
        t = self._theme
        fig, ax = self._new_figure()
        self._add_left_accent_bar(ax)
        self._add_bottom_accent_strip(ax)
        self._add_header(ax, content.title, plan.id)

        if getattr(content, "infographic_image", None):
            self._add_infographic_preview(ax, content.infographic_image)
        else:
            y_start = 1.8
            for i, bullet in enumerate(content.content_bullets[:6]):
                display = textwrap.fill(bullet, width=60)
                # Accent-colored bullet character
                ax.text(
                    1.0, y_start + i * 0.65,
                    "\u25cf",
                    fontsize=8, color=t.mpl_accent,
                    ha="left", va="top",
                )
                ax.text(
                    1.4, y_start + i * 0.65,
                    display,
                    fontsize=12, color=t.mpl_text_dark,
                    ha="left", va="top",
                    fontfamily=t.body_font,
                )

        if content.key_insight:
            self._add_insight_bar(ax, content.key_insight)

        self._add_footer_accent_line(ax)
        self._add_footer(ax, plan.id)
        return self._fig_to_bytes(fig)

    def _add_infographic_preview(self, ax, image_bytes: bytes) -> None:
        """Render an infographic image in the slide preview."""
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        img_arr = np.array(img)
        imagebox = OffsetImage(img_arr, zoom=0.38)
        ab = AnnotationBbox(imagebox, (FIG_W / 2, 3.8), frameon=False)
        ax.add_artist(ab)

    # ── Chart Slide ─────────────────────────────────────────

    def _render_chart(self, plan: SlidePlan, content: SlideContent) -> bytes:
        t = self._theme
        fig, ax = self._new_figure()
        self._add_left_accent_bar(ax)
        self._add_bottom_accent_strip(ax)
        self._add_header(ax, content.title, plan.id)

        if content.chart_data:
            chart_buf = self._chart_gen.generate(content.chart_data)
            chart_buf.seek(0)
            from PIL import Image
            chart_img = Image.open(chart_buf)
            chart_arr = np.array(chart_img)

            imagebox = OffsetImage(chart_arr, zoom=0.45)
            ab = AnnotationBbox(imagebox, (FIG_W / 2, 4.0), frameon=False)
            ax.add_artist(ab)
        else:
            ax.text(
                FIG_W / 2, 4.0,
                "[ Chart placeholder — no data available ]",
                fontsize=14, color=t.mpl_text_muted, ha="center", va="center",
                style="italic",
            )

        self._add_footer_accent_line(ax)
        self._add_footer(ax, plan.id)
        return self._fig_to_bytes(fig)

    # ── Table Slide ─────────────────────────────────────────

    def _render_table(self, plan: SlidePlan, content: SlideContent) -> bytes:
        t = self._theme
        fig, ax = self._new_figure()
        self._add_left_accent_bar(ax)
        self._add_bottom_accent_strip(ax)
        self._add_header(ax, content.title, plan.id)

        if content.table_data:
            headers = content.table_data.headers
            rows = content.table_data.rows[:8]
            n_cols = len(headers)
            n_rows = len(rows)

            col_width = min(11.0 / max(n_cols, 1), 3.0)
            table_left = 1.0
            table_top = 2.0
            row_h = 0.45

            for c, header in enumerate(headers):
                rect = mpatches.FancyBboxPatch(
                    (table_left + c * col_width, table_top),
                    col_width - 0.05, row_h,
                    boxstyle="round,pad=0.02",
                    facecolor=t.mpl_primary, edgecolor="none",
                )
                ax.add_patch(rect)
                ax.text(
                    table_left + c * col_width + col_width / 2,
                    table_top + row_h / 2,
                    header[:15],
                    fontsize=9, fontweight="bold", color=(1, 1, 1),
                    ha="center", va="center",
                )

            for r, row in enumerate(rows):
                y = table_top + (r + 1) * row_h
                bg = t.mpl_bg_light if r % 2 == 0 else t.mpl_bg_white
                for c in range(n_cols):
                    cell_val = row[c] if c < len(row) else ""
                    rect = mpatches.FancyBboxPatch(
                        (table_left + c * col_width, y),
                        col_width - 0.05, row_h,
                        boxstyle="round,pad=0.02",
                        facecolor=bg, edgecolor=(0.9, 0.9, 0.9),
                    )
                    ax.add_patch(rect)
                    ax.text(
                        table_left + c * col_width + col_width / 2,
                        y + row_h / 2,
                        str(cell_val)[:20],
                        fontsize=8, color=t.mpl_text_dark,
                        ha="center", va="center",
                    )

            if content.table_data.source_annotation:
                ax.text(
                    table_left, table_top + (n_rows + 1.3) * row_h,
                    content.table_data.source_annotation,
                    fontsize=7, color=t.mpl_text_muted, ha="left", va="top",
                    style="italic",
                )
        else:
            ax.text(
                FIG_W / 2, 4.0,
                "[ Table placeholder — no data available ]",
                fontsize=14, color=t.mpl_text_muted, ha="center", va="center",
                style="italic",
            )

        self._add_footer_accent_line(ax)
        self._add_footer(ax, plan.id)
        return self._fig_to_bytes(fig)

    # ── Split Slide ─────────────────────────────────────────

    def _render_split(self, plan: SlidePlan, content: SlideContent) -> bytes:
        t = self._theme
        fig, ax = self._new_figure()
        self._add_left_accent_bar(ax)
        self._add_bottom_accent_strip(ax)
        self._add_header(ax, content.title, plan.id)

        # Accent vertical divider
        rect = mpatches.Rectangle(
            (6.5, 1.5), 0.02, 4.5,
            facecolor=t.mpl_accent, edgecolor="none", zorder=2,
        )
        ax.add_patch(rect)

        # Left panel — bullets with triangle markers
        y_start = 2.0
        for i, bullet in enumerate(content.content_bullets[:5]):
            display = textwrap.fill(bullet, width=50)
            ax.text(
                1.0, y_start + i * 0.75,
                "\u25b8",
                fontsize=8, color=t.mpl_accent,
                ha="left", va="top",
            )
            ax.text(
                1.3, y_start + i * 0.75,
                display,
                fontsize=9, color=t.mpl_text_dark, ha="left", va="top",
                fontfamily=t.body_font,
            )

        # Right panel — positioned below header with adequate spacing
        if content.chart_data:
            try:
                chart_buf = self._chart_gen.generate(content.chart_data)
                chart_buf.seek(0)
                from PIL import Image
                chart_img = Image.open(chart_buf)
                chart_arr = np.array(chart_img)
                imagebox = OffsetImage(chart_arr, zoom=0.27)
                ab = AnnotationBbox(imagebox, (FIG_W * 0.74, 4.0), frameon=False)
                ax.add_artist(ab)
            except Exception:
                ax.text(
                    FIG_W * 0.74, 4.0, "[ Chart ]",
                    fontsize=12, color=t.mpl_text_muted, ha="center", va="center",
                )
        else:
            ax.text(
                FIG_W * 0.73, 3.8, "[ Visual ]",
                fontsize=12, color=t.mpl_text_muted, ha="center", va="center",
                style="italic",
            )

        if content.key_insight:
            self._add_insight_bar(ax, content.key_insight)

        self._add_footer_accent_line(ax)
        self._add_footer(ax, plan.id)
        return self._fig_to_bytes(fig)

    # ── Exec Summary Slide ──────────────────────────────────

    def _render_exec_summary(self, plan: SlidePlan, content: SlideContent) -> bytes:
        t = self._theme
        fig, ax = self._new_figure()
        self._add_left_accent_bar(ax)
        self._add_bottom_accent_strip(ax)
        self._add_header(ax, content.title, plan.id)

        kpis = []
        findings = []
        for bullet in content.content_bullets:
            if ":" in bullet and len(bullet) < 60:
                parts = bullet.split(":", 1)
                kpis.append((parts[0].strip(), parts[1].strip()))
            else:
                findings.append(bullet)

        n_kpis = min(len(kpis), 4)
        if n_kpis > 0:
            card_w = min(2.8, 11.0 / n_kpis - 0.3)
            card_gap = (11.0 - n_kpis * card_w) / (n_kpis + 1)
            for i, (label, value) in enumerate(kpis[:4]):
                cx = 1.0 + card_gap * (i + 1) + card_w * i
                cy = 2.0

                # Card background
                rect = mpatches.FancyBboxPatch(
                    (cx, cy), card_w, 1.5,
                    boxstyle="round,pad=0.15",
                    facecolor=t.mpl_bg_light, edgecolor=t.mpl_accent,
                    linewidth=1.5,
                )
                ax.add_patch(rect)

                # Accent top strip on card
                strip = mpatches.Rectangle(
                    (cx + 0.1, cy), card_w - 0.2, 0.05,
                    facecolor=t.mpl_accent, edgecolor="none", zorder=3,
                )
                ax.add_patch(strip)

                ax.text(
                    cx + card_w / 2, cy + 0.55,
                    value[:20], fontsize=14, fontweight="bold",
                    color=t.mpl_accent, ha="center", va="center",
                )
                ax.text(
                    cx + card_w / 2, cy + 1.1,
                    label[:20], fontsize=8, color=t.mpl_text_muted,
                    ha="center", va="center", fontweight="bold",
                )

        y_start = 4.2
        for i, finding in enumerate(findings[:4]):
            display = textwrap.fill(finding, width=100)
            ax.text(
                1.0, y_start + i * 0.65,
                "\u25cf",
                fontsize=6, color=t.mpl_accent,
                ha="left", va="top",
            )
            ax.text(
                1.4, y_start + i * 0.65,
                display,
                fontsize=10, color=t.mpl_text_dark, ha="left", va="top",
                fontfamily=t.body_font,
            )

        if content.key_insight:
            self._add_insight_bar(ax, content.key_insight)

        self._add_footer_accent_line(ax)
        self._add_footer(ax, plan.id)
        return self._fig_to_bytes(fig)

    # ── Section Divider Slide ───────────────────────────────

    def _render_section_divider(self, plan: SlidePlan, content: SlideContent) -> bytes:
        t = self._theme
        fig, ax = self._new_gradient_figure()

        white = (1.0, 1.0, 1.0)

        # Left accent bar (shorter, decorative)
        rect = mpatches.Rectangle(
            (0.8, 2.0), 0.06, 3.5,
            facecolor=t.mpl_accent, edgecolor="none", zorder=2,
        )
        ax.add_patch(rect)

        # Section number label
        ax.text(
            1.2, 2.2, f"SECTION {plan.id}",
            fontsize=10, fontweight="bold", color=t.mpl_accent,
            ha="left", va="top",
            fontfamily=t.heading_font,
        )

        # Section title (large, left-aligned)
        ax.text(
            1.2, 2.9, content.title,
            fontsize=28, fontweight="bold", color=white,
            ha="left", va="top", wrap=True,
            fontfamily=t.heading_font,
        )

        # Optional subtitle
        if content.key_insight:
            ax.text(
                1.2, 4.8, content.key_insight,
                fontsize=12, color=white,
                ha="left", va="top",
                fontfamily=t.body_font,
            )

        # Bottom accent strip
        rect = mpatches.Rectangle(
            (0, FIG_H - 0.12), FIG_W, 0.12,
            facecolor=t.mpl_accent, edgecolor="none", zorder=2,
        )
        ax.add_patch(rect)

        return self._fig_to_bytes(fig)

    # ── Closing Slide ───────────────────────────────────────

    def _render_closing(self, plan: SlidePlan, content: SlideContent) -> bytes:
        t = self._theme
        fig, ax = self._new_gradient_figure()

        white = (1.0, 1.0, 1.0)

        # Top accent bar
        rect = mpatches.Rectangle(
            (0, 0), FIG_W, 0.06,
            facecolor=t.mpl_accent, edgecolor="none", zorder=2,
        )
        ax.add_patch(rect)

        # Title
        title_text = content.title if content.title else "Thank You"
        ax.text(
            FIG_W / 2, 2.8, title_text,
            fontsize=32, fontweight="bold", color=white,
            ha="center", va="center", wrap=True,
            fontfamily=t.heading_font,
        )

        # Accent divider
        ax.plot(
            [FIG_W / 2 - 1.5, FIG_W / 2 + 1.5], [3.9, 3.9],
            color=t.mpl_accent, linewidth=4, solid_capstyle="round",
        )

        # Subtitle / contact info
        if content.key_insight:
            ax.text(
                FIG_W / 2, 4.5, content.key_insight,
                fontsize=14, color=white,
                ha="center", va="center",
                fontfamily=t.body_font,
            )

        # Bottom accent strip
        rect = mpatches.Rectangle(
            (0, FIG_H - 0.12), FIG_W, 0.12,
            facecolor=t.mpl_accent, edgecolor="none", zorder=2,
        )
        ax.add_patch(rect)

        return self._fig_to_bytes(fig)
