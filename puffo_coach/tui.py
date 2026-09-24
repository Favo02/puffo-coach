"""Textual TUI for Puffo Coach."""

from __future__ import annotations

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
    Checkbox,
    Collapsible,
    Footer,
    Header,
    Input,
    Label,
    Select,
)

from puffo_coach.models import CategoryConfig
from puffo_coach.pipeline import (
    DATE_PRESETS,
    DEFAULT_HEALTH_HOURS,
    PRIMARY_SPORT_TYPES,
    VALID_HEALTH_HOURS,
    PipelineResult,
    get_date_preset,
    run_pipeline,
)

PRIMARY_SPORTS: list[tuple[str, str]] = [
    ("Soccer", "soccer"),
    ("Volleyball", "volleyball"),
    ("Beach Volleyball", "beach_volleyball"),
    ("Workout", "workout"),
    ("Hike", "hike"),
    ("Run", "run"),
    ("Ride", "ride"),
]


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
    """Clean, focused Textual application for Puffo Coach."""

    TITLE = "Puffo Coach"
    SUB_TITLE = "Context Builder for LLMs"
    ENABLE_COMMAND_PALETTE = False

    BINDINGS = [
        Binding("g", "generate_context", "Generate (g)", priority=True),
        Binding("c", "copy_context", "Copy (c)"),
        Binding("s", "save_context", "Save (s)"),
        Binding("d", "toggle_dark", "Dark (d)"),
        Binding("q", "quit", "Quit (q)"),
    ]

    DEFAULT_CSS = """
    Screen {
        background: $surface;
    }

    #status_bar {
        height: 3;
        dock: top;
        padding: 0 1;
        background: $panel;
        border-bottom: heavy $accent;
        layout: horizontal;
        align-vertical: middle;
    }

    #footer_stats {
        text-style: bold;
        color: $text;
        width: 1fr;
    }

    #settings_scroll {
        height: 1fr;
        padding: 0 1;
    }

    .section_heading {
        text-style: bold;
        color: $accent;
        margin-top: 1;
        margin-bottom: 0;
    }

    .field_label {
        color: $text-muted;
        margin-top: 0;
        margin-bottom: 0;
    }

    .row {
        height: auto;
        layout: horizontal;
        margin-top: 0;
        margin-bottom: 0;
    }

    .half_col {
        width: 1fr;
        height: auto;
        margin-right: 1;
    }

    .third_col {
        width: 1fr;
        height: auto;
        margin-right: 1;
    }

    .grid_4col {
        layout: grid;
        grid-size: 4;
        grid-gutter: 0;
        height: auto;
    }

    Collapsible {
        padding: 0;
        margin-top: 1;
        margin-bottom: 0;
        border: round $primary-darken-2;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.last_result: PipelineResult | None = None
        self._programmatic_widgets: set[str] = set()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)

        # Prominent status bar
        with Horizontal(id="status_bar"):
            yield Label("● Status: Ready (press 'g' to generate context)", id="footer_stats")

        # Main settings container
        with VerticalScroll(id="settings_scroll"):
            # ── Date Range ────────────────────────────────────────────
            yield Label("Date Range", classes="section_heading")
            start_d, end_d = get_date_preset("last_7d")
            preset_options = [(label, key) for key, label in DATE_PRESETS] + [("Custom", "custom")]

            with Horizontal(classes="row"):
                with Vertical(classes="third_col"):
                    yield Label("Preset", classes="field_label")
                    yield Select(preset_options, value="last_7d", id="sel_preset", allow_blank=False)
                with Vertical(classes="third_col"):
                    yield Label("From", classes="field_label")
                    yield Input(value=str(start_d), id="inp_from_date", placeholder="YYYY-MM-DD")
                with Vertical(classes="third_col"):
                    yield Label("To", classes="field_label")
                    yield Input(value=str(end_d), id="inp_to_date", placeholder="YYYY-MM-DD")

            # ── General Settings ──────────────────────────────────────
            yield Label("General Settings", classes="section_heading")
            with Horizontal(classes="row"):
                with Vertical(classes="half_col"):
                    yield Label("Output File Path (optional)", classes="field_label")
                    yield Input(placeholder="context_from_...md (blank for auto-name)", id="inp_output_path")

            # ── Data Sources ──────────────────────────────────────────
            yield Label("Data Sources", classes="section_heading")

            # Meals (TimeTagger)
            with Collapsible(title="Meals (TimeTagger)", id="col_meals", collapsed=False):
                yield Checkbox("Enable Meals (all tracked meals)", value=True, id="chk_meals_enabled")

            # Activities (Strava)
            with Collapsible(title="Activities (Strava)", id="col_activities", collapsed=False):
                with Horizontal(classes="row"):
                    yield Checkbox("Enable Activities", value=True, id="chk_activities_enabled")
                    yield Checkbox("All Sport Types", value=True, id="chk_activities_all")
                with Container(classes="grid_4col", id="cnt_activities_types"):
                    for label, slug in PRIMARY_SPORTS:
                        yield Checkbox(label, value=True, id=f"chk_sport_{slug}")
                yield Input(placeholder="Custom sports (e.g. swim, walk)", id="inp_custom_sports")

            # Health Vitals (ZeppBridge)
            with Collapsible(title="Health Vitals & Sleep (ZeppBridge)", id="col_health", collapsed=False):
                with Horizontal(classes="row"):
                    yield Checkbox("Enable Health Vitals & Sleep", value=True, id="chk_health_enabled")
                    with Vertical(classes="half_col"):
                        yield Label("Detail (HR/HRV bucket size)", classes="field_label")
                        bucket_options = [
                            (f"{h}h/bucket ({24 // h} entries/day)", h) for h in VALID_HEALTH_HOURS
                        ]
                        yield Select(
                            bucket_options,
                            value=DEFAULT_HEALTH_HOURS,
                            id="sel_health_detail",
                            allow_blank=False,
                        )

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

    def on_input_changed(self, event: Input.Changed) -> None:
        """Switch preset to custom if user manually modifies date inputs."""
        widget_id = event.input.id or ""
        if widget_id in self._programmatic_widgets:
            self._programmatic_widgets.remove(widget_id)
            return

        if widget_id in ("inp_from_date", "inp_to_date"):
            self._set_select_programmatic("sel_preset", "custom")

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle checkboxes logic for activities sport types."""
        chk_id = event.checkbox.id or ""
        if chk_id in self._programmatic_widgets:
            self._programmatic_widgets.remove(chk_id)
            return

        # Activities all toggle
        if chk_id == "chk_activities_all":
            if event.value:
                for _, slug in PRIMARY_SPORTS:
                    self._set_checkbox_programmatic(f"chk_sport_{slug}", True)

        elif chk_id.startswith("chk_sport_"):
            all_checked = all(
                self.query_one(f"#chk_sport_{slug}", Checkbox).value
                for _, slug in PRIMARY_SPORTS
            )
            self._set_checkbox_programmatic("chk_activities_all", all_checked)

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

        # ── Meals ─────────────────────────────────────────────────────
        meals_enabled = self.query_one("#chk_meals_enabled", Checkbox).value
        meals_cfg = CategoryConfig(enabled=meals_enabled)

        # ── Activities ────────────────────────────────────────────────
        act_enabled = self.query_one("#chk_activities_enabled", Checkbox).value
        act_filter: list[str] = []
        if not self.query_one("#chk_activities_all", Checkbox).value:
            for label, slug in PRIMARY_SPORTS:
                if self.query_one(f"#chk_sport_{slug}", Checkbox).value:
                    act_filter.append(label.lower())
            custom_sports = self.query_one("#inp_custom_sports", Input).value.strip()
            if custom_sports:
                act_filter.extend([s.strip().lower() for s in custom_sports.split(",") if s.strip()])

        activities_cfg = CategoryConfig(
            enabled=act_enabled,
            filter=act_filter,
        )

        # ── Health ────────────────────────────────────────────────────
        health_enabled = self.query_one("#chk_health_enabled", Checkbox).value
        health_detail = int(self.query_one("#sel_health_detail", Select).value)

        health_cfg = CategoryConfig(
            enabled=health_enabled,
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

        self._update_progress("Starting context generation…")
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

    def _update_progress(self, msg: str) -> None:
        """Update progress text in the actions bar."""
        self.query_one("#footer_stats", Label).update(f"⏳ {msg}")

    def _on_generation_success(
        self, result: PipelineResult, from_date: date, to_date: date
    ) -> None:
        """Update state with generated context."""
        self.last_result = result
        stats = result.stats
        stats_msg = (
            f"✓ Done ({from_date} → {to_date} | "
            f"Meals: {stats.meals_count} | "
            f"Activities: {stats.activities_count} | "
            f"Sleep: {stats.sleep_sessions_count} | "
            f"Daily Vitals: {stats.daily_metrics_count} | "
            f"Chars: {len(result.markdown):,})"
        )
        self.query_one("#footer_stats", Label).update(stats_msg)
        self.notify("Context generated successfully. Press 'c' to copy or 's' to save.", severity="information")

    def _on_generation_error(self, error_msg: str) -> None:
        """Display error status."""
        self.query_one("#footer_stats", Label).update(f"✗ Error: {error_msg}")
        self.notify(f"Generation failed: {error_msg}", severity="error")

    def action_copy_context(self) -> None:
        """Copy the generated markdown to clipboard."""
        if not self.last_result or not self.last_result.markdown:
            self.notify("No context generated yet. Press 'g' first.", severity="warning")
            return

        text = self.last_result.markdown
        copied = copy_text_to_clipboard(text, app=self)
        if copied:
            self.notify(f"Copied {len(text):,} characters to clipboard.", severity="information")
        else:
            self.notify("Unable to access clipboard.", severity="warning")

    def action_save_context(self) -> None:
        """Save the generated markdown to disk."""
        if not self.last_result or not self.last_result.markdown:
            self.notify("No context generated yet. Press 'g' first.", severity="warning")
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
