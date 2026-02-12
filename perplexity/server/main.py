"""
Main entry point for Perplexity HTTP server.
Uses uvicorn to serve the Starlette admin app.
"""

import argparse

# Initialize logging before importing other modules
from ..logger import setup_logger
setup_logger()

from .app import app, get_pool


def run_server(
    host: str = "0.0.0.0",
    port: int = 8123,
) -> None:
    """Start the HTTP server with uvicorn."""
    import webbrowser
    import threading
    import uvicorn

    # Initialize the pool on startup
    get_pool()

    # Open admin panel in browser after server starts
    def open_browser():
        import time
        time.sleep(0.8)
        webbrowser.open(f"http://127.0.0.1:{port}/admin/")

    threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run(app, host=host, port=port)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Perplexity HTTP server.")
    parser.add_argument("--host", default="0.0.0.0", help="HTTP host.")
    parser.add_argument("--port", type=int, default=8123, help="HTTP port.")
    args = parser.parse_args()
    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
