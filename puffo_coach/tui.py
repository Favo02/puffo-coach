"""Textual TUI for Puffo Coach."""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Any

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Checkbox,
    Collapsible,
    Footer,
    Header,
    Input,
    Label,
    LoadingIndicator,
    Markdown,
    Select,
    Static,
)

from puffo_coach.models import CategoryConfig
from puffo_coach.pipeline import (
    ALL_KNOWN_METRICS,
    ALL_MEAL_TYPES,
    COMMON_SPORT_TYPES,
    DATE_PRESETS,
    DETAIL_LEVELS,
    HEALTH_METRICS_CORE,
    HEALTH_METRICS_HIGH,
    PipelineResult,
    get_date_preset,
    run_pipeline,
)


def copy_text_to_clipboard(text: str, app: App | None = None) -> bool:
    """Copy text to system clipboard and terminal via OSC 52."""
    copied = False
    if app is not None:
        try:
            app.copy_to_clipboard(text)
            copied = True
        except Exception:
            pass

    try:
        if shutil.which("wl-copy"):
            subprocess.run(["wl-copy"], input=text.encode("utf-8"), check=True, timeout=2)
            copied = True
        elif shutil.which("xclip"):
            subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode("utf-8"), check=True, timeout=2)
            copied = True
        elif shutil.which("xsel"):
            subprocess.run(["xsel", "--clipboard", "--input"], input=text.encode("utf-8"), check=True, timeout=2)
            copied = True
    except Exception:
        pass

    return copied


