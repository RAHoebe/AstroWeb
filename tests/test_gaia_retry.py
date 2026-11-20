import threading
from astroweb import gaia
from astroweb.jobs import JobQueue
from astroweb.store import Store


def record(store, id='test', **gaia_state):
    value=dict(id=id,gaia=dict(status='unavailable',**gaia_state),assets={'stars':'s','stars_laid':'sl'},
               versions=[],video=None,metadata={},published=True,hst_search={'fields':['preserve']})
    store.put('objects',id,value)
    return value


def test_transient_failures_back_off_then_recover_without_archive_search(tmp_path,monkeypatch):
    store=Store(tmp_path);record(store)
    queue=JobQueue(store,resume=False)
    monkeypatch.setattr(gaia,'solve',lambda *a:dict(status='unavailable'))
    try:
        assert queue.retry_alignments(timestamp=100)
        queue.retry_future.result(timeout=5)
        first=store.get('objects','test')['gaia']
        assert first['retry_attempts']==1
        assert not queue.retry_alignments(timestamp=first['retry_after']-1)
        assert queue.retry_alignments(timestamp=first['retry_after']+1)
        queue.retry_future.result(timeout=5)
        second=store.get('objects','test')['gaia']
        assert second['retry_attempts']==2 and second['retry_after']>first['retry_after']+200
        monkeypatch.setattr(gaia,'solve',lambda *a:dict(status='solved',corners=['real matching output']))
        assert queue.retry_alignments(timestamp=second['retry_after']+1)
        queue.retry_future.result(timeout=5)
        assert store.get('objects','test')['gaia']['status']=='solved'
        assert store.get('objects','test')['hst_search']=={'fields':['preserve']}
        assert not queue.retry_alignments(timestamp=1e15)
    finally:queue.shutdown()


def test_repeated_page_requests_do_not_queue_duplicate_retries(tmp_path,monkeypatch):
    store=Store(tmp_path);record(store);record(store,'second')
    queue=JobQueue(store,resume=False);started=threading.Event();release=threading.Event()
    def solve(*args):
        started.set();release.wait(5);return dict(status='no_match')
    monkeypatch.setattr(gaia,'solve',solve)
    try:
        assert queue.retry_alignments()
        assert started.wait(2)
        assert not queue.retry_alignments()
        release.set();queue.retry_future.result(timeout=5)
        assert store.get('objects','test')['gaia']['status']=='unavailable'
    finally:release.set();queue.shutdown()


def test_retry_respects_render_priority_offline_mode_and_nontransient_failure(tmp_path,monkeypatch):
    store=Store(tmp_path);record(store);queue=JobQueue(store,resume=False)
    try:
        monkeypatch.setenv('ASTROWEB_OFFLINE','1')
        assert not queue.retry_alignments()
        monkeypatch.delenv('ASTROWEB_OFFLINE')
        store.put('jobs','active',dict(status='queued'))
        assert not queue.retry_alignments()
        store.update('jobs','active',status='completed')
        for state in ('solved','no_match','no_pointing'):
            store.update('objects','test',gaia=dict(status=state))
            assert not queue.retry_alignments()
    finally:queue.shutdown()


def test_retry_deadline_and_attempt_counter_survive_queue_restart(tmp_path,monkeypatch):
    store=Store(tmp_path);record(store,retry_after=2000,retry_attempts=3)
    queue=JobQueue(store,resume=False);queue.shutdown()
    monkeypatch.setattr(gaia,'solve',lambda *a:dict(status='unavailable'))
    reopened=JobQueue(store,resume=False)
    try:
        assert not reopened.retry_alignments(timestamp=1999)
        assert reopened.retry_alignments(timestamp=2001)
        reopened.retry_future.result(timeout=5)
        assert store.get('objects','test')['gaia']['retry_attempts']==4
    finally:reopened.shutdown()


def test_restart_keeps_interrupted_retry_separate_from_archive_discovery(tmp_path,monkeypatch):
    store=Store(tmp_path)
    capture=record(store,retry_after=2000,retry_attempts=3,retry_only=True)
    store.update('objects',capture['id'],gaia={**capture['gaia'],'status':'running'})
    discovery=[]
    monkeypatch.setattr(JobQueue,'prepare_capture',lambda *a:discovery.append(a))
    queue=JobQueue(store)
    try:
        state=store.get('objects',capture['id'])['gaia']
        assert state['status']=='unavailable'
        assert state['retry_after']==2000 and state['retry_attempts']==3
        assert not queue.retry_alignments(timestamp=1999)
    finally:queue.shutdown()
    assert not discovery
