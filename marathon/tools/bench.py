#!/usr/bin/env python3
"""Drive the remote bench (remote-bench.js) from anywhere: send a command, print the band's answer.

    python3 bench.py TOPIC ping
    python3 bench.py TOPIC hr '{"seconds": 20}'
    python3 bench.py TOPIC selftest
    python3 bench.py TOPIC listen          # everything the phone has said in the last hour

TOPIC is the name after `#bench=` in the link opened on the phone. Commands: ping, state, log, hr,
battery, acc, selftest, ppi, offline ({"op": "status|start|stop"}), recordings, disk, fetch-hr,
resubscribe, rebuild, settings ({"meas": 2|3}). The phone answers within about 6 s of a command
arriving, plus however long the command takes (selftest about 75 s, ppi up to 90 s).

Standard library only; honours https_proxy like everything else here.
"""
import json
import sys
import time
import urllib.request
import uuid

RELAY = "https://ntfy.sh"


def _get(url, timeout=30):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read().decode()


def _post(url, body):
    req = urllib.request.Request(url, data=body.encode(), method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def replies(topic, since):
    """Every reply part published on <topic>-out since `since`, as dicts."""
    out = []
    for line in _get(f"{RELAY}/{topic}-out/json?poll=1&since={since}").splitlines():
        try:
            ev = json.loads(line)
            if ev.get("event") == "message":
                out.append(json.loads(ev["message"]))
        except (ValueError, KeyError):
            continue
    return out


def join(parts, cid):
    mine = sorted((p for p in parts if p.get("id") == cid), key=lambda p: p["part"])
    if not mine or len({p["part"] for p in mine}) < mine[0]["of"]:
        return None
    return json.loads("".join(p["data"] for p in mine))


def send(topic, cmd, args=None, timeout=180):
    cid = uuid.uuid4().hex[:12]
    since = int(time.time()) - 1
    _post(f"{RELAY}/{topic}-cmd", json.dumps({"id": cid, "cmd": cmd, "args": args or {}}))
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(4)
        got = join(replies(topic, since), cid)
        if got is not None:
            return got
    return {"id": cid, "ok": False, "error": f"no answer in {timeout} s - is the page open, bench allowed, screen on?"}


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    topic, cmd = argv[1], argv[2]
    if cmd == "listen":
        for p in replies(topic, "1h"):
            print(json.dumps(p)[:400])
        return 0
    args = json.loads(argv[3]) if len(argv) > 3 else {}
    timeout = 240 if cmd in ("selftest", "ppi", "rebuild") else 120
    r = send(topic, cmd, args, timeout=timeout)
    print(json.dumps(r, indent=1))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