class PuffoCoachApp(App):
    """Main Textual application for Puffo Coach."""

    TITLE = "Puffo Coach"
    SUB_TITLE = "Health & Fitness Context Builder for LLMs"

    BINDINGS = [
        Binding("g", "generate_context", "Generate Context", priority=True),
        Binding("c", "copy_context", "Copy to Clipboard"),
        Binding("s", "save_context", "Save to File"),
        Binding("d", "toggle_dark", "Toggle Dark"),
        Binding("q", "quit", "Quit"),
    ]

    DEFAULT_CSS = """
    Screen {
        layout: horizontal;
        background: $surface;
    }

    #sidebar {
        width: 52;
        height: 100%;
        border-right: heavy $primary-background;
        padding: 0 1;
        background: $surface-darken-1;
    }

    #main_content {
        width: 1fr;
        height: 100%;
        padding: 1;
        layout: vertical;
    }

    #actions_bar {
        height: auto;
        margin-bottom: 1;
        align: left middle;
    }

    #actions_bar Button {
        margin-right: 1;
    }

    .section_heading {
        text-style: bold;
        color: $accent;
        margin-top: 1;
        margin-bottom: 0;
    }

    .field_label {
        color: $text-muted;
        margin-top: 1;
    }

    .row {
        height: auto;
        layout: horizontal;
    }

    .half_col {
        width: 1fr;
    }

    .grid_2col {
        layout: grid;
        grid-size: 2;
        grid-gutter: 0;
        height: auto;
    }

    Collapsible {
        padding: 0;
        margin-top: 1;
        border: round $primary-darken-2;
    }

    #preview_container {
        height: 1fr;
        border: solid $primary;
        background: $background;
        padding: 1;
    }

    #welcome_box {
        padding: 1;
        color: $text;
    }

    #status_box {
        padding: 1;
        color: $accent;
    }

    #error_box {
        padding: 1;
        color: $error;
        border: solid $error;
        background: $error-darken-3;
    }

    #footer_stats {
        height: 1;
        color: $text-muted;
        padding: 0 1;
        margin-top: 1;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.last_result: PipelineResult | None = None
        self._programmatic_widgets: set[str] = set()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal():
            # Left sidebar: Configuration
            with VerticalScroll(id="sidebar"):
                yield Label("📅 Date Range", classes="section_heading")
                preset_options = [(label, key) for key, label in DATE_PRESETS] + [("Custom", "custom")]
                yield Select(preset_options, value="last_7d", id="sel_preset", allow_blank=False)

                start_d, end_d = get_date_preset("last_7d")
                with Horizontal(classes="row"):
                    with Vertical(classes="half_col"):
                        yield Label("From", classes="field_label")
                        yield Input(value=str(start_d), id="inp_from_date", placeholder="YYYY-MM-DD")
                    with Vertical(classes="half_col"):
                        yield Label("To", classes="field_label")
                        yield Input(value=str(end_d), id="inp_to_date", placeholder="YYYY-MM-DD")

                yield Label("⚙️ Global Detail Level", classes="section_heading")
                detail_options = [(lvl.capitalize(), lvl) for lvl in DETAIL_LEVELS]
                yield Select(detail_options, value="medium", id="sel_global_detail", allow_blank=False)

                yield Label("📦 Data Sources", classes="section_heading")

                # ── Meals Collapsible ──────────────────────────────────
                with Collapsible(title="🍽️ Meals (TimeTagger)", id="col_meals", collapsed=False):
                    yield Checkbox("Enable Meals", value=True, id="chk_meals_enabled")
                    yield Label("Meals Detail Override", classes="field_label")
                    meals_detail_opts = [("Inherit (Global)", "inherit")] + detail_options
                    yield Select(meals_detail_opts, value="inherit", id="sel_meals_detail", allow_blank=False)

                    yield Label("Meal Types", classes="field_label")
                    yield Checkbox("All Meal Types", value=True, id="chk_meals_all")
                    with Container(classes="grid_2col", id="cnt_meals_types"):
                        yield Checkbox("Colazione", value=True, id="chk_meal_colazione")
                        yield Checkbox("Pranzo", value=True, id="chk_meal_pranzo")
                        yield Checkbox("Cena", value=True, id="chk_meal_cena")
                        yield Checkbox("Merenda", value=True, id="chk_meal_merenda")

                # ── Activities Collapsible ──────────────────────────────
                with Collapsible(title="🏃 Activities (Strava)", id="col_activities", collapsed=False):
                    yield Checkbox("Enable Activities", value=True, id="chk_activities_enabled")
                    yield Label("Activities Detail Override", classes="field_label")
                    act_detail_opts = [("Inherit (Global)", "inherit")] + detail_options
                    yield Select(act_detail_opts, value="inherit", id="sel_activities_detail", allow_blank=False)

                    yield Label("Sport Types", classes="field_label")
                    yield Checkbox("All Sport Types", value=True, id="chk_activities_all")
                    with Container(classes="grid_2col", id="cnt_activities_types"):
                        yield Checkbox("Ride", value=True, id="chk_sport_ride")
                        yield Checkbox("Run", value=True, id="chk_sport_run")
                        yield Checkbox("Hike", value=True, id="chk_sport_hike")
                        yield Checkbox("Walk", value=True, id="chk_sport_walk")
                        yield Checkbox("Swim", value=True, id="chk_sport_swim")
                        yield Checkbox("Workout", value=True, id="chk_sport_workout")
                    yield Input(placeholder="Custom sports (e.g. soccer, virtualride)", id="inp_custom_sports")

                # ── Health Collapsible ──────────────────────────────────
                with Collapsible(title="❤️ Health Vitals (ZeppBridge)", id="col_health", collapsed=False):
                    yield Checkbox("Enable Health Vitals", value=True, id="chk_health_enabled")
                    yield Label("Health Detail Override", classes="field_label")
                    health_detail_opts = [("Inherit (Global)", "inherit")] + detail_options
                    yield Select(health_detail_opts, value="inherit", id="sel_health_detail", allow_blank=False)

                    yield Label("Metrics Customization", classes="field_label")
                    yield Checkbox("Use defaults for detail level", value=True, id="chk_health_defaults")
                    yield Button("↺ Reset to Detail Defaults", id="btn_reset_health_metrics")

                    yield Label("Core Vitals", classes="field_label")
                    with Container(classes="grid_2col", id="cnt_health_core"):
                        for metric in HEALTH_METRICS_CORE:
                            yield Checkbox(metric, value=True, id=f"chk_metric_{metric}")

                    yield Label("Advanced Vitals", classes="field_label")
                    with Container(classes="grid_2col", id="cnt_health_adv"):
                        adv_metrics = [m for m in HEALTH_METRICS_HIGH if m not in HEALTH_METRICS_CORE]
                        for metric in adv_metrics:
                            yield Checkbox(metric, value=False, id=f"chk_metric_{metric}")

                    yield Label("Additional Vitals", classes="field_label")
                    with Container(classes="grid_2col", id="cnt_health_extra"):
                        extra_metrics = [m for m in ALL_KNOWN_METRICS if m not in HEALTH_METRICS_HIGH]
                        for metric in extra_metrics:
                            yield Checkbox(metric, value=False, id=f"chk_metric_{metric}")

                    yield Input(placeholder="Additional metrics (e.g. pai_total, afib_readiness)", id="inp_custom_metrics")

                # ── Output file ─────────────────────────────────────────
                yield Label("📁 Output File", classes="section_heading")
                yield Input(placeholder="context_from_...md (blank for auto-name)", id="inp_output_path")

            # Right main panel: Actions & Markdown Output Preview
            with Vertical(id="main_content"):
                with Horizontal(id="actions_bar"):
                    yield Button("⚡ Generate Context (g)", id="btn_generate", variant="primary")
                    yield Button("📋 Copy to Clipboard (c)", id="btn_copy", variant="default")
                    yield Button("💾 Save to File (s)", id="btn_save", variant="success")

                with VerticalScroll(id="preview_container"):
                    yield Static(
                        "### 👋 Welcome to Puffo Coach\n\n"
                        "Configure your date range and data sources on the left panel, "
                        "then click **Generate Context** or press `g`.\n\n"
                        "Once generated, preview the rendered XML/Markdown here and copy or save directly.",
                        id="welcome_box",
                    )

                yield Label("Status: Ready", id="footer_stats")

        yield Footer()

    # ── Programmatic Control Helpers ──────────────────────────────────

    def _set_checkbox_programmatic(self, widget_id: str, value: bool) -> None:
        """Update a checkbox without triggering user-interaction cascading."""
        try:
            chk = self.query_one(f"#{widget_id}", Checkbox)
            if chk.value != value:
                self._programmatic_widgets.add(widget_id)
                chk.value = value
        except Exception:
            pass

    def _set_input_programmatic(self, widget_id: str, value: str) -> None:
        """Update an input without triggering user-interaction cascading."""
        try:
            inp = self.query_one(f"#{widget_id}", Input)
            if inp.value != value:
                self._programmatic_widgets.add(widget_id)
                inp.value = value
        except Exception:
            pass

    def _set_select_programmatic(self, widget_id: str, value: Any) -> None:
        """Update a select without triggering user-interaction cascading."""
        try:
            sel = self.query_one(f"#{widget_id}", Select)
            if sel.value != value:
                self._programmatic_widgets.add(widget_id)
                sel.value = value
        except Exception:
            pass

    # ── Reactive Handlers ─────────────────────────────────────────────

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle dropdown selection changes."""
        widget_id = event.select.id or ""
        if widget_id in self._programmatic_widgets:
            self._programmatic_widgets.remove(widget_id)
            return

        if widget_id == "sel_preset":
            preset_key = str(event.value)
            if preset_key != "custom":
                start_d, end_d = get_date_preset(preset_key)
                self._set_input_programmatic("inp_from_date", str(start_d))
                self._set_input_programmatic("inp_to_date", str(end_d))

        elif widget_id in ("sel_global_detail", "sel_health_detail"):
            # Update health default metrics if default mode is active
            chk_defaults = self.query_one("#chk_health_defaults", Checkbox)
            if chk_defaults.value:
                self._apply_health_defaults_for_current_detail()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Switch preset to custom if user manually modifies date inputs."""
        widget_id = event.input.id or ""
        if widget_id in self._programmatic_widgets:
            self._programmatic_widgets.remove(widget_id)
            return

        if widget_id in ("inp_from_date", "inp_to_date"):
            self._set_select_programmatic("sel_preset", "custom")

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle checkboxes logic for meals, activities, and health vitals."""
        chk_id = event.checkbox.id or ""
        if chk_id in self._programmatic_widgets:
            self._programmatic_widgets.remove(chk_id)
            return

        # Meals all toggle
        if chk_id == "chk_meals_all":
            for meal_type in ALL_MEAL_TYPES:
                self._set_checkbox_programmatic(f"chk_meal_{meal_type}", event.value)

        elif chk_id.startswith("chk_meal_"):
            all_checked = all(self.query_one(f"#chk_meal_{m}", Checkbox).value for m in ALL_MEAL_TYPES)
            self._set_checkbox_programmatic("chk_meals_all", all_checked)

        # Activities all toggle
        elif chk_id == "chk_activities_all":
            for sport in ("ride", "run", "hike", "walk", "swim", "workout"):
                self._set_checkbox_programmatic(f"chk_sport_{sport}", event.value)

        elif chk_id.startswith("chk_sport_"):
            all_checked = all(
                self.query_one(f"#chk_sport_{s}", Checkbox).value
                for s in ("ride", "run", "hike", "walk", "swim", "workout")
            )
            self._set_checkbox_programmatic("chk_activities_all", all_checked)

        # Health metrics customization
        elif chk_id == "chk_health_defaults":
            if event.value:
                self._apply_health_defaults_for_current_detail()

        elif chk_id.startswith("chk_metric_"):
            # User manually changed a metric -> untick 'use defaults'
            self._set_checkbox_programmatic("chk_health_defaults", False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        if event.button.id == "btn_generate":
            self.action_generate_context()
        elif event.button.id == "btn_copy":
            self.action_copy_context()
        elif event.button.id == "btn_save":
            self.action_save_context()
        elif event.button.id == "btn_reset_health_metrics":
            self._set_checkbox_programmatic("chk_health_defaults", True)
            self._apply_health_defaults_for_current_detail()
            self.notify("Health metrics reset to defaults.", severity="information")

    # ── Detail & Metrics Helpers ──────────────────────────────────────

    def _get_effective_health_detail(self) -> str:
        """Return the effective health detail level."""
        h_detail = str(self.query_one("#sel_health_detail", Select).value)
        if h_detail != "inherit":
            return h_detail
        return str(self.query_one("#sel_global_detail", Select).value)

    def _apply_health_defaults_for_current_detail(self) -> None:
        """Sync metric checkboxes with the current effective health detail level."""
        eff_detail = self._get_effective_health_detail()
        defaults = HEALTH_METRICS_HIGH if eff_detail == "high" else HEALTH_METRICS_CORE

        for metric in ALL_KNOWN_METRICS:
            self._set_checkbox_programmatic(f"chk_metric_{metric}", metric in defaults)

    # ── Build Configuration ───────────────────────────────────────────

    def _build_configs(self) -> tuple[date, date, dict[str, CategoryConfig]]:
        """Validate input fields and build pipeline configurations."""
        from_raw = self.query_one("#inp_from_date", Input).value.strip()
        to_raw = self.query_one("#inp_to_date", Input).value.strip()

        try:
            from_date = datetime.strptime(from_raw, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(f"Invalid From Date: '{from_raw}'. Expected YYYY-MM-DD.")

        try:
            to_date = datetime.strptime(to_raw, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(f"Invalid To Date: '{to_raw}'. Expected YYYY-MM-DD.")

        if from_date > to_date:
            raise ValueError("From Date must be earlier than or equal to To Date.")

        global_detail = str(self.query_one("#sel_global_detail", Select).value)

        # ── Meals ─────────────────────────────────────────────────────
        meals_enabled = self.query_one("#chk_meals_enabled", Checkbox).value
        meals_detail_raw = str(self.query_one("#sel_meals_detail", Select).value)
        meals_detail = global_detail if meals_detail_raw == "inherit" else meals_detail_raw

        meals_filter: list[str] = []
        if not self.query_one("#chk_meals_all", Checkbox).value:
            meals_filter = [
                m for m in ALL_MEAL_TYPES
                if self.query_one(f"#chk_meal_{m}", Checkbox).value
            ]

        meals_cfg = CategoryConfig(
            enabled=meals_enabled,
            filter=meals_filter,
            detail_level=meals_detail,
        )

        # ── Activities ────────────────────────────────────────────────
        act_enabled = self.query_one("#chk_activities_enabled", Checkbox).value
        act_detail_raw = str(self.query_one("#sel_activities_detail", Select).value)
        act_detail = global_detail if act_detail_raw == "inherit" else act_detail_raw

        act_filter: list[str] = []
        if not self.query_one("#chk_activities_all", Checkbox).value:
            for s in ("ride", "run", "hike", "walk", "swim", "workout"):
                if self.query_one(f"#chk_sport_{s}", Checkbox).value:
                    act_filter.append(s)
            custom_sports = self.query_one("#inp_custom_sports", Input).value.strip()
            if custom_sports:
                act_filter.extend([s.strip().lower() for s in custom_sports.split(",") if s.strip()])

        activities_cfg = CategoryConfig(
            enabled=act_enabled,
            filter=act_filter,
            detail_level=act_detail,
        )

        # ── Health ────────────────────────────────────────────────────
        health_enabled = self.query_one("#chk_health_enabled", Checkbox).value
        health_detail_raw = str(self.query_one("#sel_health_detail", Select).value)
        health_detail = global_detail if health_detail_raw == "inherit" else health_detail_raw

        health_filter: list[str] = []
        chk_defaults = self.query_one("#chk_health_defaults", Checkbox)
        if not chk_defaults.value:
            for metric in ALL_KNOWN_METRICS:
                chk = self.query(f"#chk_metric_{metric}")
                if chk and chk.first().value:
                    health_filter.append(metric)
            custom_metrics = self.query_one("#inp_custom_metrics", Input).value.strip()
            if custom_metrics:
                health_filter.extend([m.strip().lower() for m in custom_metrics.split(",") if m.strip()])
        else:
            # Curated defaults for detail level
            health_filter = list(
                HEALTH_METRICS_HIGH if health_detail == "high" else HEALTH_METRICS_CORE
            )

        health_cfg = CategoryConfig(
            enabled=health_enabled,
            filter=health_filter,
            detail_level=health_detail,
        )

        if not (meals_enabled or act_enabled or health_enabled):
            raise ValueError("Select at least one source (Meals, Activities, or Health).")

        return from_date, to_date, {
            "meals": meals_cfg,
            "activities": activities_cfg,
            "health": health_cfg,
        }

    # ── Actions & Background Worker ───────────────────────────────────

    def action_generate_context(self) -> None:
        """Trigger background context generation."""
        try:
            from_date, to_date, configs = self._build_configs()
        except ValueError as err:
            self.notify(str(err), title="Configuration Error", severity="error")
            return

        self._show_loading("Starting context generation…")
        self._run_pipeline_worker(from_date, to_date, configs)

    @work(exclusive=True, thread=True)
    def _run_pipeline_worker(
        self, from_date: date, to_date: date, configs: dict[str, CategoryConfig]
    ) -> None:
        """Run data fetching and markdown rendering in a background thread."""
        try:
            result = run_pipeline(
                from_date=from_date,
                to_date=to_date,
                configs=configs,
                progress_callback=lambda msg: self.call_from_thread(self._update_progress, msg),
            )
            self.call_from_thread(self._on_generation_success, result, from_date, to_date)
        except Exception as exc:
            self.call_from_thread(self._on_generation_error, str(exc))

    def _show_loading(self, initial_msg: str) -> None:
        """Display loading spinner and progress container."""
        container = self.query_one("#preview_container", VerticalScroll)
        container.remove_children()
        container.mount(
            LoadingIndicator(),
            Static(initial_msg, id="status_box"),
        )
        self.query_one("#footer_stats", Label).update("Status: ⏳ Fetching data…")

    def _update_progress(self, msg: str) -> None:
        """Update progress text in the loading container."""
        status_widget = self.query("#status_box")
        if status_widget:
            status_widget.first().update(f"⏳ {msg}")

    def _on_generation_success(
        self, result: PipelineResult, from_date: date, to_date: date
    ) -> None:
        """Render the generated markdown context in the preview container."""
        self.last_result = result
        container = self.query_one("#preview_container", VerticalScroll)
        container.remove_children()
        container.mount(Markdown(result.markdown, id="markdown_viewer"))

        stats = result.stats
        stats_msg = (
            f"✓ {from_date} → {to_date} | "
            f"Meals: {stats.meals_count} | "
            f"Activities: {stats.activities_count} | "
            f"Sleep: {stats.sleep_sessions_count} | "
            f"Daily Vitals: {stats.daily_metrics_count} | "
            f"Chars: {len(result.markdown):,}"
        )
        self.query_one("#footer_stats", Label).update(f"Status: {stats_msg}")
        self.notify("Context generated successfully!", severity="information")

    def _on_generation_error(self, error_msg: str) -> None:
        """Render error card in the preview container."""
        container = self.query_one("#preview_container", VerticalScroll)
        container.remove_children()
        container.mount(
            Static(
                f"### ❌ Error Generating Context\n\n```\n{error_msg}\n```\n\n"
                "Please check your credentials, network connection, or database path in `.env`.",
                id="error_box",
            )
        )
        self.query_one("#footer_stats", Label).update("Status: ❌ Error during generation")
        self.notify("Generation failed. See preview for details.", severity="error")

    def action_copy_context(self) -> None:
        """Copy the generated markdown to clipboard."""
        if not self.last_result or not self.last_result.markdown:
            self.notify("No context generated yet. Click 'Generate Context' first.", severity="warning")
            return

        text = self.last_result.markdown
        copied = copy_text_to_clipboard(text, app=self)
        if copied:
            self.notify(f"Copied {len(text):,} characters to clipboard!", severity="information")
        else:
            self.notify("Unable to access clipboard.", severity="warning")

    def action_save_context(self) -> None:
        """Save the generated markdown to disk."""
        if not self.last_result or not self.last_result.markdown:
            self.notify("No context generated yet. Click 'Generate Context' first.", severity="warning")
            return

        from_raw = self.query_one("#inp_from_date", Input).value.strip()
        to_raw = self.query_one("#inp_to_date", Input).value.strip()
        default_name = f"context_from_{from_raw}_to_{to_raw}.md"

        user_path_raw = self.query_one("#inp_output_path", Input).value.strip()
        if user_path_raw:
            target = Path(user_path_raw)
            if user_path_raw.endswith(("/", "\\")) or target.is_dir() or (target.suffix == "" and not target.exists()):
                target.mkdir(parents=True, exist_ok=True)
                out_path = target / default_name
            else:
                out_path = target
        else:
            out_path = Path.cwd() / default_name

        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(self.last_result.markdown, encoding="utf-8")
            self.notify(f"Saved to {out_path} ({len(self.last_result.markdown):,} chars)", severity="information")
        except Exception as exc:
            self.notify(f"Failed to save file: {exc}", severity="error")


def main() -> None:
    """Run the Puffo Coach Textual application."""
    app = PuffoCoachApp()
    app.run()


if __name__ == "__main__":
    main()
