"""netfast.py -- a latency-tuned requests.Session for the hot path (book reads, order POSTs).

The defaults in requests are fine for scraping but leave latency on the table for trading:
  * keep-alive is on, but the pool is tiny and a stale socket forces a fresh TCP+TLS (~1.5 RTTs).
  * urllib3 sets TCP_NODELAY by default, but we also want SO_KEEPALIVE so the kernel keeps the
    warm connection from being silently dropped between bursts (a dropped socket = a cold reconnect
    on the very next order, exactly when you can least afford it).
  * default retries add hidden latency/backoff on a blip; for a maker you want FAIL-FAST and to
    re-decide on the next loop, not a silent multi-second retry storm.

This makes those explicit. It does NOT cross regions for you -- co-locate in eu-west-2 (see DEPLOY.md);
this just removes the per-request overhead so a warm request is one origin RTT, not three.
"""
from __future__ import annotations

import socket

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# TCP_NODELAY (Nagle off -> don't coalesce/delay our tiny order frames) + SO_KEEPALIVE (hold the
# warm connection open between bursts so the next order reuses it instead of a cold TCP+TLS).
_SOCKOPTS = [
    (socket.IPPROTO_TCP, socket.TCP_NODELAY, 1),
    (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1),
]


class _FastAdapter(HTTPAdapter):
    def init_poolmanager(self, *a, **kw):
        kw["socket_options"] = _SOCKOPTS
        super().init_poolmanager(*a, **kw)


def fast_session(pool: int = 16, retries: int = 0) -> requests.Session:
    """A keep-alive Session with NODELAY+KEEPALIVE sockets, a warm pool, and (by default) no retries
    so a blip fails fast and the caller re-decides next loop rather than blocking on backoff."""
    s = requests.Session()
    r = Retry(total=retries, connect=retries, read=retries, backoff_factor=0, respect_retry_after_header=False)
    ad = _FastAdapter(pool_connections=pool, pool_maxsize=pool, max_retries=r)
    s.mount("https://", ad)
    s.mount("http://", ad)
    return s
