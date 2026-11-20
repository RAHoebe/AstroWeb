from threading import Thread

import numpy as np
import pytest
from PIL import Image
from werkzeug.serving import make_server

from astroweb import lunar_detail, surface_labels
from astroweb.app import create_app
from astroweb.media import import_object


@pytest.fixture
def app(tmp_path):
    app = create_app(tmp_path/"library", testing=True)
    store = app.extensions["store"]
    photo = tmp_path/"planet.png"
    Image.new("RGB",(300,240),"darkred").save(photo)
    for body in ("JUPITER","SATURN"):
        capture = import_object(store,body,[photo])
        store.update("objects",capture["id"],published=True)
    try:
        yield app
    finally:
        app.extensions["jobs"].shutdown()


def sign_in(client):
    with client.session_transaction() as session:
        session["admin"] = True
    return client.get("/api/session").json["csrf"]


def test_saved_features_use_original_coordinates_and_scope_to_capture(app):
    client = app.test_client()
    route = "/api/admin/objects/JUPITER/surface-label"
    mark = dict(preset="great-red-spot", x=.63, y=.43)
    assert client.put(route,json=mark).status_code == 403
    anonymous = client.get("/api/session").json["csrf"]
    assert client.put(route,json=mark,headers={"X-CSRF-Token":anonymous}).status_code == 401
    headers = {"X-CSRF-Token":sign_in(client)}
    assert client.put(route,json={**mark,"y":1.1},headers=headers).status_code == 400
    assert client.put(route,json={**mark,"preset":"cassini-division"},headers=headers).status_code == 400
    assert client.put(route,json=mark,headers=headers).status_code == 200
    mark["x"] = .7
    assert client.put(route,json=mark,headers=headers).status_code == 200
    visitor = app.test_client()
    live = visitor.get("/api/objects/JUPITER/discover").json
    assert "presets" not in live
    point, = live["objects"]
    assert (point["x"],point["y"],point["placement"]) == (.7,.43,"manual")
    assert point["name"]["nl"] == "Grote Rode Vlek"
    assert point["name"]["en"] == "Great Red Spot"
    assert point["summary"]["nl"] and point["summary"]["en"]
    assert point["journey"] == "PIA21395"
    assert visitor.get("/api/objects/SATURN/discover").json["objects"] == []
    assert client.put(route,json={"id":point["id"],"remove":True},headers=headers).status_code == 200
    assert visitor.get("/api/objects/JUPITER/discover").json["objects"] == []


def test_lunar_labels_use_inverse_registration_and_skip_shadow(tmp_path, monkeypatch):
    photo = tmp_path/"moon.jpg"
    Image.new("RGB",(720,720),"gray").save(photo)
    matrix = np.array([[0.,-1.,719.],[1.,0.,0.],[0.,0.,1.]])
    view = dict(subearth_lon=0.,subearth_lat=0.,posangle=0.,subsolar_lon=-70.,subsolar_lat=0.)
    monkeypatch.setattr(lunar_detail,"registered_view",lambda *args:(matrix,view,np.array([359.5,359.5]),300.))
    store = type("Store",(),{"path":lambda self,path:photo})()
    found = {p["id"]:p for p in surface_labels.lunar_points(store,{"poster":"moon.jpg"})}
    assert "moon-aristarchus" in found
    assert "PIA12909" not in found
    point = found["moon-aristarchus"]
    assert point["x"] < .5 and point["y"] > .5
    assert point["journey"] == "moon-aristarchus"
    assert point["placement"] == "registered"


def test_viewer_guide_mark_cycle_zoom_and_original_tab(app):
    pw = pytest.importorskip("playwright.sync_api")
    client = app.test_client()
    sign_in(client)
    cookie = client.get_cookie("session").value
    web = make_server("127.0.0.1",0,app,threaded=True)
    Thread(target=web.serve_forever,daemon=True).start()
    origin = f"http://127.0.0.1:{web.server_port}"
    try:
        with pw.sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome")
            page = browser.new_page(viewport={"width":1024,"height":768})
            page.context.add_cookies([{"name":"session","value":cookie,"url":origin}])
            errors = []
            page.on("pageerror",lambda error:errors.append(str(error)))
            page.goto(origin+"/viewer/JUPITER")
            page.get_by_role("tab",name="Wat zie ik?").click()
            pw.expect(page.locator("#discovery-status")).to_contain_text("nog geen onderdelen")
            for preset in ("great-red-spot","cloud-belts"):
                page.locator("#surface-add").click()
                page.locator("#surface-preset").select_option(preset)
                image = page.locator("#viewer-original")
                pw.expect(image).to_be_visible()
                rect = image.bounding_box()
                page.mouse.click(rect["x"]+rect["width"]*.68,rect["y"]+rect["height"]*.42)
                page.locator("#surface-save").click()
                pw.expect(page.locator("#discovery-list")).to_have_value(preset)
            page.locator("#discovery-prev").click()
            pw.expect(page.locator("#discovery-list")).to_have_value("great-red-spot")
            pw.expect(page.locator("#discovery-journey")).to_have_attribute("href","/viewer/JUPITER?destination=PIA21395#solar-system")
            page.locator("#discovery-zoom").click()
            pw.expect(page.locator("#original-level")).to_have_text("3×")
            page.locator("#discovery-zoom").click()
            pw.expect(page.locator("#original-level")).to_have_text("1×")
            page.locator("#viewer [data-lang=en]").click()
            pw.expect(page.locator("#discovery-list option:checked")).to_have_text("Great Red Spot")
            page.get_by_role("tab",name="Original").click()
            pw.expect(page.locator("#discovery-pins")).to_be_hidden()
            pw.expect(page.locator("#viewer-original")).to_be_visible()
            assert not errors
            browser.close()
    finally:
        web.shutdown()
