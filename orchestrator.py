"""
orchestrator.py — Pipeline controller and state machine.
Manages the end-to-end flow from topic input to PPTX output.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from agents.critic_agent import CriticAgent
from agents.deep_research_agent import DeepResearchAgent
from agents.infographic_agent import InfographicAgent
from agents.layout_critic_agent import LayoutCriticAgent
from agents.layout_decider import LayoutDecider
from agents.research_agent import ResearchAgent
from agents.slide_content_agent import SlideContent, SlideContentAgent
from agents.slide_render_decider import SlideRenderDecider
from agents.storyline_agent import (
    ComparativeStorylineGenerator,
    FrameworkChoice,
    FrameworkSelectorAgent,
    StorylineAgent,
)
from config import Settings, get_settings
from engine.llm_provider import LLMProvider
from engine.pipeline_logger import PipelineLogger
from generators.nano_banana_pro import NanoBananaProIntegration
from generators.ppt_generator import InteractivePPTGenerator
from generators.themes import PresentationTheme, THEME_CORPORATE_BLUE
from models import (
    InfographicProposal,
    LayoutValidationResult,
    PipelineState,
    RenderDecision,
    ResearchFinding,
    SlidePlan,
    StorylineOutline,
)


class PipelineOrchestrator:
    """Orchestrates the full presentation generation pipeline.

    State machine: idle → researching → planning → generating → review → finalizing → done

    The orchestrator provides callback hooks for UI integration:
    - on_status_change: Called when pipeline status changes
    - on_outline_ready: Called when two outlines are ready for user selection
    - on_review_ready: Called when slide content is ready for user review
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        on_status_change: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._llm = LLMProvider(self._settings)
        self._log = PipelineLogger("Orchestrator")

        # Initialize all agents with shared LLM
        self._research_agent = ResearchAgent(llm=self._llm, settings=self._settings)
        self._deep_research = DeepResearchAgent(llm=self._llm, settings=self._settings)
        self._framework_selector = FrameworkSelectorAgent(
            llm=self._llm, settings=self._settings
        )
        self._storyline_agent = StorylineAgent(llm=self._llm, settings=self._settings)
        self._comparative_gen = ComparativeStorylineGenerator(
            llm=self._llm, settings=self._settings
        )
        self._layout_decider = LayoutDecider(llm=self._llm, settings=self._settings)
        self._content_agent = SlideContentAgent(llm=self._llm, settings=self._settings)
        self._critic = CriticAgent(llm=self._llm, settings=self._settings)
        self._infographic = InfographicAgent(llm=self._llm, settings=self._settings)
        self._layout_critic = LayoutCriticAgent(llm=self._llm, settings=self._settings)
        self._render_decider = SlideRenderDecider(
            llm=self._llm, settings=self._settings
        )
        self._imagen = NanoBananaProIntegration(settings=self._settings)
        self._ppt_gen = InteractivePPTGenerator()
        self._selected_theme: PresentationTheme = THEME_CORPORATE_BLUE

        # Pipeline state
        self.state = PipelineState()
        self._on_status_change = on_status_change

        # Intermediate results
        self._research_synthesis: str = ""
        self._framework_choices: List[FrameworkChoice] = []
        self._outline_a: Optional[StorylineOutline] = None
        self._outline_b: Optional[StorylineOutline] = None
        self._slide_contents: List[SlideContent] = []
        self._research_map: Dict[int, str] = {}
        self._infographic_proposals: List[InfographicProposal] = []
        self._render_decisions: List[RenderDecision] = []
        self._layout_results: List[LayoutValidationResult] = []

    def _set_status(self, status: str, step: str = "") -> None:
        """Update pipeline status and notify UI."""
        self.state.status = status
        self.state.current_step = step
        self._log.info(f"Pipeline status: {status} | {step}")
        if self._on_status_change:
            self._on_status_change(status, step)

    def set_theme(self, theme: PresentationTheme) -> None:
        """Set the visual theme for PPTX generation."""
        self._selected_theme = theme
        self._ppt_gen.theme = theme
        self._log.decision(f"Theme set: {theme.display_name}")

    @property
    def infographic_proposals(self) -> List[InfographicProposal]:
        return self._infographic_proposals

    @property
    def render_decisions(self) -> List[RenderDecision]:
        return self._render_decisions

    @property
    def slide_contents(self) -> List[SlideContent]:
        return self._slide_contents

    # ── Phase 1: Research ───────────────────────────────────

    def run_research(
        self,
        topic: str,
        num_subtopics: int = 6,
        focus_subtopics: Optional[List[str]] = None,
    ) -> List[ResearchFinding]:
        """Execute the research phase.

        Args:
            topic: Main presentation topic.
            num_subtopics: Number of subtopics to research.
            focus_subtopics: Specific subtopics to prioritize.

        Returns:
            List of ResearchFinding objects.
        """
        self._set_status("researching", "Decomposing topic and searching")
        self.state.topic = topic

        try:
            findings = self._research_agent.research_topic(
                topic=topic,
                num_subtopics=num_subtopics,
                focus_areas=focus_subtopics,
            )
            self.state.research_findings = findings

            # Synthesize for downstream use
            self._set_status("researching", "Synthesizing findings")
            self._research_synthesis = self._research_agent.synthesize(topic, findings)

            self._log.info(f"Research complete: {len(findings)} findings")
            return findings

        except Exception as e:
            self._set_status("error", f"Research failed: {e}")
            self.state.errors.append(str(e))
            raise

    # ── Phase 2: Framework Selection & Storyline ────────────

    def run_framework_selection(
        self,
        audience: str = "business executives",
    ) -> List[FrameworkChoice]:
        """Select top 2 frameworks for the topic.

        Returns:
            List of 2 FrameworkChoice objects.
        """
        self._set_status("planning", "Selecting narrative frameworks")

        try:
            choices = self._framework_selector.select(
                topic=self.state.topic,
                research_summary=self._research_synthesis[:3000],
                audience=audience,
            )
            self._framework_choices = choices
            return choices

        except Exception as e:
            self._set_status("error", f"Framework selection failed: {e}")
            self.state.errors.append(str(e))
            raise

    def run_comparative_outlines(
        self,
        target_slides: int = 12,
    ) -> Tuple[StorylineOutline, StorylineOutline]:
        """Generate two competing outlines based on selected frameworks.

        Args:
            target_slides: Target number of slides per outline.

        Returns:
            Tuple of (outline_a, outline_b).
        """
        self._set_status("planning", "Generating comparative outlines")

        if len(self._framework_choices) < 2:
            raise ValueError("Must run framework selection first")

        try:
            fa, fb = self._framework_choices[0], self._framework_choices[1]
            self._outline_a, self._outline_b = self._comparative_gen.generate(
                topic=self.state.topic,
                research_summary=self._research_synthesis[:4000],
                framework_a=fa.framework,
                angle_a=fa.narrative_angle,
                framework_b=fb.framework,
                angle_b=fb.narrative_angle,
                target_slides=target_slides,
            )
            return self._outline_a, self._outline_b

        except Exception as e:
            self._set_status("error", f"Outline generation failed: {e}")
            self.state.errors.append(str(e))
            raise

    def select_outline(self, choice: str) -> StorylineOutline:
        """User selects their preferred outline.

        Args:
            choice: 'a' or 'b'.

        Returns:
            The selected StorylineOutline.
        """
        if choice.lower() == "a" and self._outline_a:
            self.state.selected_outline = self._outline_a
        elif choice.lower() == "b" and self._outline_b:
            self.state.selected_outline = self._outline_b
        else:
            raise ValueError(f"Invalid choice: {choice}. Must be 'a' or 'b'.")

        self._log.decision(
            f"User selected outline {choice.upper()}: "
            f"{self.state.selected_outline.framework_name}"
        )
        return self.state.selected_outline

    # ── Phase 3: Content Generation ─────────────────────────

    def run_content_generation(self) -> List[SlideContent]:
        """Generate content for all slides in the selected outline.

        Returns:
            List of SlideContent objects.
        """
        if not self.state.selected_outline:
            raise ValueError("Must select an outline first")

        slides = self.state.selected_outline.slides
        self._set_status("generating", "Running deep research for data slides")

        try:
            # Step 1: Deep research for slides that need data
            deep_findings = self._deep_research.research_slides_batch(
                slides=slides,
                shared_context=self._research_synthesis[:2000],
            )
            # Build research map: slide_id → research text
            self._research_map = {}
            for finding in deep_findings:
                # Match by topic (slide title)
                for s in slides:
                    if s.title == finding.topic:
                        self._research_map[s.id] = finding.content
                        break

            # Fill in general research for slides without deep research
            for s in slides:
                if s.id not in self._research_map:
                    self._research_map[s.id] = self._research_synthesis[:2000]

            # Step 2: Layout confirmation (parallel)
            self._set_status("generating", "Confirming slide layouts")
            from concurrent.futures import ThreadPoolExecutor, as_completed

            def _decide_layout(s):
                return self._layout_decider.decide(
                    slide=s,
                    available_data=self._research_map.get(s.id, ""),
                )

            with ThreadPoolExecutor(max_workers=3) as executor:
                list(executor.map(_decide_layout, slides))

            # Step 3: Content generation
            self._set_status("generating", "Generating slide content")
            theme_desc = self._selected_theme.description if self._selected_theme else "Corporate Blue"
            self._slide_contents = self._content_agent.generate_all(
                slides=slides,
                research_map=self._research_map,
                theme_description=theme_desc,
            )

            return self._slide_contents

        except Exception as e:
            self._set_status("error", f"Content generation failed: {e}")
            self.state.errors.append(str(e))
            raise

    # ── Phase 4: Validation ─────────────────────────────────

    def run_validation(self) -> Dict[str, Any]:
        """Run CriticAgent validation on all generated content.

        Returns:
            Dict with 'slide_results' and 'has_critical_issues'.
        """
        self._set_status("review", "Validating content accuracy")

        try:
            slides_data = [
                {
                    "id": self.state.selected_outline.slides[i].id,
                    "title": content.title,
                    "content_bullets": content.content_bullets,
                    "key_insight": content.key_insight,
                    "chart_data": content.chart_data.model_dump()
                    if content.chart_data
                    else None,
                    "table_data": content.table_data.model_dump()
                    if content.table_data
                    else None,
                }
                for i, content in enumerate(self._slide_contents)
            ]

            results = self._critic.validate_all(
                slides_content=slides_data,
                research_map={k: v for k, v in self._research_map.items()},
            )

            has_critical = any(
                any(issue.severity == "critical" for issue in r.issues) for r in results
            )

            self._log.info(
                f"Validation complete: {len(results)} slides checked, "
                f"critical_issues={has_critical}"
            )

            return {
                "slide_results": [r.model_dump() for r in results],
                "has_critical_issues": has_critical,
            }

        except Exception as e:
            self._set_status("error", f"Validation failed: {e}")
            self.state.errors.append(str(e))
            raise

    # ── Phase 5: Infographic Enrichment ─────────────────────

    def run_infographic_evaluation(self) -> List[InfographicProposal]:
        """Evaluate slides for infographic enrichment.

        Returns:
            List of InfographicProposal objects.
        """
        self._set_status("generating", "Evaluating infographic opportunities")

        try:
            slides_data = [
                {
                    "id": self.state.selected_outline.slides[i].id,
                    "title": content.title,
                    "layout_type": self.state.selected_outline.slides[i].layout_type,
                    "content_bullets": content.content_bullets,
                    "chart_data": content.chart_data.model_dump()
                    if content.chart_data
                    else None,
                    "table_data": content.table_data.model_dump()
                    if content.table_data
                    else None,
                }
                for i, content in enumerate(self._slide_contents)
            ]

            self._infographic_proposals = self._infographic.evaluate_all_slides(
                slides_data
            )
            return self._infographic_proposals

        except Exception as e:
            self._log.warning(f"Infographic evaluation failed (non-critical): {e}")
            return []

    def run_infographic_generation(self) -> int:
        """Generate infographic images for slides where recommended.

        Must be called after run_infographic_evaluation().

        Returns:
            Number of infographics successfully generated.
        """
        if not self._infographic_proposals:
            self._log.info("No infographic proposals to generate")
            return 0

        if not self._imagen.is_available:
            self._log.warning("Imagen not available, skipping infographic generation")
            return 0

        self._set_status("generating", "Generating infographic images")

        generated_count = 0
        for proposal in self._infographic_proposals:
            if not proposal.infographic_recommended:
                continue
            if not proposal.generated_prompt:
                continue

            # Find the corresponding SlideContent
            slide_idx = None
            for i, slide in enumerate(self.state.selected_outline.slides):
                if slide.id == proposal.slide_number:
                    slide_idx = i
                    break

            if slide_idx is None or slide_idx >= len(self._slide_contents):
                continue

            content = self._slide_contents[slide_idx]

            # Skip slides that already have charts or tables
            if content.chart_data or content.table_data:
                self._log.info(
                    f"Skipping infographic for slide {proposal.slide_number} "
                    f"(already has chart/table)"
                )
                continue

            try:
                image_buf = self._imagen.generate_visual(
                    prompt=proposal.generated_prompt,
                    placement=proposal.placement,
                    theme=self._selected_theme,
                )
                if image_buf:
                    content.infographic_image = image_buf.read()
                    generated_count += 1
                    self._log.info(
                        f"Infographic generated for slide {proposal.slide_number}"
                    )
            except Exception as e:
                self._log.warning(
                    f"Infographic generation failed for slide "
                    f"{proposal.slide_number}: {e}"
                )

        # Also generate infographics for text_heavy_infographic slides
        if self.state.selected_outline:
            for i, slide in enumerate(self.state.selected_outline.slides):
                if slide.visual_type == "text_heavy_infographic" and i < len(
                    self._slide_contents
                ):
                    content = self._slide_contents[i]
                    if content.infographic_image:
                        continue  # Already has an image
                    prompt = content.infographic_prompt
                    if not prompt:
                        prompt = (
                            f"Professional business infographic about {content.title}: "
                            f"{content.key_insight}. Clean modern design, 16:9 widescreen format."
                        )
                    try:
                        image_buf = self._imagen.generate_visual(
                            prompt=prompt,
                            placement="full-slide",
                            theme=self._selected_theme,
                        )
                        if image_buf:
                            content.infographic_image = image_buf.read()
                            generated_count += 1
                            self._log.info(
                                f"Text-heavy infographic generated for slide {slide.id}"
                            )
                    except Exception as e:
                        self._log.warning(
                            f"Text-heavy infographic failed for slide {slide.id}: {e}"
                        )

        self._log.info(f"Infographic generation complete: {generated_count} images")
        return generated_count

    # ── Render Decisions (Deciding Agent) ─────────────────────

    def run_render_decisions(self) -> List[RenderDecision]:
        """Run the deciding agent on all slides in parallel.

        Determines which slides get full-image generation vs standard rendering.

        Returns:
            List of RenderDecision objects.
        """
        if not self.state.selected_outline or not self._slide_contents:
            raise ValueError("Must generate content before render decisions")

        self._set_status("generating", "Deciding slide render strategies")

        try:
            self._render_decisions = self._render_decider.decide_all(
                slides=self.state.selected_outline.slides,
                contents=self._slide_contents,
                theme=self._selected_theme,
            )

            image_count = sum(
                1 for d in self._render_decisions if d.render_mode == "image_generation"
            )
            self._log.info(
                f"Render decisions: {image_count} image slides, "
                f"{len(self._render_decisions) - image_count} standard"
            )
            return self._render_decisions

        except Exception as e:
            self._log.warning(f"Render decision failed (non-critical): {e}")
            return []

    def run_slide_image_generation(self) -> int:
        """Generate full-slide images for slides marked as image_generation.

        Must be called after run_render_decisions().

        Returns:
            Number of images successfully generated.
        """
        if not self._render_decisions:
            self._log.info("No render decisions to process")
            return 0

        if not self._imagen.is_available:
            self._log.warning(
                "Image generation not available, skipping full-slide images"
            )
            return 0

        self._set_status(
            "generating", "Generating full-slide images for text-heavy slides"
        )

        from concurrent.futures import ThreadPoolExecutor, as_completed

        image_decisions = [
            d
            for d in self._render_decisions
            if d.render_mode == "image_generation" and d.image_prompt
        ]

        if not image_decisions:
            self._log.info("No slides marked for image generation")
            return 0

        self._log.info(
            f"Generating full-slide images for {len(image_decisions)} text-heavy slides "
            f"(model: {self._imagen.GEMINI_IMAGE_MODEL})"
        )

        generated = 0

        def _generate_one(decision: RenderDecision):
            for i, slide in enumerate(self.state.selected_outline.slides):
                if slide.id == decision.slide_id:
                    self._log.info(
                        f"Calling Gemini image API for slide {decision.slide_id}: "
                        f"{slide.title[:50]}"
                    )
                    result = self._imagen.generate_visual(
                        prompt=decision.image_prompt,
                        placement="full-slide",
                        theme=self._selected_theme,
                    )
                    if result is None:
                        self._log.warning(
                            f"Gemini returned None for slide {decision.slide_id}"
                        )
                    return i, result
            return -1, None

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(_generate_one, d): d for d in image_decisions}
            for future in as_completed(futures):
                decision = futures[future]
                try:
                    idx, image_buf = future.result()
                    if idx >= 0 and image_buf and idx < len(self._slide_contents):
                        self._slide_contents[idx].full_slide_image = image_buf.read()
                        generated += 1
                        self._log.info(
                            f"Full-slide image generated for slide {decision.slide_id} "
                            f"({len(self._slide_contents[idx].full_slide_image) / 1024:.0f} KB)"
                        )
                    elif idx >= 0 and not image_buf:
                        self._log.warning(
                            f"No image returned for slide {decision.slide_id} — "
                            f"will fallback to standard bullet rendering"
                        )
                except Exception as e:
                    self._log.error(
                        f"Image generation FAILED for slide {decision.slide_id}: {e}"
                    )

        self._log.info(
            f"Full-slide image generation: {generated}/{len(image_decisions)} succeeded"
        )
        return generated

    def run_universal_refinement(self) -> int:
        """Refine ALL slides via nano banana pro image-to-image.

        Every slide (charts, tables, bullets, etc.) gets visual polish.
        The refinement prompt preserves all data exactly — only the surrounding
        design (colors, borders, backgrounds, typography) is enhanced.

        Slides that already have a full_slide_image (from text-to-image generation)
        are skipped since they are already AI-generated.

        Returns:
            Number of slides successfully refined.
        """
        if not self._imagen.is_available:
            self._log.info("Imagen not available, skipping universal refinement")
            return 0

        if not self.state.selected_outline or not self._slide_contents:
            return 0

        self._set_status("generating", "Polishing all slides with AI refinement")

        from concurrent.futures import ThreadPoolExecutor, as_completed
        from generators.slide_previewer import SlidePreviewRenderer
        from prompts.render_decision_prompts import SLIDE_REFINEMENT_PROMPT

        # Create a preview renderer with the current theme
        previewer = SlidePreviewRenderer(theme=self._selected_theme)
        previewer._total_slides = len(self.state.selected_outline.slides)
        previewer._topic = self.state.topic

        slides = self.state.selected_outline.slides
        theme = self._selected_theme

        # Identify slides that need refinement (all except those already refined)
        to_refine = []
        for i, content in enumerate(self._slide_contents):
            if i >= len(slides):
                break
            if content.full_slide_image:
                self._log.info(f"Slide {slides[i].id}: already has AI image, skipping")
                continue
            to_refine.append((i, slides[i], content))

        if not to_refine:
            self._log.info("All slides already have full images, no refinement needed")
            return 0

        self._log.info(
            f"Universal refinement: {len(to_refine)} slides to refine "
            f"(model: {self._imagen.GEMINI_IMAGE_MODEL})"
        )

        refined = 0

        def _refine_one(idx: int, slide, content):
            # Step 1: Render the slide to PNG via matplotlib previewer
            preview_bytes = previewer.render_slide(slide, content)

            # Step 2: Build the refinement prompt with theme colors
            prompt = SLIDE_REFINEMENT_PROMPT.format(
                primary_color=theme.primary_hex,
                accent_color=theme.accent_hex,
                bg_color=theme.bg_white_hex,
                text_color=theme.text_dark_hex,
                slide_title=content.title,
                slide_type=slide.layout_type,
                slide_num=idx + 1,
                total_slides=len(slides),
            )

            # Step 3: Send to nano banana pro for image-to-image refinement
            result = self._imagen.refine_slide(
                slide_image=preview_bytes,
                refinement_prompt=prompt,
            )
            return idx, result

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(_refine_one, i, s, c): (i, s) for i, s, c in to_refine
            }
            for future in as_completed(futures):
                idx, slide = futures[future]
                try:
                    result_idx, image_buf = future.result()
                    if image_buf and result_idx < len(self._slide_contents):
                        self._slide_contents[
                            result_idx
                        ].full_slide_image = image_buf.read()
                        refined += 1
                        self._log.info(
                            f"Slide {slide.id} refined "
                            f"({len(self._slide_contents[result_idx].full_slide_image) / 1024:.0f} KB)"
                        )
                    elif not image_buf:
                        self._log.warning(
                            f"Slide {slide.id}: refinement returned None, keeping original"
                        )
                except Exception as e:
                    self._log.warning(f"Refinement failed for slide {slide.id}: {e}")

        self._log.info(f"Universal refinement: {refined}/{len(to_refine)} succeeded")
        return refined

    def regenerate_single_slide(
        self,
        slide_index: int,
        custom_prompt: str = "",
    ) -> Optional[SlideContent]:
        """Regenerate content for a single slide, optionally with user instructions.

        Args:
            slide_index: Index into self._slide_contents.
            custom_prompt: Optional user instructions to guide regeneration.

        Returns:
            New SlideContent if successful, None on error.
        """
        if not self.state.selected_outline:
            self._log.warning("No outline selected")
            return None
        if slide_index < 0 or slide_index >= len(self._slide_contents):
            self._log.warning(f"Invalid slide index: {slide_index}")
            return None

        slide = self.state.selected_outline.slides[slide_index]
        old_content = self._slide_contents[slide_index]
        research_data = self._research_map.get(
            slide.id, self._research_synthesis[:2000]
        )

        if custom_prompt:
            research_data += f"\n\n**USER INSTRUCTIONS:** {custom_prompt}"

        try:
            new_content = self._content_agent.generate_content(slide, research_data)
            # Preserve existing infographic image if the new content doesn't have one
            if old_content.infographic_image and not new_content.infographic_image:
                new_content.infographic_image = old_content.infographic_image
            self._slide_contents[slide_index] = new_content
            self._log.info(f"Slide {slide.id} regenerated successfully")
            return new_content
        except Exception as e:
            self._log.error(f"Failed to regenerate slide {slide.id}: {e}")
            return None

    def regenerate_infographic(
        self,
        slide_number: int,
        new_prompt: str,
        placement: str = "full-slide",
    ) -> Optional[bytes]:
        """Regenerate an infographic for a specific slide with a new prompt.

        Used by the review UI when user edits the prompt.

        Args:
            slide_number: The slide ID.
            new_prompt: The updated generation prompt.
            placement: Infographic placement type.

        Returns:
            PNG image bytes if successful, None otherwise.
        """
        if not self._imagen.is_available:
            self._log.warning("Imagen not available")
            return None

        image_buf = self._imagen.generate_visual(
            prompt=new_prompt,
            placement=placement,
            theme=self._selected_theme,
        )
        if image_buf:
            image_bytes = image_buf.read()
            # Update the corresponding SlideContent
            for i, slide in enumerate(self.state.selected_outline.slides):
                if slide.id == slide_number and i < len(self._slide_contents):
                    self._slide_contents[i].infographic_image = image_bytes
                    break
            # Update the corresponding proposal prompt
            for proposal in self._infographic_proposals:
                if proposal.slide_number == slide_number:
                    proposal.generated_prompt = new_prompt
                    proposal.placement = placement
                    break
            return image_bytes
        return None

    # ── Layout Validation ────────────────────────────────────

    def run_layout_validation(self) -> List[LayoutValidationResult]:
        """Run layout critic on all slides.

        Should be called after content generation, before PPTX build.

        Returns:
            List of LayoutValidationResult objects.
        """
        if not self.state.selected_outline or not self._slide_contents:
            raise ValueError("Must generate content before layout validation")

        self._set_status("generating", "Validating slide layouts")

        try:
            self._layout_results = self._layout_critic.validate_all(
                slides=self.state.selected_outline.slides,
                contents=self._slide_contents,
            )

            invalid_count = sum(1 for r in self._layout_results if not r.is_valid)
            adjustment_count = sum(len(r.adjustments) for r in self._layout_results)
            density_warnings = sum(1 for r in self._layout_results if r.density_warning)

            self._log.info(
                f"Layout validation complete: "
                f"{invalid_count} invalid, "
                f"{adjustment_count} adjustments, "
                f"{density_warnings} density warnings"
            )

            return self._layout_results

        except Exception as e:
            self._log.warning(f"Layout validation failed (non-critical): {e}")
            return []

    # ── Phase 6: PPTX Generation ────────────────────────────

    def run_pptx_generation(self, output_filename: Optional[str] = None) -> Path:
        """Generate the final PPTX file.

        Args:
            output_filename: Custom filename for the output.

        Returns:
            Path to the generated PPTX file.
        """
        if not self.state.selected_outline or not self._slide_contents:
            raise ValueError("Must generate content before building PPTX")

        self._set_status("finalizing", "Building PowerPoint presentation")

        try:
            output_path = self._ppt_gen.create_presentation(
                topic=self.state.topic,
                slides=self.state.selected_outline.slides,
                contents=self._slide_contents,
                output_filename=output_filename,
            )

            # Upload to GCS if configured
            from utils.gcp_storage import get_storage_manager
            storage = get_storage_manager()
            if storage.enabled:
                gcs_path = f"presentations/{output_path.name}"
                gcs_uri = storage.upload_file(output_path, gcs_path, content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")
                if gcs_uri:
                    self.state.output_gcs_uri = gcs_uri
                    self._log.info(f"Presentation uploaded to GCS: {gcs_uri}")

            self.state.output_file = str(output_path)
            self._set_status("done", f"Presentation saved: {output_path.name}")
            return output_path

        except Exception as e:
            self._set_status("error", f"PPTX generation failed: {e}")
            self.state.errors.append(str(e))
            raise

    # ── Full Auto Pipeline ──────────────────────────────────

    def run_full_pipeline(
        self,
        topic: str,
        audience: str = "business executives",
        outline_choice: str = "a",
        num_subtopics: int = 6,
        output_filename: Optional[str] = None,
    ) -> Path:
        """Run the entire pipeline end-to-end (no human-in-the-loop).

        This is primarily for testing. The UI should call individual phases
        with approval steps in between.

        Args:
            topic: Presentation topic.
            audience: Target audience.
            outline_choice: 'a' or 'b' for auto-selection.
            num_subtopics: Number of subtopics.
            output_filename: Custom output filename.

        Returns:
            Path to the generated PPTX.
        """
        self._log.action("Full Pipeline", f"topic={topic[:60]}")

        # Phase 1: Research
        self.run_research(topic, num_subtopics)

        # Phase 2: Planning
        self.run_framework_selection(audience)
        self.run_comparative_outlines()
        self.select_outline(outline_choice)

        # Phase 3: Content
        self.run_content_generation()

        # Phase 4: Validation
        self.run_validation()

        # Phase 4b: Layout validation
        self.run_layout_validation()

        # Phase 5: Infographic evaluation + generation
        self.run_infographic_evaluation()
        self.run_infographic_generation()

        # Phase 6: Generate PPTX
        return self.run_pptx_generation(output_filename)
