"""Open a disposable UI preview; all writable JSON records live in a temp directory.

Run from the project root with: python -B tools/smoke_app.py
The preview closes after 40 seconds. It never changes the game's settings.
"""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import config
    import blueprint_db
    import crafting_db
    import refinery_db
    import main as application
    from hud_controller import TopTelemetryHUD
    from session_store import ServerLogManager

    with tempfile.TemporaryDirectory(prefix="synthscan-preview-") as directory:
        output = Path(directory)
        for name in ("config.json", "server_log.json", "shard_history.json", "inventory.json",
                     "crafting_recipes.json", "blueprints_library.json", "blueprints_catalog.json", "blueprints_favorites.json"):
            shutil.copy2(ROOT / name, output / name)
        config.CONFIG_FILE = str(output / "config.json")
        refinery_db.INVENTORY_FILE = str(output / "inventory.json")
        crafting_db.RECIPES_FILE = str(output / "crafting_recipes.json")
        blueprint_db.BLUEPRINT_LIB_FILE = str(output / "blueprints_library.json")
        blueprint_db.BLUEPRINT_CATALOG_FILE = str(output / "blueprints_catalog.json")
        blueprint_db.BLUEPRINT_FAVORITES_FILE = str(output / "blueprints_favorites.json")
        application.ServerLogManager = lambda: ServerLogManager(output / "server_log.json")
        application.TopTelemetryHUD = lambda **kwargs: TopTelemetryHUD(**kwargs, history_path=output / "shard_history.json")
        app = application.SynthScanApp(start_hidden="--hidden" in sys.argv)
        errors = []

        def report_exception(kind, value, tb):
            errors.append(str(value))
            traceback.print_exception(kind, value, tb)

        app.root.report_callback_exception = report_exception
        app.root.after(1000, lambda: app.switch_page("servers"))
        app.root.after(2000, lambda: app.top_hud.set_game_monitor(1))

        def inspect():
            app.root.update_idletasks()
            bounds = app.top_hud.bar_canvas.bbox("all")
            text_bounds = [app.top_hud.bar_canvas.bbox(item)
                           for item in app.top_hud.bar_canvas.find_all()
                           if app.top_hud.bar_canvas.type(item) == "text"]
            hud_text = [app.top_hud.bar_canvas.itemcget(item, "text")
                        for item in app.top_hud.bar_canvas.find_all()
                        if app.top_hud.bar_canvas.type(item) == "text"]
            state = app.top_hud.state
            for metric, label in (("ping_ms", "PING:"), ("entities", "ENT:")):
                if state.get(metric) is None and label in hud_text:
                    errors.append(f"Unavailable {metric} is displayed")
            if "MED:" in hud_text:
                errors.append("Unverified medical imprint is displayed")
            clipped = [box for box in text_bounds if box and
                       (box[0] < 0 or box[1] < 0 or box[2] > app.top_hud.bar_width or box[3] > app.top_hud.BAR_HEIGHT)]
            if clipped:
                errors.append("HUD text extends outside its window")
            controls = []
            def find_controls(widget):
                if isinstance(widget, application.ctk.CTkButton) and "SHARD" in str(widget.cget("text")):
                    controls.append({"text": widget.cget("text"), "x": widget.winfo_rootx() - app.root.winfo_rootx(),
                                     "width": widget.winfo_width(), "mapped": bool(widget.winfo_ismapped())})
                for child in widget.winfo_children():
                    find_controls(child)
            find_controls(app.root)
            print(json.dumps({"event": "preview_ready", "shard": app.top_hud.state.get("full_shard_id"),
                              "health": app.top_hud.state.get("health", {}).get("status"),
                              "window_width": app.root.winfo_width(), "window_state": app.root.state(),
                              "geometry": app.root.geometry(), "controls": controls,
                              "bar_width": app.top_hud.bar_width, "bar_height": app.top_hud.BAR_HEIGHT,
                              "hud_text": hud_text,
                              "drawing_bounds": bounds, "clipped_text": clipped,
                              "history_cards": len(app.scroll_servers.winfo_children()), "callback_errors": errors}), flush=True)

        app.root.after(4000, inspect)

        if "--exercise-respawn-note" in sys.argv:
            def exercise_respawn_note():
                app.open_set_medical_imprint_dialog()
                popup = next(widget for widget in app.root.winfo_children()
                             if isinstance(widget, application.ctk.CTkToplevel)
                             and widget.title() == "RESPAWN NOTE (MANUAL)")
                entries, buttons, labels = [], [], []
                def collect(widget):
                    if isinstance(widget, application.ctk.CTkEntry):
                        entries.append(widget)
                    if isinstance(widget, application.ctk.CTkButton):
                        buttons.append(widget)
                    if isinstance(widget, application.ctk.CTkLabel):
                        labels.append(str(widget.cget("text")))
                    for child in widget.winfo_children():
                        collect(child)
                collect(popup)
                assert any("does not sync" in text for text in labels)
                assert not any("Auto-syncs" in text for text in labels)
                entries[0].delete(0, "end")
                entries[0].insert(0, "PREVIEW MANUAL NOTE")
                next(button for button in buttons if button.cget("text") == "SAVE NOTE").invoke()
                assert app.cfg["medical_imprint"] == "PREVIEW MANUAL NOTE"
                assert app.btn_hdr_med.cget("text") == "🏥 RESPAWN NOTE"
                app.top_hud.render_bar()
                assert not any("PREVIEW MANUAL NOTE" in app.top_hud.bar_canvas.itemcget(item, "text")
                               for item in app.top_hud.bar_canvas.find_all()
                               if app.top_hud.bar_canvas.type(item) == "text")
                print(json.dumps({"event": "manual_respawn_note_passed", "temporary_records_only": True}), flush=True)
            app.root.after(12000, exercise_respawn_note)

        if "--all-pages" in sys.argv:
            enabled = app.top_hud.enabled
            app.on_top_hud_toggle(not enabled)
            assert app.top_hud.enabled != enabled
            app.on_top_hud_toggle(enabled)
            print(json.dumps({"event": "hud_toggle_without_settings_page", "passed": True}), flush=True)
            for delay, page in enumerate(tuple(app._page_builders), start=5):
                def inspect_page(page=page):
                    app.switch_page(page)
                    app.root.update_idletasks()
                    print(json.dumps({"event": "page_opened", "page": page,
                                      "children": len(app.pages[page].winfo_children())}), flush=True)
                app.root.after(delay * 1000, inspect_page)
            app.root.after(14000, lambda: app.top_hud.set_compact(False))
            app.root.after(14500, inspect)
            app.root.after(15000, lambda: app.top_hud.set_compact(True))
            app.root.after(15500, inspect)
            if "--hidden" in sys.argv:
                app.root.after(16000, app._restore_window)
                app.root.after(16500, inspect)
            app.root.after(18000, app.exit_app)

        if "--observe-telemetry" in sys.argv:
            def inspect_live():
                state = app.top_hud.state
                print(json.dumps({"event": "live_telemetry", "values": {key: state.get(key) for key in
                                  ("ping_ms", "client_fps", "server_fps", "shard_pop", "srv_pop", "server_name")},
                                  "sources": {key: state.get("metric_meta", {}).get(key) for key in
                                  ("ping_ms", "client_fps", "server_fps", "shard_pop", "srv_pop")},
                                  "callback_errors": errors}), flush=True)
            for delay in (10000, 20000, 30000):
                app.root.after(delay, inspect_live)

        if "--exercise-reminder" in sys.argv:
            def exercise_reminder():
                app.open_shard_reminder_dialog()
                popup = next(widget for widget in app.root.winfo_children()
                             if isinstance(widget, application.ctk.CTkToplevel) and widget.title() == "SHARD REMINDER")
                entries, buttons = [], []
                def collect(widget):
                    if isinstance(widget, application.ctk.CTkEntry):
                        entries.append(widget)
                    if isinstance(widget, application.ctk.CTkButton):
                        buttons.append(widget)
                    for child in widget.winfo_children():
                        collect(child)
                collect(popup)
                entries[0].insert(0, "PREVIEW TEST")
                entries[1].delete(0, "end")
                entries[1].insert(0, "30")
                next(button for button in buttons if button.cget("text") == "SAVE REMINDER").invoke()
                assert app.top_hud.state["cooldowns"][-1]["label"] == "PREVIEW TEST"
                print(json.dumps({"event": "reminder_flow_passed", "temporary_records_only": True}), flush=True)
            app.root.after(6500, exercise_reminder)

        app.root.after(40000, app.exit_app)
        try:
            app.root.mainloop()
        except SystemExit:
            raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
