"""Studio must move to a finished render once, then respect the viewer's choice."""
from threading import Event, Thread

import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS
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
    save_started,release_upload=Event(),Event()
    try:
        for ident, size in (("IC_1396", (192, 128)), ("NGC_7000", (128, 192))):
            paths = []
            for role in ("final", "starless", "stars", "stars_laid"):
                path = tmp_path / f"{ident}_{role}.png"
                Image.new("RGB", size, "navy").save(path)
                paths.append(path)
            record=import_object(store, ident, paths)
            store.update("objects",record["id"],capture_date="2026-11-04")
            if ident=="IC_1396":
                newer=import_object(store,ident,paths,repeat=True,session_name="Paneel 2",capture_date="2026-11-09")
        night=import_object(store,"", [tmp_path/"NGC_7000_final.png"], nightscape="startrails",title="Sterrensporen boven het meer")
        for i in range(6):
            store.put("jobs",str(i),dict(id=str(i),object_id=night["id"],status="completed",progress=100))
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
            menu = page.locator("#admin-object-list")
            options = menu.locator("option")
            pw.expect(options).to_have_count(4)
            pw.expect(options.filter(has_text="IC 1396")).to_have_count(1)
            pw.expect(page.locator("#job-list .job-item")).to_have_count(5)
            pw.expect(page.locator("#job-list strong").nth(1)).to_have_text("Sterrensporen boven het meer")
            assert "~" not in page.locator("#job-list").inner_text()
            menu.select_option("NGC_7000")
            pw.expect(page.locator("#focus-image")).to_be_visible()
            pw.expect(page.locator("#film-orientation")).to_be_hidden()
            menu.select_option("IC_1396")
            captures=page.locator("#studio-capture-picker")
            pw.expect(captures).to_have_value(newer["id"])
            pw.expect(captures.locator("option")).to_have_count(2)
            pw.expect(captures.locator("option").first).to_contain_text("Paneel 2")
            captures.select_option("IC_1396")
            pw.expect(menu).to_have_value("IC_1396")
            pw.expect(page.locator("#film-orientation")).to_be_visible()
            page.locator("#studio [data-lang=en]").click()
            pw.expect(page.locator("#edit-object-title")).to_have_text("IC 1396 · The Elephant’s Trunk region")
            assert options.filter(has_text="IC 1396").inner_text().count("IC 1396") == 1
            # Polling must keep both the selected capture and menu focus.
            menu.focus()
            with page.expect_response(lambda r: r.url.endswith("/api/admin/objects")):
                pass
            pw.expect(menu).to_be_focused()
            pw.expect(captures).to_have_value("IC_1396")
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

            page.locator("#studio [data-lang=nl]").click()
            page.locator("#new-object").click()
            y,x=np.mgrid[:192,:256]
            image=np.asarray(220*np.exp(-((x-55)**2+(y-27)**2)/500)+
                             90*np.exp(-((x-190)**2+(y-130)**2)/400)+x/9+y/19,dtype=np.uint8)
            sources=[]
            for role in ("final","starless","stars"):
                image_file=tmp_path/f"NGC_6939_{role}.png"
                Image.fromarray(image).save(image_file)
                sources.append(image_file)
            wcs=WCS(naxis=2)
            wcs.wcs.ctype=["RA---TAN","DEC--TAN"]
            wcs.wcs.crval=[308.2967,60.408]
            wcs.wcs.crpix=[128,96]
            wcs.wcs.cd=[[-.0037,0],[0,.0037]]
            fitted=tmp_path/"NGC_6939_final.fits"
            fits.PrimaryHDU(data=image[::-1].copy(),header=wcs.to_header()).writeto(fitted)
            files=page.locator("#image-files")
            files.set_input_files([*sources,fitted])
            pw.expect(page.locator("#identifier-source")).to_contain_text("Herkend in de catalogus: NGC 6939")
            pw.expect(page.locator("#studio-editor")).to_be_hidden()
            jobs_before=len(store.all("jobs"))

            def delayed_import(*args,**kwargs):
                save_started.set()
                assert release_upload.wait(20)
                return import_object(*args,**kwargs)

            monkeypatch.setattr("astroweb.app.import_object",delayed_import)
            upload_posts=[]
            page.on("request",lambda r: upload_posts.append(r) if r.method=="POST" and
                    ("upload-autozoom" in r.url or r.url.endswith("/api/admin/objects")) else None)
            page.locator("#upload-button").click()
            assert save_started.wait(10)
            pw.expect(page.locator("#upload-progress")).to_have_attribute("value","100")
            pw.expect(page.locator("#upload-status")).to_contain_text("server controleert en bewaart")
            release_upload.set()
            pw.expect(page.locator("#draft-uploaded")).to_be_visible()
            assert len(store.all("jobs"))==jobs_before
            draft=store.get("objects","NGC_6939")
            assert draft["fits"] and not draft["published"]
            page.reload()
            menu.select_option("NGC_6939")
            pw.expect(page.locator("#draft-uploaded")).to_be_visible()
            for _ in range(2):
                page.locator("#auto-zoom").click()
                pw.expect(page.locator("#auto-alignment")).to_contain_text("FITS-hemelcoördinaten")
                pw.expect(page.locator("#auto-list li").first).to_contain_text("NGC 6939")
                pw.expect(page.locator("#auto-list")).to_contain_text("Vuurwerkstelsel")
            page.locator("#auto-apply").click()
            pw.expect(page.locator("#point-name")).to_have_value("Sterrenhoop NGC 6939")
            page.locator("#render-button").click()
            pw.expect(page.locator("#version-list option")).to_have_count(1,timeout=60000)
            assert len(upload_posts)==1
            browser.close()
    finally:
        release_upload.set()
        web.shutdown()
        web.server_close()
        queue.shutdown()
