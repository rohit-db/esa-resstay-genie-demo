"""Strict {{name}} rendering for SQL (and later dashboard/Genie) templates."""

from __future__ import annotations

import re

PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


class TemplateError(ValueError):
    pass


def render_template(text: str, context: dict[str, str]) -> str:
    """Replace every {{name}}; unknown names and leftover braces are errors, never silent."""
    missing = sorted({m.group(1) for m in PLACEHOLDER.finditer(text)} - set(context))
    if missing:
        raise TemplateError(f"unknown placeholders: {missing}")
    rendered = PLACEHOLDER.sub(lambda m: context[m.group(1)], text)
    if "{{" in rendered or "}}" in rendered:
        raise TemplateError("unbalanced template braces remain after rendering")
    return rendered
