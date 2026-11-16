"""Shared web/TV controls and cancellation of a previous exploration request."""
import io
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from PIL import Image

pw=pytest.importorskip('playwright.sync_api')
STATIC=Path(__file__).resolve().parents[1]/'astroweb/static'


def fixtures(page):
    pixels=io.BytesIO();Image.new('RGB',(640,480),'#442833').save(pixels,format='JPEG')
    capture=dict(id='M_31',name={'nl':'Andromeda','en':'Andromeda'},date='2026-11-03',poster='/photo.jpg',
                 features=dict(mosaic=True,space=False,cosmic=True,planner=False,solar=False))
    def respond(route):
        path=urlsplit(route.request.url).path
        if path in ('/observatory','/calendar'):route.fulfill(path=STATIC/'observatory.html')
        elif path.startswith('/static/'):route.fulfill(path=STATIC/Path(path).name)
        elif path=='/api/observatory':route.fulfill(json=dict(captures=[capture],month='2026-11'))
        elif path.endswith('/cosmic'):route.fulfill(json=dict(status='ready',data=dict(method='catalogue',lookback_years=2500000,source='https://science.nasa.gov/',capture=capture)))
        elif path=='/api/calendar':
            days=[dict(date=f'2026-11-{i:02d}',hours=10,dark_hours=10,windows=[],peak_altitude=None,moon_illumination=.1) for i in range(1,31)]
            route.fulfill(json=dict(status='ready',data=dict(kind='collection',month='2026-11',days=days,seasons=[days[0]]*12,best=[],timezone='Europe/Amsterdam',default_site=True,source='Astropy',events=[dict(capture,day='2026-11-03',time=None,catalog_id='M_31')])) )
        elif path.startswith('/viewer/'):
            route.fulfill(body='<h1 id="chosen">'+path.split('/')[-1]+'</h1>',content_type='text/html')
        elif path.endswith('/mosaic'):route.fulfill(json=dict(status='preparing'))
        elif path=='/photo.jpg':route.fulfill(body=pixels.getvalue(),content_type='image/jpeg')
        else:route.fulfill(status=404)
    page.route('http://observatory.test/**',respond)


def test_old_preparation_cannot_replace_new_mode_and_language_updates():
    with pw.sync_playwright() as playwright:
        browser=playwright.chromium.launch(channel='chrome')
        page=browser.new_page(reduced_motion='reduce')
        fixtures(page)
        page.add_init_script("""const original=window.fetch;
          window.fetch=async(...args)=>{
            if(String(args[0]).includes('/api/observatory/mosaic'))await new Promise(resolve=>window.releaseMosaic=resolve);
            return original(...args);
          };""")
        page.goto('http://observatory.test/observatory?capture=M_31')
        pw.expect(page.locator('body')).to_have_attribute('data-loaded','true')
        page.locator('[data-mode=mosaic]').click()
        pw.expect(page.locator('#obs-loading')).to_be_visible()
        page.locator('#obs-home').click()
        page.locator('[data-mode=cosmic]').click()
        pw.expect(page.locator('body')).to_have_attribute('data-ready','cosmic')
        page.evaluate('()=>window.releaseMosaic()')
        pw.expect(page.locator('body')).to_have_attribute('data-mode','cosmic')
        page.locator('[data-lang=en]').click()
        pw.expect(page.locator('#obs-scene-title')).to_have_text('Light journey')
        pw.expect(page.locator('#obs-return')).to_have_text('← Back to capture')
        assert 'mode=cosmic' in page.url
        assert not page.evaluate('()=>document.documentElement.scrollWidth>innerWidth')
        browser.close()


@pytest.mark.parametrize('tv',[False,True])
def test_collection_calendar_has_day_view_and_opens_the_selected_capture(tv):
    with pw.sync_playwright() as playwright:
        browser=playwright.chromium.launch(channel='chrome')
        page=browser.new_page(viewport={'width':960,'height':540} if tv else {'width':1440,'height':1000},reduced_motion='reduce')
        fixtures(page)
        page.goto('http://observatory.test/calendar?month=2026-11'+('&tv=1' if tv else ''))
        pw.expect(page.locator('body')).to_have_attribute('data-ready','planner')
        assert 'Andromeda' not in page.locator('#obs-calendar-title').inner_text()
        assert page.locator('.day-thumbs a').count()==1
        if tv:page.evaluate("()=>window.mapKey('select')")
        else:page.locator('[data-index="2"]').click()
        pw.expect(page.locator('#obs-calendar-day')).to_be_visible()
        assert page.locator('.day-photo').count()==1
        assert page.locator('.timeline-photo').count()==0  # A date-only photo has no invented timestamp.
        if tv:page.evaluate("()=>window.mapKey('select')")
        else:page.locator('.day-photo').click()
        pw.expect(page.locator('#chosen')).to_have_text('M_31')
        browser.close()


def test_tv_overview_fits_and_remote_protocol_controls_the_scene():
    with pw.sync_playwright() as playwright:
        browser=playwright.chromium.launch(channel='chrome')
        page=browser.new_page(viewport={'width':960,'height':540},reduced_motion='reduce')
        fixtures(page)
        page.goto('http://observatory.test/observatory?tv=1&capture=M_31&lang=en')
        pw.expect(page.locator('body')).to_have_attribute('data-loaded','true')
        assert page.evaluate('()=>[...document.querySelectorAll(".mode-card h2")].every(e=>e.scrollWidth<=e.clientWidth)')
        page.evaluate("()=>{window.mapKey('next');window.mapKey('next');window.mapKey('select');}")
        pw.expect(page.locator('body')).to_have_attribute('data-ready','cosmic')
        page.evaluate("()=>window.mapKey('next')")
        pw.expect(page.locator('#obs-progress')).to_have_value('80')
        assert page.evaluate('()=>window.collectionBack()')
        pw.expect(page.locator('#obs-hub')).to_be_visible()
        assert not page.evaluate('()=>window.collectionBack()')
        browser.close()
