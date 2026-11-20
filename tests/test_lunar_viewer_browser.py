"""Real web routes expose the new lunar destinations in both interface languages."""
import subprocess
from threading import Thread

import pytest
from PIL import Image
from werkzeug.serving import make_server

from astroweb.app import create_app
from astroweb.media import import_object
from astroweb.render import ffmpeg_executable
from astroweb import solar_detail

pw=pytest.importorskip('playwright.sync_api')


def test_lunar_destinations_names_sources_and_selection(tmp_path,monkeypatch):
    app=create_app(tmp_path/'data',testing=True)
    store,queue=app.extensions['store'],app.extensions['jobs']
    photo=tmp_path/'Moon.png';Image.new('RGB',(128,128),'gray').save(photo)
    record=import_object(store,'MOON',[photo],capture_date='2026-09-27T21:42:17+00:00')
    store.update('objects',record['id'],published=True)
    video=tmp_path/'test.mp4'
    subprocess.run([ffmpeg_executable(),'-hide_banner','-loglevel','error','-y','-f','lavfi',
                    '-i','color=c=gray:s=320x180:r=24','-t','0.25','-c:v','libx264','-pix_fmt','yuv420p',str(video)],check=True)
    monkeypatch.setattr(solar_detail,'movie',lambda *args:video)
    server=make_server('127.0.0.1',0,app,threaded=True)
    Thread(target=server.serve_forever,daemon=True).start()
    origin=f'http://127.0.0.1:{server.server_port}'
    try:
        with pw.sync_playwright() as playwright:
            browser=playwright.chromium.launch(channel='chrome')
            page=browser.new_page(viewport=dict(width=1366,height=768))
            errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(origin+'/viewer/MOON#solar-system')
            pw.expect(page.locator('#hubble-panel')).to_be_visible()
            pw.expect(page.locator('#hubble-field option')).to_have_count(10)
            pw.expect(page.locator('#hubble-field option[value=moon-copernicus]')).to_have_text('Copernicus-krater')
            page.locator('#hubble-field').select_option('moon-copernicus')
            pw.expect(page.locator('#hubble-video')).to_have_attribute('src','/media/MOON/solar-system/moon-copernicus')
            pw.expect(page.locator('#hubble-description')).to_contain_text('ingemeten LRO')
            page.locator('#viewer [data-lang=en]').click()
            pw.expect(page.locator('#hubble-field option[value=moon-copernicus]')).to_have_text('Copernicus crater')
            pw.expect(page.locator('#hubble-description')).to_contain_text('registered LRO')
            pw.expect(page.locator('#hubble-source')).to_have_attribute('href','https://data.lroc.im-ldi.com/lroc/?c_lon=-20.08&c_lat=9.62')
            assert not errors
            browser.close()
    finally:
        server.shutdown();queue.shutdown()
