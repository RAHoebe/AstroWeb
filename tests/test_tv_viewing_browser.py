"""Check TV photo framing and navigation with a single catalogue feature."""
from io import BytesIO
from pathlib import Path

from PIL import Image
import pytest

pw = pytest.importorskip("playwright.sync_api")
ASSETS = Path(__file__).resolve().parents[1] / "tv/app/src/main/assets"


def test_portrait_fits_and_single_feature_advances_to_another_capture():
    page_html = (ASSETS / "viewing.html").read_text(encoding="utf8")
    for token, script in [("PHOTO_CAMERA", "photo-camera.js"), ("NIGHT_CHART", "night-chart.js"), ("VIEWING", "viewing.js")]:
        page_html = page_html.replace(f"__{token}__", (ASSETS / script).read_text(encoding="utf8"))
    page_html = page_html.replace("__LANG__", "en").replace("__CAPTURE__", "A").replace("__MAP__", "modes")
    rows = [{"id": x, "catalog_id": x, "name": {"en": x}, "date": "2026-11-15",
             "field": {"kind": "gaia"}} for x in "AB"]
    rows[0].update(video="/media/A/movie", final="/media/A/final")
    photo = BytesIO()
    Image.new("RGB", (200, 360), "navy").save(photo, "JPEG")

    def serve(route):
        path = route.request.url.split(".test", 1)[1]
        if path == "/":
            route.fulfill(content_type="text/html", body=page_html)
        elif path == "/api/objects":
            route.fulfill(json={"objects": rows})
        elif path == "/api/atlas":
            route.fulfill(json={"captures": rows})
        elif path.endswith("/discover"):
            target = path.split("/")[-2]
            route.fulfill(json={"objects": [{"id": target, "name": target + " feature", "x": .5,
                                             "y": .5, "ra": 10, "dec": 30, "type": "star"}]})
        elif path.endswith("/poster"):
            route.fulfill(content_type="image/jpeg", body=photo.getvalue())
        else:
            route.fulfill(json={"observations": []})

    with pw.sync_playwright() as runtime:
        browser = runtime.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 960, "height": 540})
        page.route("http://tv.test/**", serve)
        page.goto("http://tv.test/")
        page.get_by_role("button", name="Photo frame").click()
        page.get_by_role("button", name="A ·").click()
        page.get_by_role("button", name="Slow movement").click()
        plane = page.locator(".photo-plane.tall")
        pw.expect(plane).to_be_visible()
        assert plane.bounding_box() == pytest.approx({"x": 0, "y": 0, "width": 960, "height": 540})
        for _ in range(3):
            assert page.evaluate("collectionBack()")
        page.get_by_role("button", name="What am I seeing?").click()
        page.get_by_role("button", name="A ·").click()
        pw.expect(page.locator("#hud")).to_contain_text("A feature")
        page.evaluate("mapKey('next')")
        pw.expect(page.locator("#hud")).to_contain_text("B feature")
        page.evaluate("mapKey('in')")
        pw.expect(page.locator("#hud")).to_contain_text("A feature")
        page.evaluate("collectionBack()")
        page.evaluate("collectionBack()")
        held = []
        page.route("**/media/A/movie", lambda route: held.append(route))
        page.get_by_role("button", name="Evening programme").click()
        page.get_by_role("button", name="A ·").click()
        page.get_by_role("button", name="5 min", exact=True).click()
        pw.expect(page.locator(".scene.visible .photo-plane")).to_be_visible()
        pw.expect(page.locator(".scene")).to_have_count(1)
        pw.expect(page.locator(".scene.visible img[src='/media/A/poster']")).to_be_visible()
        page.evaluate("mapKey('next')")
        pw.expect(page.locator("video")).to_have_count(1)
        page.wait_for_function("document.querySelector('video').networkState === 2")
        assert held
        assert page.locator("video").evaluate("v=>getComputedStyle(v.parentElement).opacity") == "0"
        pw.expect(page.locator(".scene.visible img[src='/media/A/poster']")).to_be_visible()
        page.evaluate("mapKey('previous')")
        pw.expect(page.locator("video")).to_have_count(0)
        held[0].abort()
        pw.expect(page.locator(".scene")).to_have_count(1)
        browser.close()
