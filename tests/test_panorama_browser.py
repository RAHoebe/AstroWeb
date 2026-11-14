"""Run with Playwright and Chrome installed to exercise the panorama loading race."""
import io
from pathlib import Path

import pytest
from PIL import Image

playwright = pytest.importorskip("playwright.sync_api")
STATIC = Path(__file__).resolve().parents[1] / "astroweb" / "static"


@pytest.mark.parametrize("pixel_ratio", [1, 2])
def test_delayed_panorama_decode_cannot_overwrite_selected_capture(pixel_ratio):
    output = io.BytesIO()
    Image.new("RGB", (800, 400), "navy").save(output, format="JPEG")
    def pin(target, x):
        return {"target":target,"name":{"nl":target,"en":target},"x":x,"y":.5,
                "corners":[[x-.03,.48],[x+.03,.48],[x+.03,.52],[x-.03,.52]]}
    scene = {"wrap":True,"image":"/sky.jpg","pins":[pin("NGC_7000",.25),pin("M_31",.65)]}

    def respond(route):
        from urllib.parse import urlsplit
        path = urlsplit(route.request.url).path
        if path=="/panorama":
            route.fulfill(path=STATIC/"panorama.html")
        elif path=="/api/panorama":
            route.fulfill(json=scene)
        elif path.startswith("/static/"):
            route.fulfill(path=STATIC/Path(path).name)
        elif path=="/sky.jpg" or path.endswith("/poster"):
            route.fulfill(body=output.getvalue(),content_type="image/jpeg")
        else:
            route.fulfill(body="viewer",content_type="text/html")

    with playwright.sync_playwright() as pw:
        browser=pw.chromium.launch(channel="chrome")
        page=browser.new_page(device_scale_factor=pixel_ratio,reduced_motion="reduce")
        page.route("http://panorama.test/**",respond)
        page.add_init_script("""const decode=Image.prototype.decode;
          Image.prototype.decode=async function(){
            await decode.call(this);
            if(this.src.endsWith('/sky.jpg')){
              document.documentElement.dataset.decoding='true';
              await new Promise(resolve=>window.finishDecode=resolve);
            }
          };""")
        page.goto("http://panorama.test/panorama")
        playwright.expect(page.locator("html")).to_have_attribute("data-decoding","true")
        picker=page.locator("#pano-jump")
        playwright.expect(picker).to_be_disabled()
        page.evaluate("finishDecode()")
        playwright.expect(picker).to_be_enabled()
        picker.select_option("M_31")
        page.uncheck("#pano-labels")
        stage=page.locator("#pano-stage")
        stage.click(position=stage.evaluate("e=>({x:e.clientWidth/2,y:e.clientHeight/2})"))
        playwright.expect(page).to_have_url("http://panorama.test/viewer/M_31?from=panorama#original")
        browser.close()
