"""Unit and integration tests for Textual TUI interface."""

import tempfile
import unittest
from datetime import date
from pathlib import Path

from puffo_coach.pipeline import PipelineResult, PipelineStats
from puffo_coach.tui import PRIMARY_SPORTS, PuffoCoachApp


class TestTuiApp(unittest.IsolatedAsyncioTestCase):
    async def test_initial_state_and_preset_selection(self) -> None:
        app = PuffoCoachApp()
        async with app.run_test() as pilot:
            inp_from = app.query_one("#inp_from_date")
            inp_to = app.query_one("#inp_to_date")
            self.assertTrue(len(inp_from.value) == 10)
            self.assertTrue(len(inp_to.value) == 10)

            # Change to 'today' preset
            app.query_one("#sel_preset").value = "today"
            await pilot.pause(0.1)
            today_str = str(date.today())
            self.assertEqual(inp_from.value, today_str)
            self.assertEqual(inp_to.value, today_str)

    async def test_manual_date_edit_switches_to_custom(self) -> None:
        app = PuffoCoachApp()
        async with app.run_test() as pilot:
            app.query_one("#inp_from_date").value = "2026-01-01"
            await pilot.pause(0.1)
            self.assertEqual(app.query_one("#sel_preset").value, "custom")

    async def test_meals_toggle(self) -> None:
        app = PuffoCoachApp()
        async with app.run_test() as pilot:
            _, _, cfgs = app._build_configs()
            self.assertTrue(cfgs["meals"].enabled)

            app.query_one("#chk_meals_enabled").value = False
            await pilot.pause(0.1)
            _, _, cfgs = app._build_configs()
            self.assertFalse(cfgs["meals"].enabled)

    async def test_activities_customization(self) -> None:
        app = PuffoCoachApp()
        async with app.run_test() as pilot:
            # Uncheck all sports except ride
            for _, slug in PRIMARY_SPORTS:
                if slug != "ride":
                    app.query_one(f"#chk_sport_{slug}").value = False
            await pilot.pause(0.1)
            self.assertFalse(app.query_one("#chk_activities_all").value)

            app.query_one("#inp_custom_sports").value = "padel, tennis"
            await pilot.pause(0.1)
            _, _, cfgs = app._build_configs()
            self.assertEqual(cfgs["activities"].filter, ["ride", "padel", "tennis"])

    async def test_health_detail_selection(self) -> None:
        app = PuffoCoachApp()
        async with app.run_test() as pilot:
            app.query_one("#sel_health_detail").value = 12
            await pilot.pause(0.1)
            _, _, cfgs = app._build_configs()
            self.assertTrue(cfgs["health"].enabled)
            self.assertEqual(cfgs["health"].detail_level, 12)

    async def test_render_and_save(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "test_out.md"
            app = PuffoCoachApp()
            async with app.run_test() as pilot:
                dummy = PipelineResult(
                    markdown="# Generated LLM Context\n\n<meals>Breakfast</meals>",
                    stats=PipelineStats(meals_count=1, activities_count=2, sleep_sessions_count=1, daily_metrics_count=6),
                    meals=[],
                    activities=[],
                    health=None,
                )
                app._on_generation_success(dummy, date(2026, 9, 1), date(2026, 9, 7))
                await pilot.pause(0.1)

                footer = app.query_one("#footer_stats")
                self.assertIn("Meals: 1", str(footer.content))

                app.query_one("#inp_output_path").value = str(out_file)
                app.action_save_context()
                await pilot.pause(0.05)
                self.assertTrue(out_file.exists())
                self.assertEqual(out_file.read_text(encoding="utf-8"), dummy.markdown)

    async def test_command_palette_disabled(self) -> None:
        app = PuffoCoachApp()
        async with app.run_test() as pilot:
            self.assertFalse(app.ENABLE_COMMAND_PALETTE)
            await pilot.press("ctrl+p")
            await pilot.pause(0.05)
            self.assertEqual(len(app.screen_stack), 1)


if __name__ == "__main__":
    unittest.main()
