"""A quiet local static file server, started only when a storyboard asks for one (`project.serve`)."""

from __future__ import annotations

import contextlib
import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):  # keep stderr for teaserkit's own progress
        pass


@contextlib.contextmanager
def serve_static(directory: str | Path, port: int = 0, host: str = "127.0.0.1") -> Iterator[str]:
    """Serve `directory` over HTTP for the duration of the block. Yields the base URL."""
    handler = functools.partial(_Quiet, directory=str(Path(directory).resolve()))
    httpd = ThreadingHTTPServer((host, port), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://{host}:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()
