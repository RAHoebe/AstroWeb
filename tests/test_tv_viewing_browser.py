"""Contextual exploration, random playback and decoded-frame transitions."""
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import subprocess
from urllib.parse import urlsplit

from PIL import Image
import pytest
from astroweb.render import ffmpeg_executable

pw = pytest.importorskip("playwright.sync_api")
ASSETS = Path(__file__).resolve().parents[1] / "tv/app/src/main/assets"


def viewing_fixture(page, mode="modes", lang="en", primary="A"):
    html = (ASSETS / "viewing.html").read_text(encoding="utf8")
    for token, script in [("PHOTO_CAMERA", "photo-camera.js"), ("NIGHT_CHART", "night-chart.js"), ("VIEWING", "viewing.js")]:
        html = html.replace(f"__{token}__", (ASSETS / script).read_text(encoding="utf8"))
    html = html.replace("__LANG__", lang).replace("__CAPTURE__", primary).replace("__MAP__", mode)
    rows = [{"id": ident, "catalog_id": ident, "name": {"en": ident, "nl": ident}, "date": "2026-11-15",
             "field": {"kind": "gaia"}, "final": f"/media/{ident}/final"} for ident in "AB"]
    rows[0]["video"] = "/media/A/movie"
    if primary=="SATURN":
        rows.append({"id":"SATURN","catalog_id":"SATURN","body":"SATURN","name":{"en":"Saturn","nl":"Saturnus"}})
    photo = BytesIO()
    Image.new("RGB", (200, 360), "navy").save(photo, "JPEG")
    requests = []
    stamp = datetime(2026, 11, 15, tzinfo=timezone.utc).timestamp()
    sequence = dict(day="2026-11-15", start=stamp, step=600, target=[[180, 30], [190, 40]], hours=[0, 1], peak=1,
                    bodies={"sun": [[10, -30], [20, -35]]})

    def serve(route):
        path = urlsplit(route.request.url).path
        requests.append(path)
        if path == "/":
            route.fulfill(content_type="text/html", body=html)
        elif path == "/api/objects":
            route.fulfill(json={"objects": rows})
        elif path == "/api/atlas":
            route.fulfill(json={"captures": rows})
        elif path in ("/api/objects/A", "/api/objects/B", "/api/objects/SATURN"):
            route.fulfill(json=next(row for row in rows if row["id"] == path.split("/")[-1]))
        elif path=="/api/objects/SATURN/discover":
            route.fulfill(json={"kind":"surface","objects":[
                {"id":"titan","name":"Titan","type":"Moon","x":.3,"y":.46},
                {"id":"rings","name":{"en":"Rings","nl":"Ringen"},"type":"Feature","x":.75,"y":.48,
                 "journey":"PIA11141"},
            ]})
        elif path=="/api/objects/SATURN/solar-system":
            route.fulfill(json={"observations":[{"id":"PIA11657"},{"id":"PIA11141"}]})
        elif path.endswith("/discover"):
            target = path.split("/")[-2]
            route.fulfill(json={"objects": [{"id": target + str(i), "name": target + " feature " + str(i),
                                             "x": .4 + i * .1, "y": .5, "ra": 10, "dec": 30, "type": "star"}
                                            for i in (1, 2)]})
        elif path.endswith("/night-tracks"):
            route.fulfill(json=dict(capture=sequence, tonight=sequence, observed=stamp, now=stamp,
                                    timezone="UTC", default_site=True, day_only=False))
        elif path.endswith("/poster") or path.endswith("/final"):
            route.fulfill(content_type="image/jpeg", body=photo.getvalue())
        elif path.endswith("/tv-program"):
            route.fulfill(json={"journey": None, "trips": []})
        else:
            route.fulfill(json={"observations": []})

    page.route("http://tv.test/**", serve)
    return requests


@pytest.mark.parametrize("lang", ["nl", "en"])
def test_explore_only_uses_selected_capture_and_has_two_actions(lang):
    with pw.sync_playwright() as runtime:
        browser = runtime.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 960, "height": 540})
        requests = viewing_fixture(page, mode="explore", lang=lang, primary="B")
        page.goto("http://tv.test/")
        expected = ["Opnamenacht en vanavond", "Wat zie ik?"] if lang == "nl" else ["Capture night and tonight", "What am I seeing?"]
        pw.expect(page.locator("#choices button")).to_have_text(expected)
        pw.expect(page.locator("#menu h1")).to_have_text("Verken" if lang == "nl" else "Explore")
        page.get_by_role("button", name=expected[1], exact=True).click()
        pw.expect(page.locator("#hud")).to_contain_text("B feature 1")
        page.evaluate("()=>{for(let i=0;i<7;i++)mapKey('next');mapKey('previous');mapKey('out');mapKey('in');}")
        pw.expect(page.locator("#hud")).to_contain_text("B feature")
        assert not any("/objects/A" in path for path in requests)
        assert "/api/objects" not in requests and "/api/atlas" not in requests
        assert page.evaluate("collectionBack()")
        pw.expect(page.locator("#choices button")).to_have_text(expected)
        page.get_by_role("button", name=expected[0], exact=True).click()
        pw.expect(page.locator("#hud strong")).to_have_text("Opnamenacht" if lang == "nl" else "Capture night")
        assert "/api/objects/B/night-tracks" in requests
        page.evaluate("mapKey('out')")
        pw.expect(page.locator("#hud strong")).to_have_text("Vanavond" if lang == "nl" else "Tonight")
        browser.close()


