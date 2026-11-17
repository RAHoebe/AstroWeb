"""Container termination must close the server and the durable render worker."""
import signal
import sys
from types import SimpleNamespace

import pytest
import waitress

from astroweb import __main__, app


@pytest.mark.parametrize("terminate", [True, False])
def test_serve_closes_worker_and_restores_signal_handler(monkeypatch, terminate):
    events = []
    previous = object()
    handlers = []

    def install(signum, handler):
        assert signum == signal.SIGTERM
        handlers.append(handler)
        return previous

    def serve(*args, **kwargs):
        events.append("serve")
        if terminate:
            handlers[0](signal.SIGTERM, None)

    worker = SimpleNamespace(shutdown=lambda: events.append("shutdown"))
    monkeypatch.setattr(app, "create_app", lambda: SimpleNamespace(extensions={"jobs": worker}))
    monkeypatch.setattr(waitress, "serve", serve)
    monkeypatch.setattr(signal, "signal", install)
    monkeypatch.setattr(sys, "argv", ["astroweb", "serve"])
    __main__.main()
    assert events == ["serve", "shutdown"]
    assert handlers[-1] is previous
