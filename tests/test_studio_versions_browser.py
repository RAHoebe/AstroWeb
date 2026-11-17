"""Studio must move to a finished render once, then respect the viewer's choice."""
from threading import Thread

import pytest
from PIL import Image
from werkzeug.serving import make_server

from astroweb.app import create_app
from astroweb.media import import_object

pw = pytest.importorskip("playwright.sync_api")


def test_finished_render_and_capture_labels(tmp_path, monkeypatch):
    app = create_app(tmp_path / "data", testing=True)
    store, queue = app.extensions["store"], app.extensions["jobs"]
    # Keep catalogues offline. Encoding, publication, polling and playback use the normal paths.
    monkeypatch.setattr(queue, "prepare_capture", lambda *_: None)
    monkeypatch.setattr(queue, "prepare_journey", lambda *_: None)
    web = make_server("127.0.0.1", 0, app, threaded=True)
    worker = Thread(target=web.serve_forever, daemon=True)
    worker.start()
    try:
        for ident, size in (("IC_1396", (192, 128)), ("NGC_7000", (128, 192))):
            paths = []
            for role in ("final", "starless", "stars", "stars_laid"):
                path = tmp_path / f"{ident}_{role}.png"
                Image.new("RGB", size, "navy").save(path)
                paths.append(path)
            import_object(store, ident, paths)
        job = queue.submit("IC_1396", {"duration": 4, "resolution": 720})
        queue.futures[job["id"]].result(timeout=60)
        with app.test_client() as client:
            with client.session_transaction() as session:
                session["admin"] = True
            cookie = client.get_cookie("session").value
        origin = f"http://127.0.0.1:{web.server_port}"
        with pw.sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome")
            page = browser.new_page()
            page.context.add_cookies([{"name": "session", "value": cookie, "url": origin}])
            page.goto(origin + "/admin")
            options = page.locator("#admin-object-list button")
            options.filter(has_text="NGC 7000").click()
            pw.expect(page.locator("#focus-image")).to_be_visible()
            pw.expect(page.locator("#film-orientation")).to_be_hidden()
            options.filter(has_text="IC 1396").click()
            pw.expect(page.locator("#film-orientation")).to_be_visible()
            page.locator("#studio [data-lang=en]").click()
            pw.expect(page.locator("#edit-object-title")).to_have_text("IC 1396 · The Elephant’s Trunk region")
            assert options.filter(has_text="IC 1396").inner_text().count("IC 1396") == 1
            # Polling must keep an unchanged object button connected and focused.
            button = options.filter(has_text="IC 1396")
            button.focus()
            with page.expect_response(lambda r: r.url.endswith("/api/admin/objects")):
                pass
            pw.expect(button).to_be_focused()
            versions = page.locator("#version-list")
            pw.expect(versions).to_have_value(job["id"])
            page.locator("#render-button").click()
            pw.expect(versions.locator("option")).to_have_count(2, timeout=60000)
            latest = versions.locator("option").first.get_attribute("value")
            pw.expect(versions).to_have_value(latest)
            player = page.locator("#version-video")
            pw.expect(player).to_have_attribute("src", f"/api/admin/objects/IC_1396/versions/{latest}/movie")
            page.wait_for_function("document.querySelector('#version-video').readyState >= 1")
            versions.select_option(job["id"])
            with page.expect_response(lambda r: r.url.endswith("/api/admin/objects")):
                pass
            pw.expect(versions).to_have_value(job["id"])
            browser.close()
    finally:
        web.shutdown()
        web.server_close()
        queue.shutdown()
