import os
import re
from typing import Any, Optional

import requests

from agent.logger import get_logger

logger = get_logger(__name__)


def extract_figma_file_key(value: str | None) -> Optional[str]:
    if not value:
        return None
    value = value.strip()
    patterns = [
        r"figma\.com/(?:file|design)/([A-Za-z0-9]+)",
        r"^([A-Za-z0-9]{10,})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, value)
        if match:
            return match.group(1)
    return None


def get_saved_connection_config(connection_id: int) -> Optional[dict[str, Any]]:
    from agent.db import query

    rows = query(
        """
        SELECT id, name, source_type, config
        FROM saved_connections
        WHERE id = %s
        """,
        [connection_id],
    )
    return rows[0] if rows else None


def fetch_figma_design_context(config: dict[str, Any]) -> str:
    file_url = config.get("figma_file_url") or config.get("file_url") or config.get("url")
    file_key = config.get("figma_file_key") or extract_figma_file_key(file_url)
    node_id = config.get("figma_node_id") or config.get("node_id")
    token = config.get("figma_access_token") or config.get("access_token") or os.getenv("FIGMA_ACCESS_TOKEN")

    if not file_key:
        return "Figma design reference was provided, but no valid Figma file key could be extracted."
    if not token or token == "********":
        return "Figma design reference was provided, but no Figma access token is available to fetch the design."

    url = f"https://api.figma.com/v1/files/{file_key}"
    params = {"ids": node_id} if node_id else None
    response = requests.get(url, headers={"X-Figma-Token": token}, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()

    document = payload.get("document", {})
    root = document
    if node_id:
        root = _find_node(document, node_id.replace("-", ":")) or document

    summary = {
        "file_name": payload.get("name"),
        "last_modified": payload.get("lastModified"),
        "thumbnail_url_available": bool(payload.get("thumbnailUrl")),
        "selected_node": _node_summary(root, depth=0, max_depth=3),
        "colors": _extract_colors(root)[:16],
        "text_styles": _extract_text_styles(root)[:12],
    }

    import json

    return (
        "Figma design reference summary. Use this as dashboard layout and visual direction; "
        "match spacing, hierarchy, card structure, colors, and typography where practical.\n"
        f"{json.dumps(summary, default=str)}"
    )


def build_figma_context_from_connection(connection_id: Optional[int]) -> Optional[str]:
    if not connection_id:
        return None
    saved = get_saved_connection_config(connection_id)
    if not saved:
        return "Figma design connection was selected, but the connection was not found."
    if saved.get("source_type") != "figma_design":
        return "Selected design connection is not a Figma design connector."
    return fetch_figma_design_context(saved.get("config") or {})


def _find_node(node: dict[str, Any], node_id: str) -> Optional[dict[str, Any]]:
    if node.get("id") == node_id:
        return node
    for child in node.get("children", []) or []:
        found = _find_node(child, node_id)
        if found:
            return found
    return None


def _node_summary(node: dict[str, Any], depth: int, max_depth: int) -> dict[str, Any]:
    box = node.get("absoluteBoundingBox") or {}
    summary = {
        "name": node.get("name"),
        "type": node.get("type"),
        "width": box.get("width"),
        "height": box.get("height"),
        "layout_mode": node.get("layoutMode"),
        "item_spacing": node.get("itemSpacing"),
        "padding": {
            "top": node.get("paddingTop"),
            "right": node.get("paddingRight"),
            "bottom": node.get("paddingBottom"),
            "left": node.get("paddingLeft"),
        },
    }
    if depth < max_depth:
        summary["children"] = [
            _node_summary(child, depth + 1, max_depth)
            for child in (node.get("children", []) or [])[:8]
        ]
    else:
        summary["child_count"] = len(node.get("children", []) or [])
    return summary


def _extract_colors(node: dict[str, Any]) -> list[str]:
    colors: list[str] = []

    def walk(item: dict[str, Any]) -> None:
        for paint in (item.get("fills") or []) + (item.get("strokes") or []):
            color = paint.get("color")
            if paint.get("visible", True) and color:
                colors.append(_rgba_to_hex(color, paint.get("opacity", 1)))
        for child in item.get("children", []) or []:
            walk(child)

    walk(node)
    seen = []
    for color in colors:
        if color not in seen:
            seen.append(color)
    return seen


def _extract_text_styles(node: dict[str, Any]) -> list[dict[str, Any]]:
    styles: list[dict[str, Any]] = []

    def walk(item: dict[str, Any]) -> None:
        if item.get("type") == "TEXT":
            style = item.get("style") or {}
            styles.append({
                "name": item.get("name"),
                "font_family": style.get("fontFamily"),
                "font_size": style.get("fontSize"),
                "font_weight": style.get("fontWeight"),
                "line_height": style.get("lineHeightPx"),
            })
        for child in item.get("children", []) or []:
            walk(child)

    walk(node)
    return styles


def _rgba_to_hex(color: dict[str, Any], opacity: float = 1) -> str:
    r = round(float(color.get("r", 0)) * 255)
    g = round(float(color.get("g", 0)) * 255)
    b = round(float(color.get("b", 0)) * 255)
    if opacity < 1:
        a = round(opacity * 255)
        return f"#{r:02x}{g:02x}{b:02x}{a:02x}"
    return f"#{r:02x}{g:02x}{b:02x}"
