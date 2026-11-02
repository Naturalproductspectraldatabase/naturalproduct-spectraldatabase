"""Small, offline-safe pagination helpers for both NPDB NMR spectrum galleries.

No database, network, browser JavaScript or Streamlit dependency. Source-of-
truth page state uses one canonical number per nucleus; controls at the top
and bottom are synchronized through Streamlit's on_change/on_click callbacks.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any


def bounded_page(requested: Any, total_pages: int) -> int:
    """Return a valid integer page in [1, total_pages]."""
    last_page = max(1, int(total_pages))
    try:
        page = int(requested)
    except (TypeError, ValueError, OverflowError):
        return 1
    return max(1, min(page, last_page))


def pagination_window(total_records: int, page_size: int, page_number: int) -> tuple[int, int, int]:
    """Return the zero-based half-open slice and total page count."""
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    total = max(0, int(total_records))
    pages = max(1, (total + page_size - 1) // page_size)
    page = bounded_page(page_number, pages)
    start = (page - 1) * page_size
    end = min(start + page_size, total)
    return start, end, pages


def set_gallery_page(state: MutableMapping[str, Any], prefix: str, target: Any, total_pages: int) -> int:
    """Synchronize canonical page and two widgets; only affects session state."""
    page = bounded_page(target, total_pages)
    state[f"{prefix}_page"] = page
    state[f"{prefix}_top_jump"] = page
    state[f"{prefix}_bottom_jump"] = page
    return page


def apply_gallery_criteria(
    state: MutableMapping[str, Any],
    *,
    prefix: str,
    search_text: str,
    page_size: int,
    total_pages: int,
) -> int:
    """Reset page on a search/size change; clamp after result-count changes."""
    signature = (str(search_text or "").strip().casefold(), int(page_size))
    key = f"{prefix}_filter_signature"
    if state.get(key) != signature:
        state[key] = signature
        return set_gallery_page(state, prefix, 1, total_pages)
    page = bounded_page(state.get(f"{prefix}_page", 1), total_pages)
    return set_gallery_page(state, prefix, page, total_pages)
