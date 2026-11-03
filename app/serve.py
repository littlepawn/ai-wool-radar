"""Serve the static page with the Python standard library.

The page is a single hand-maintained index.html at the repository root, with
assets (icons) in assets/. If that file is missing we fall back to the
generated dist/ directory, keeping `python3 app/generate.py` + serve usable.

Python stdlib only. Usage: python3 app/serve.py [port, default 8080]
Bind address defaults to 0.0.0.0; set HOST to restrict it (e.g. a Tailscale IP).
"""
import os
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# Only these top-level entries are exposed; source (app/), data (data/),
# state/ and every dotfile stay private even though the docroot is the repo.
PUBLIC_DIRS = ("assets",)
PUBLIC_FILES = ("index.html", "icon.svg", "icon-128.png", "icon-512.png",
                "favicon.ico", "robots.txt")


class Handler(SimpleHTTPRequestHandler):
    """Serve only the page and its assets; never source, data or dotfiles."""

    def list_directory(self, path):
        self.send_error(404, "Not found")
        return None

    def send_head(self):
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        rel = path.lstrip("/")
        if rel.startswith(".") or "/." in rel:
            self.send_error(404, "Not found")
            return None
        if path == "/":
            pass
        else:
            parts = [p for p in rel.split("/") if p]
            if not parts:
                self.send_error(404, "Not found")
                return None
            if len(parts) > 1 and parts[0] not in PUBLIC_DIRS:
                self.send_error(404, "Not found")
                return None
            if len(parts) == 1 and parts[0] not in PUBLIC_FILES:
                self.send_error(404, "Not found")
                return None
        return super().send_head()

    def log_message(self, fmt, *args):
        pass


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", "8080"))
    if (ROOT / "index.html").exists():
        docroot = ROOT
    else:
        dist = ROOT / "dist"
        if not (dist / "index.html").exists():
            sys.path.insert(0, str(ROOT))
            from app.generate import main as generate
            generate()
        docroot = dist
    host = os.environ.get("HOST", "0.0.0.0")
    server = ThreadingHTTPServer((host, port), partial(Handler, directory=str(docroot)))
    print(f"serving {docroot} on http://{host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
