"""Solar journeys are prepared once and completed movies bypass the encoder lock."""
from threading import Event

import numpy as np
from PIL import Image

from astroweb import solar_detail
from astroweb.jobs import JobQueue
from astroweb.media import import_object
from astroweb.store import Store


def test_first_film_prepares_details_and_restart_recovers_missing_files(tmp_path, monkeypatch):
    store = Store(tmp_path/"data")
    photo = tmp_path/"mars.png"
    Image.new("RGB",(160,180),"navy").save(photo)
    capture = import_object(store,"MARS",[photo])
    ready = Event()
    renders = []
    def encode(frames,credit,path):
        path.write_bytes(b"prepared detail")
        renders.append(credit)
        ready.set()
    monkeypatch.setattr(solar_detail,"mission_image",lambda *_:np.zeros((180,160,3),np.uint8))
    monkeypatch.setattr(solar_detail,"encode",encode)
    monkeypatch.setattr(JobQueue,"prepare_capture",lambda *_:None)
    monkeypatch.setattr(JobQueue,"prepare_journey",lambda *_:None)
    queue = JobQueue(store,resume=False)
    def render_capture():
        job = queue.submit(capture["id"],{"duration":4,"resolution":720})
        queue.futures[job["id"]].result(timeout=30)
        assert store.get("jobs",job["id"])["status"]=="completed"
    try:
        render_capture()
        assert ready.wait(10)
        queue.executor.submit(lambda:None).result(timeout=10)
        path,_ = solar_detail.movie_spec(store,capture,"PIA01167")
        assert path.read_bytes()==b"prepared detail"
        render_capture()
        queue.executor.submit(lambda:None).result(timeout=10)
        assert len(renders)==1
        with monkeypatch.context() as patch:
            patch.setattr(solar_detail,"LOCK",None)
            assert solar_detail.movie(store,capture,"PIA01167")==path
    finally:
        queue.shutdown()
    path.unlink()
    ready.clear()
    queue = JobQueue(store)
    try:
        assert ready.wait(10)
        queue.executor.submit(lambda:None).result(timeout=10)
        assert path.is_file() and len(renders)==2
    finally:
        queue.shutdown()


def test_preparation_skips_hidden_lunar_sites_and_cached_destinations(tmp_path,monkeypatch):
    from astroweb import surface_labels
    store = Store(tmp_path/"data")
    capture = dict(id="MOON",body="MOON",sha256={"final":"example"},capture_date="2026-11-21")
    cached,_ = solar_detail.movie_spec(store,capture,"moon-plato")
    cached.parent.mkdir(parents=True)
    cached.write_bytes(b"cached")
    monkeypatch.setattr(surface_labels,"lunar_points",lambda *_:[
        {"journey":"moon-plato"},{"journey":"moon-imbrium"}])
    assert solar_detail.missing_destinations(store,capture)==["moon-imbrium"]
