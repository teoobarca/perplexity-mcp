# Importing necessary modules
# re: Regular expressions for pattern matching
# sys: System-specific parameters and functions
# json: JSON parsing and serialization
# random: Random number generation
# mimetypes: Guessing MIME types of files
# uuid: Generating unique identifiers
# curl_cffi: HTTP requests and multipart form data handling
import re
import sys
import json
import time
import random
import mimetypes
from uuid import uuid4

# Try importing curl_cffi, but allow it to fail for testing environments
# that mock the requests anyway
try:
    from curl_cffi import CurlMime, requests
except ImportError:
    # Minimal stub for testing if curl_cffi is missing
    class requests:
        class Session:
            def __init__(self, *args, **kwargs): pass
            def get(self, *args, **kwargs): pass
            def post(self, *args, **kwargs): pass

    class CurlMime:
        def __init__(self, *args, **kwargs): pass
        def addpart(self, *args, **kwargs): pass

from .config import (
    DEFAULT_HEADERS,
    ENDPOINT_AUTH_SESSION,
    ENDPOINT_RATE_LIMIT,
    ENDPOINT_RATE_LIMIT_STATUS,
    ENDPOINT_SSE_ASK,
    ENDPOINT_UPLOAD_URL,
    MODEL_MAPPINGS,
    SOCKS_PROXY,
)
from .exceptions import ValidationError
from .logger import get_logger

