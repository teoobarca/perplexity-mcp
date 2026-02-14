"""
Admin, pool management, and monitor routes (plain Starlette).
"""

import mimetypes
import pathlib

from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route

from .app import get_pool


# ==================== Health & Pool Status (no auth) ====================

async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint with pool summary."""
    pool = get_pool()
    status = pool.get_status()
    return JSONResponse({
        "status": "healthy",
        "service": "perplexity-mcp",
        "pool": {
            "total": status["total"],
            "available": status["available"],
        }
    })


async def pool_status(request: Request) -> JSONResponse:
    """Pool status endpoint returning detailed runtime state."""
    pool = get_pool()
    return JSONResponse(pool.get_status())


# ==================== Token Export/Import ====================

async def pool_export(request: Request) -> JSONResponse:
    """Export all token configurations."""
    pool = get_pool()
    return JSONResponse(pool.export_config())


async def pool_export_single(request: Request) -> JSONResponse:
    """Export a single token configuration."""
    client_id = request.path_params.get("client_id")
    pool = get_pool()
    return JSONResponse(pool.export_single_client(client_id))


async def pool_import(request: Request) -> JSONResponse:
    """Import token configurations (supports array format)."""
    pool = get_pool()
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({
            "status": "error",
            "message": "Invalid JSON body"
        }, status_code=400)

    return JSONResponse(pool.import_config(body))


# ==================== Pool Management API (for admin frontend) ====================

async def pool_api(request: Request) -> JSONResponse:
    """Pool management API endpoint for admin frontend."""
    action = request.path_params.get("action")
    pool = get_pool()

    try:
        body = await request.json()
    except Exception:
        body = {}

    client_id = body.get("id")
    csrf_token = body.get("csrf_token")
    session_token = body.get("session_token")

    if action == "list":
        return JSONResponse(pool.list_clients())
    elif action == "add":
        if not all([client_id, csrf_token, session_token]):
            return JSONResponse({"status": "error", "message": "Missing required parameters"})
        return JSONResponse(pool.add_client(client_id, csrf_token, session_token))
    elif action == "remove":
        if not client_id:
            return JSONResponse({"status": "error", "message": "Missing required parameter: id"})
        return JSONResponse(pool.remove_client(client_id))
    elif action == "enable":
        if not client_id:
            return JSONResponse({"status": "error", "message": "Missing required parameter: id"})
        return JSONResponse(pool.enable_client(client_id))
    elif action == "disable":
        if not client_id:
            return JSONResponse({"status": "error", "message": "Missing required parameter: id"})
        return JSONResponse(pool.disable_client(client_id))
    elif action == "reset":
        if not client_id:
            return JSONResponse({"status": "error", "message": "Missing required parameter: id"})
        return JSONResponse(pool.reset_client(client_id))
    elif action == "export":
        return JSONResponse(pool.export_config())
    elif action == "import":
        return JSONResponse(pool.import_config(body))
    else:
        return JSONResponse({"status": "error", "message": f"Unknown action: {action}"})


# ==================== Admin Static Files ====================

async def admin_page(request: Request):
    """Admin page - redirect to /admin/."""
    return RedirectResponse(url="/admin/", status_code=302)


async def admin_page_index(request: Request):
    """Admin page entry point."""
    dist_path = pathlib.Path(__file__).parent / "web" / "dist" / "index.html"
    return FileResponse(dist_path, media_type="text/html")


async def admin_static(request: Request):
    """Serve static asset files."""
    path = request.path_params.get("path", "")
    dist_dir = pathlib.Path(__file__).parent / "web" / "dist"
    file_path = dist_dir / path

    # Security check: ensure path is within dist directory
    try:
        file_path = file_path.resolve()
        dist_dir = dist_dir.resolve()
        if not str(file_path).startswith(str(dist_dir)):
            return Response("Forbidden", status_code=403)
    except Exception:
        return Response("Bad Request", status_code=400)

    # If file exists, return it
    if file_path.is_file():
        mime_type, _ = mimetypes.guess_type(str(file_path))
        return FileResponse(file_path, media_type=mime_type or "application/octet-stream")

    # For SPA routes, return index.html
    index_path = dist_dir / "index.html"
    if index_path.is_file():
        return FileResponse(index_path, media_type="text/html")

    return Response("Not Found", status_code=404)


# ==================== Monitor API ====================

async def monitor_config(request: Request) -> JSONResponse:
    """Get or update monitor configuration."""
    if request.method == "GET":
        pool = get_pool()
        return JSONResponse({
            "status": "ok",
            "config": pool.get_monitor_config()
        })

    # POST: update config
    pool = get_pool()
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({
            "status": "error",
            "message": "Invalid JSON body"
        }, status_code=400)

    result = pool.update_monitor_config(body)

    # Send Telegram notification if configured
    if result.get("status") == "ok":
        config = result.get("config", {})
        if config.get("tg_bot_token") and config.get("tg_chat_id"):
            await pool._send_telegram_notification("Perplexity config updated")

    return JSONResponse(result)


async def monitor_start(request: Request) -> JSONResponse:
    """Start monitor background task."""
    pool = get_pool()
    started = pool.start_monitor()
    if started:
        return JSONResponse({"status": "ok", "message": "Monitor started"})
    elif not pool.is_monitor_enabled():
        return JSONResponse({"status": "error", "message": "Monitor is disabled in config"})
    else:
        return JSONResponse({"status": "ok", "message": "Monitor already running"})


async def monitor_stop(request: Request) -> JSONResponse:
    """Stop monitor background task."""
    pool = get_pool()
    stopped = pool.stop_monitor()
    if stopped:
        return JSONResponse({"status": "ok", "message": "Monitor stopped"})
    else:
        return JSONResponse({"status": "ok", "message": "Monitor not running"})


async def monitor_test(request: Request) -> JSONResponse:
    """Trigger manual health check."""
    pool = get_pool()
    try:
        body = await request.json()
    except Exception:
        body = {}

    client_id = body.get("id")

    if client_id:
        # Test specific client
        result = await pool.test_client(client_id)
        pool.save_state(writer="monitor")
        return JSONResponse(result)
    else:
        # Test all clients (test_all_clients already calls save_state)
        result = await pool.test_all_clients()
        return JSONResponse(result)


# ==================== Fallback API ====================

async def fallback_config(request: Request) -> JSONResponse:
    """Get or update fallback configuration."""
    if request.method == "GET":
        pool = get_pool()
        return JSONResponse({
            "status": "ok",
            "config": pool.get_fallback_config()
        })

    # POST: update config
    pool = get_pool()
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({
            "status": "error",
            "message": "Invalid JSON body"
        }, status_code=400)

    result = pool.update_fallback_config(body)
    return JSONResponse(result)


# ==================== Logs API ====================

def _tail_file(filepath, n: int = 100) -> tuple[list[str], int, int]:
    """Efficiently read the last n lines of a file."""
    if not filepath.exists():
        raise FileNotFoundError(f"Log file not found: {filepath}")

    file_size = filepath.stat().st_size
    if file_size == 0:
        return [], 0, 0

    lines = []
    with open(filepath, "rb") as f:
        # Read backwards from end of file
        buffer_size = 8192
        remaining = file_size
        buffer = b""

        while remaining > 0 and len(lines) <= n:
            read_size = min(buffer_size, remaining)
            remaining -= read_size
            f.seek(remaining)
            chunk = f.read(read_size)
            buffer = chunk + buffer
            lines = buffer.decode("utf-8", errors="replace").splitlines()

    # Total lines is approximate to avoid reading entire file
    total_lines = len(lines)

    return lines[-n:], total_lines, file_size


async def logs_tail(request: Request) -> JSONResponse:
    """Get last N lines of log file."""
    from perplexity.config import LOG_FILE

    # Get requested line count, default 100, max 1000
    try:
        lines_param = request.query_params.get("lines", "100")
        num_lines = min(int(lines_param), 1000)
    except ValueError:
        num_lines = 100

    # Read log file
    log_path = pathlib.Path(LOG_FILE)
    try:
        lines, total_lines, file_size = _tail_file(log_path, num_lines)
        return JSONResponse({
            "status": "ok",
            "lines": lines,
            "total_lines": total_lines,
            "file_size": file_size
        })
    except FileNotFoundError as e:
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=404)


# ==================== Route Table ====================

routes = [
    Route("/health", health_check, methods=["GET"]),
    Route("/pool/status", pool_status, methods=["GET"]),
    Route("/pool/export", pool_export, methods=["GET"]),
    Route("/pool/export/{client_id:path}", pool_export_single, methods=["GET"]),
    Route("/pool/import", pool_import, methods=["POST"]),
    Route("/pool/{action}", pool_api, methods=["POST"]),
    Route("/admin", admin_page, methods=["GET"]),
    Route("/admin/", admin_page_index, methods=["GET"]),
    Route("/admin/{path:path}", admin_static, methods=["GET"]),
    Route("/monitor/config", monitor_config, methods=["GET", "POST"]),
    Route("/monitor/start", monitor_start, methods=["POST"]),
    Route("/monitor/stop", monitor_stop, methods=["POST"]),
    Route("/monitor/test", monitor_test, methods=["POST"]),
    Route("/fallback/config", fallback_config, methods=["GET", "POST"]),
    Route("/logs/tail", logs_tail, methods=["GET"]),
]