@pytest.mark.parametrize("lang", ["nl","en"])
def test_hold_ok_opens_the_selected_saturn_detail_and_back_keeps_the_ring(tmp_path,lang):
    clip=tmp_path/"rings.mp4"
    subprocess.run([ffmpeg_executable(),"-hide_banner","-loglevel","error","-y","-f","lavfi",
                    "-i","color=c=navy:s=320x180:r=24:d=5","-c:v","libx264","-pix_fmt","yuv420p",
                    "-movflags","+faststart",str(clip)],check=True)
    with pw.sync_playwright() as runtime:
        browser=runtime.chromium.launch(channel="chrome",args=["--autoplay-policy=no-user-gesture-required"])
        page=browser.new_page(viewport={"width":960,"height":540},reduced_motion="reduce")
        requests=viewing_fixture(page,mode="explore",lang=lang,primary="SATURN")
        path="/media/SATURN/solar-system/PIA11141"
        page.route("**"+path,lambda route:route.fulfill(path=clip,content_type="video/mp4"))
        page.goto("http://tv.test/")
        page.get_by_role("button",name="Wat zie ik?" if lang=="nl" else "What am I seeing?",exact=True).click()
        hint="Houd OK vast  Detailreis" if lang=="nl" else "Hold OK  Detail journey"
        name="Ringen" if lang=="nl" else "Rings"
        pw.expect(page.locator("#hud strong")).to_contain_text("Titan")
        page.wait_for_function("()=>document.querySelector('.guide-camera img')?.complete")
        page.evaluate("()=>mapKey('rotate')")
        pw.expect(page.locator("video")).to_have_count(0)
        page.evaluate("()=>mapKey('next')")
        pw.expect(page.locator("#hud strong")).to_contain_text(name)
        pw.expect(page.locator("#hint")).to_contain_text(hint)
        page.evaluate("()=>mapKey('rotate')")
        pw.expect(page.locator(".scene.visible video")).to_have_attribute("src",path)
        assert "/api/objects/SATURN/solar-system" in requests
        assert "/api/objects/SATURN/hubble" not in requests
        assert page.evaluate("()=>collectionBack()")
        pw.expect(page.locator("#hud strong")).to_contain_text(name)
        pw.expect(page.locator("#hint")).to_contain_text(hint)
        browser.close()


@pytest.mark.parametrize("lang", ["nl", "en"])
def test_home_modes_start_randomly_without_capture_or_settings_picker(lang):
    with pw.sync_playwright() as runtime:
        browser = runtime.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 960, "height": 540})
        viewing_fixture(page, lang=lang)
        page.add_init_script("Math.random=()=>.99")
        page.goto("http://tv.test/")
        expected = ["Avondvoorstelling", "Fotolijst"] if lang == "nl" else ["Evening programme", "Photo frame"]
        pw.expect(page.locator("#choices button")).to_have_text(expected)
        page.get_by_role("button", name=expected[1], exact=True).click()
        pw.expect(page.locator("#menu")).to_be_hidden()
        pw.expect(page.locator(".scene.visible .photo-plane img[src='/media/B/poster']")).to_be_visible()
        plane = page.locator(".photo-plane.tall")
        assert plane.bounding_box() == pytest.approx({"x": 0, "y": 0, "width": 960, "height": 540})
        assert page.evaluate("collectionBack()")
        pw.expect(page.locator("#choices button")).to_have_text(expected)
        page.get_by_role("button", name=expected[0], exact=True).click()
        pw.expect(page.locator("#menu")).to_be_hidden()
        pw.expect(page.locator(".scene.visible .photo-plane img[src='/media/B/poster']")).to_be_visible()
        pw.expect(page.locator("#hud strong")).to_contain_text("B")
        browser.close()


def test_evening_preserves_photo_until_next_video_has_a_decoded_frame():
    with pw.sync_playwright() as runtime:
        browser = runtime.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 960, "height": 540})
        viewing_fixture(page)
        page.add_init_script("Math.random=()=>0")
        page.goto("http://tv.test/")
        held = []
        page.route("**/media/A/movie", lambda route: held.append(route))
        page.get_by_role("button", name="Evening programme").click()
        pw.expect(page.locator(".scene.visible .photo-plane")).to_be_visible()
        pw.expect(page.locator(".scene")).to_have_count(1)
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