logger = get_logger("client")
class Client:
    """
    A client for interacting with the Perplexity AI API.
    """

    def __init__(self, cookies=None):
        # Build proxy configuration from SOCKS_PROXY env var
        # Format: socks5://[user[:pass]@]host[:port][#remark]
        proxy_url = None
        if SOCKS_PROXY:
            # Remove the remark part (after #) if present
            proxy_url = SOCKS_PROXY.split("#")[0] if "#" in SOCKS_PROXY else SOCKS_PROXY

        if cookies is None:
            cookies = {}

        # Store original cookies for export
        self._cookies = cookies.copy()

        # Initialize an HTTP session with default headers and optional cookies
        self.session = requests.Session(
            headers=DEFAULT_HEADERS.copy(),
            cookies=cookies,
            impersonate="chrome",
            proxy=proxy_url,
        )

        # Flags and counters for account and query management
        self.own = bool(cookies)  # Indicates if the client uses its own account
        self.copilot = 0 if not cookies else float("inf")  # Remaining pro queries
        self.file_upload = 0 if not cookies else float("inf")  # Remaining file uploads

        # Unique timestamp for session identification
        self.timestamp = format(random.getrandbits(32), "08x")

        # Initialize session by making a GET request
        self.session.get(ENDPOINT_AUTH_SESSION, timeout=30)

    @property
    def cookies(self) -> dict:
        """
        Get the current cookies from the session.
        """
        if hasattr(self.session, "cookies") and hasattr(self.session.cookies, "get_dict"):
            return self.session.cookies.get_dict()
        return self._cookies

    def get_user_info(self) -> dict:
        """
        Get user session information from the auth session endpoint.

        Returns:
            dict: User session info including user details if logged in,
                  or empty dict if anonymous/not logged in.
        """
        try:
            resp = self.session.get(ENDPOINT_AUTH_SESSION, timeout=30)
            if resp.ok:
                return resp.json()
            return {}
        except Exception:
            return {}

    def get_rate_limits(self) -> dict:
        """
        Fetch real quota info from Perplexity rate-limit APIs.

        Returns:
            dict with pro_remaining and per-mode quota details:
            {
                "pro_remaining": 600,
                "modes": {
                    "pro_search": {"available": True, "remaining": None, "kind": "not_provided"},
                    "research": {"available": True, "remaining": 1, "kind": "exact"},
                    ...
                }
            }
        """
        result = {}

        try:
            resp = self.session.get(
                ENDPOINT_RATE_LIMIT,
                params={"version": "2.18", "source": "default"},
                timeout=15,
            )
            if resp.ok:
                result["pro_remaining"] = resp.json().get("remaining")
        except Exception:
            pass

        try:
            resp2 = self.session.get(
                ENDPOINT_RATE_LIMIT_STATUS,
                params={"version": "2.18", "source": "default"},
                timeout=15,
            )
            if resp2.ok:
                data = resp2.json()
                modes = data.get("modes", {})
                result["modes"] = {}
                for mode_name, mode_data in modes.items():
                    result["modes"][mode_name] = {
                        "available": mode_data.get("available", False),
                        "remaining": mode_data.get("remaining_detail", {}).get("remaining"),
                        "kind": mode_data.get("remaining_detail", {}).get("kind"),
                    }
        except Exception:
            pass

        return result

    def _validate_research_response(self, response: dict) -> None:
        """Verify the response is actually a deep research result, not a silent downgrade."""
        text = response.get("text")
        if isinstance(text, str) or text is None:
            logger.warning(
                "Deep research downgrade detected: text type=%s, response_keys=%s",
                type(text).__name__, list(response.keys()),
            )
            raise Exception(
                "Deep research was silently downgraded to a regular search by the server. "
                "This account may not have research quota remaining."
            )

    def search(
        self,
        query,
        mode="auto",
        sources=None,
        files=None,
        stream=False,
        language="en-US",
        follow_up=None,
        incognito=False,
    ):
        """
        Executes a search query on Perplexity AI.

        Parameters:
        - query: The search query string.
        - mode: Search mode ('auto', 'pro', 'reasoning', 'deep research').
        - sources: List of sources ('web', 'scholar', 'social').
        - files: Dictionary of files to upload.
        - stream: Whether to stream the response.
        - language: Language code (ISO 639).
        - follow_up: Information for follow-up queries.
        - incognito: Whether to enable incognito mode.
        """
        if sources is None:
            sources = ["web"]
        if files is None:
            files = {}

        # Validate input parameters
        valid_modes = ("auto", "pro", "reasoning", "deep research")
        if mode not in valid_modes:
            raise ValidationError(f"Invalid search mode '{mode}'. Choose from: {', '.join(valid_modes)}")

        if not all(source in ("web", "scholar", "social") for source in sources):
            raise ValidationError("Invalid sources. Choose from: web, scholar, social")

        if mode in ("pro", "reasoning", "deep research") and self.copilot <= 0:
            raise ValidationError("No remaining pro queries.")

        if files and self.file_upload - len(files) < 0:
            raise ValidationError("File upload limit exceeded.")

        # Update query and file upload counters
        self.copilot = (
            self.copilot - 1 if mode in ["pro", "reasoning", "deep research"] else self.copilot
        )
        self.file_upload = self.file_upload - len(files) if files else self.file_upload

        # Upload files and prepare the query payload
        uploaded_files = []
        for filename, file in files.items():
            file_type = mimetypes.guess_type(filename)[0]
            file_upload_info = (
                self.session.post(
                    ENDPOINT_UPLOAD_URL,
                    params={"version": "2.18", "source": "default"},
                    json={
                        "content_type": file_type,
                        "file_size": sys.getsizeof(file),
                        "filename": filename,
                        "force_image": False,
                        "source": "default",
                    },
                    timeout=30,
                )
            ).json()

            # Upload the file to the server
            mp = CurlMime()
            for key, value in file_upload_info["fields"].items():
                mp.addpart(name=key, data=value)
            mp.addpart(
                name="file",
                content_type=file_type,
                filename=filename,
                data=file,
            )

            upload_resp = self.session.post(file_upload_info["s3_bucket_url"], multipart=mp, timeout=120)

            if not upload_resp.ok:
                raise Exception("File upload error", upload_resp)

            # Extract the uploaded file URL
            if "image/upload" in file_upload_info["s3_object_url"]:
                uploaded_url = re.sub(
                    r"/private/s--.*?--/v\\d+/user_uploads/",
                    "/private/user_uploads/",
                    upload_resp.json()["secure_url"],
                )
            else:
                uploaded_url = file_upload_info["s3_object_url"]

            uploaded_files.append(uploaded_url)

        # Prepare the JSON payload for the query
        json_data = {
            "query_str": query,
            "params": {
                "attachments": (
                    uploaded_files + follow_up["attachments"] if follow_up else uploaded_files
                ),
                "frontend_context_uuid": str(uuid4()),
                "frontend_uuid": str(uuid4()),
                "is_incognito": incognito,
                "language": language,
                "last_backend_uuid": (follow_up["backend_uuid"] if follow_up else None),
                "mode": "concise" if mode == "auto" else "copilot",
                "model_preference": MODEL_MAPPINGS[mode],
                "source": "default",
                "sources": sources,
                "version": "2.18",
            },
        }

        # Send the query request and handle the response
        logger.info(
            "Search request: mode=%s, sources=%s, query=%.200s",
            mode, sources, query,
        )

        resp = self.session.post(ENDPOINT_SSE_ASK, json=json_data, stream=True, timeout=120)
        logger.debug("SSE response status: %s", resp.status_code)
        chunks = []

        def _parse_sse_event(content_json, event_num):
            """Parse nested text field, extract answer and research report from steps."""
            if "text" not in content_json or not content_json["text"]:
                return
            try:
                text_parsed = json.loads(content_json["text"])
                if isinstance(text_parsed, list):
                    logger.debug(
                        "SSE #%d: %d steps, types=%s", event_num, len(text_parsed),
                        [s.get("step_type") for s in text_parsed if isinstance(s, dict)],
                    )
                    for step in text_parsed:
                        step_type = step.get("step_type") if isinstance(step, dict) else None

                        if step_type == "RESEARCH_ANSWER":
                            # Deep research report lives in assets[0].research_report
                            for asset in step.get("assets", []):
                                report = asset.get("research_report", {})
                                src = report.get("source_content", "")
                                if src:
                                    content_json["research_report"] = src
                                    content_json["research_title"] = report.get("name", "")
                                    logger.info(
                                        "RESEARCH_ANSWER: title=%r, report=%d chars",
                                        report.get("name"), len(src),
                                    )

                        elif step_type == "FINAL":
                            final_content = step.get("content", {})
                            if "answer" in final_content:
                                answer_data = json.loads(final_content["answer"])
                                content_json["answer"] = answer_data.get("answer", "")
                                content_json["chunks"] = answer_data.get("chunks", [])
                                content_json["web_results"] = answer_data.get("web_results", [])
                                logger.debug(
                                    "FINAL step: answer_len=%d, chunks=%d, web_results=%d",
                                    len(content_json["answer"]),
                                    len(content_json["chunks"]),
                                    len(content_json["web_results"]),
                                )

                content_json["text"] = text_parsed
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                logger.warning(
                    "Failed to parse text field in SSE #%d: %s. "
                    "text type=%s, preview=%.300s",
                    event_num, e,
                    type(content_json.get("text")).__name__,
                    str(content_json.get("text", ""))[:300],
                )

        def stream_response(resp):
            """Generator for streaming responses."""
            event_num = 0
            for chunk in resp.iter_lines(delimiter=b"\r\n\r\n"):
                content = chunk.decode("utf-8")

                if content.startswith("event: message\r\n"):
                    try:
                        content_json = json.loads(content[len("event: message\r\ndata: ") :])
                        event_num += 1
                        _parse_sse_event(content_json, event_num)
                        chunks.append(content_json)
                        yield chunks[-1]
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning("Failed to parse SSE event JSON: %s, raw=%.200s", e, content[:200])
                        continue

                elif content.startswith("event: end_of_stream\r\n"):
                    return

        if stream:
            return stream_response(resp)

        t_start = time.time()
        event_count = 0
        step_types_seen = []

        for chunk in resp.iter_lines(delimiter=b"\r\n\r\n"):
            content = chunk.decode("utf-8")

            if content.startswith("event: message\r\n"):
                try:
                    content_json = json.loads(content[len("event: message\r\ndata: ") :])
                    event_count += 1
                    _parse_sse_event(content_json, event_count)

                    # Track step types for journal
                    if isinstance(content_json.get("text"), list):
                        for step in content_json["text"]:
                            if isinstance(step, dict) and step.get("step_type"):
                                st = step["step_type"]
                                if st not in step_types_seen:
                                    step_types_seen.append(st)

                    chunks.append(content_json)
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning("Failed to parse SSE event JSON: %s, raw=%.200s", e, content[:200])
                    continue

            elif content.startswith("event: end_of_stream\r\n"):
                duration_ms = (time.time() - t_start) * 1000
                result = chunks[-1] if chunks else {}

                if not chunks:
                    logger.warning("Search returned 0 chunks — response may be empty or format changed")

                logger.info(
                    "Search complete: %.0fms, %d events, %d chunks, answer=%s, keys=%s, steps=%s",
                    duration_ms, event_count, len(chunks),
                    "yes(%d)" % len(result.get("answer", "")) if "answer" in result else "NO",
                    list(result.keys()) if result else [],
                    step_types_seen,
                )

                # Store metadata for journal (consumed by app.py)
                if result:
                    result["_meta"] = {
                        "duration_ms": duration_ms,
                        "sse_event_count": event_count,
                        "step_types": step_types_seen,
                        "chunk_count": len(chunks),
                    }

                if mode == "deep research" and result:
                    self._validate_research_response(result)
                return result
