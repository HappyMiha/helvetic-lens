"""Optional loopback server for synthetic fixtures; no third-party dependencies."""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    directory = Path(__file__).resolve().parents[1] / "demo"
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"Synthetic demo source: http://127.0.0.1:{args.port}/index.html")
    print(
        "Use ALLOW_PRIVATE_SOURCES=true only in your local test API to fetch this loopback source."
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
