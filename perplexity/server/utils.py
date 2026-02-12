"""
Utility functions for Perplexity server module.

This module provides helper functions for validation
and other common operations used by the server.
"""

from typing import Any, Dict, List, Optional, Tuple

try:
    from ..exceptions import ValidationError
    from ..config import (
        SEARCH_MODES,
        SEARCH_SOURCES,
        MODEL_MAPPINGS,
    )
except ImportError:
    from perplexity.exceptions import ValidationError
    from perplexity.config import (
        SEARCH_MODES,
        SEARCH_SOURCES,
        MODEL_MAPPINGS,
    )


# ==================== Validation Functions ====================

def validate_search_params(
    mode: str, model: Optional[str], sources: list, own_account: bool = False
) -> None:
    """
    Validate search parameters.

    Args:
        mode: Search mode
        model: Model name (optional)
        sources: List of sources
        own_account: Whether using own account

    Raises:
        ValidationError: If parameters are invalid

    Example:
        >>> validate_search_params("pro", "gpt-4.5", ["web"], True)
    """
    # Validate mode - guard against None SEARCH_MODES
    if SEARCH_MODES is None or mode not in SEARCH_MODES:
        valid_modes = ', '.join(SEARCH_MODES) if SEARCH_MODES else "auto, pro, reasoning, deep research"
        raise ValidationError(f"Invalid mode '{mode}'. Must be one of: {valid_modes}")

    # Validate model - guard against None MODEL_MAPPINGS
    if model is not None:
        if MODEL_MAPPINGS is None:
            valid_models = [None]
        else:
            valid_models = list(MODEL_MAPPINGS.get(mode, {}).keys())
        if model not in valid_models:
            raise ValidationError(
                f"Invalid model '{model}' for mode '{mode}'. "
                f"Valid models: {', '.join(str(m) for m in valid_models)}"
            )

    # Check if model requires own account
    if model is not None and not own_account:
        raise ValidationError(
            "Model selection requires an account with cookies. "
            "Initialize Client with cookies parameter."
        )

    # Validate sources - guard against None SEARCH_SOURCES
    if SEARCH_SOURCES is None:
        valid_sources_list = ["web", "scholar", "social"]
    else:
        valid_sources_list = SEARCH_SOURCES
    invalid_sources = [s for s in sources if s not in valid_sources_list]
    if invalid_sources:
        raise ValidationError(
            f"Invalid sources: {', '.join(invalid_sources)}. "
            f"Valid sources: {', '.join(valid_sources_list)}"
        )

    if not sources:
        raise ValidationError("At least one source must be specified")


def validate_query_limits(
    copilot_remaining: int,
    file_upload_remaining: int,
    mode: str,
    files_count: int,
) -> None:
    """
    Validate query and file upload limits.

    Args:
        copilot_remaining: Remaining copilot queries
        file_upload_remaining: Remaining file uploads
        mode: Search mode
        files_count: Number of files to upload

    Raises:
        ValidationError: If limits are exceeded

    Example:
        >>> validate_query_limits(5, 10, "pro", 2)
    """
    # Check copilot queries
    if mode in ["pro", "reasoning", "deep research"] and copilot_remaining <= 0:
        raise ValidationError(
            f"No remaining enhanced queries for mode '{mode}'. "
            f"Create a new account or use mode='auto'."
        )

    # Check file uploads
    if files_count > 0 and file_upload_remaining < files_count:
        raise ValidationError(
            f"Insufficient file uploads. Requested: {files_count}, "
            f"Available: {file_upload_remaining}"
        )


def validate_file_data(files: dict) -> None:
    """
    Validate file data dictionary.

    Args:
        files: Dictionary with filenames as keys and file data as values

    Raises:
        ValidationError: If file data is invalid

    Example:
        >>> validate_file_data({"doc.pdf": b"..."})
    """
    if not isinstance(files, dict):
        raise ValidationError("Files must be a dictionary")

    for filename, data in files.items():
        if not isinstance(filename, str):
            raise ValidationError(f"Filename must be string, got {type(filename)}")

        if not filename.strip():
            raise ValidationError("Filename cannot be empty")

        if not isinstance(data, (bytes, str)):
            raise ValidationError(f"File data must be bytes or string, got {type(data)}")


def sanitize_query(query: str) -> str:
    """
    Sanitize and validate query string.

    Args:
        query: Query string

    Returns:
        Sanitized query string

    Raises:
        ValidationError: If query is invalid

    Example:
        >>> sanitize_query("  What is AI?  ")
        'What is AI?'
    """
    if not isinstance(query, str):
        raise ValidationError(f"Query must be string, got {type(query)}")

    query = query.strip()

    if not query:
        raise ValidationError("Query cannot be empty")

    if len(query) > 10000:
        raise ValidationError("Query is too long (max 10000 characters)")

    return query
