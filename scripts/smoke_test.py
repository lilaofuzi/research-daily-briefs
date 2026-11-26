"""Check a generated site over HTTP, including nested project URL deployment."""
import argparse
import functools
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen


def verify(base):
    def get(path):
        with urlopen(base.rstrip("/") + "/" + path, timeout=20) as r:
            if r.status != 200:
                raise AssertionError("Unexpected HTTP status")
            return r.read().decode("utf-8")
    assert "科研简报归档馆" in get("")
    for asset in ("app.mjs", "core.mjs", "styles.css"):
        assert get(asset).strip()
    index = json.loads(get("data/index.json"))
    papers = json.loads(get("data/papers.json"))
    assert index["schema_version"] == papers["schema_version"] == 1
    by_id = {p["id"]: p for p in papers["papers"]}
    for record in index["briefs"]:
        brief = json.loads(get(record["path"]))
        assert brief["date"] == record["date"]
        assert [p["id"] for p in brief["items"]] == record["paper_ids"]
        assert all(pid in by_id for pid in record["paper_ids"])
        for v in record["versions"]:
            assert json.loads(get(v["path"]))["date"] == record["date"]
    print(f"HTTP smoke passed: {len(index['briefs'])} briefs, {len(papers['papers'])} unique metadata records")


def local(directory):
    directory = Path(directory).resolve()
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass
    # Serving the parent verifies relative asset paths at /dist/, as on project Pages.
    handler = functools.partial(QuietHandler, directory=str(directory.parent))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        verify(f"http://127.0.0.1:{server.server_port}/{directory.name}/")
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--url")
    args = parser.parse_args()
    if args.directory:
        local(args.directory)
    elif args.url:
        verify(args.url)
    else:
        parser.error("--directory or --url required")
