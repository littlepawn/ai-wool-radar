"""Serve the generated static page. Generates dist/index.html on startup
if it is missing, then serves the dist/ directory with the stdlib server.

Python stdlib only. Usage: python3 app/serve.py [port, default 8080]
"""
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", "8080"))
    dist = ROOT / "dist"
    if not (dist / "index.html").exists():
        sys.path.insert(0, str(ROOT))
        from app.generate import main as generate
        generate()
    os.chdir(dist)
    server = ThreadingHTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    print(f"serving {dist} on http://0.0.0.0:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
