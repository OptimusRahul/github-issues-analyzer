"""Text shaping shared by embeddings, the LLM prompt and the bot comment."""

from __future__ import annotations

import re

BODY_CHARS = 2000

_URL = re.compile(r"(?:https?:|www\.|//)\S*", re.IGNORECASE)
_MENTION = re.compile(r"@(?=[\w-])")
_ISSUE_REF = re.compile(r"(?<![\w&])#(?=\d)|\bGH-(?=\d)", re.IGNORECASE)
_MARKUP = re.compile(r"[<>`]")
_MARKDOWN = re.compile(r"([\\\[\]()!&*_~|])")
_SPACE = re.compile(r"\s+")


def issue_text(issue: dict) -> str:
    """Title plus the start of the body: the text that represents an issue for search."""
    body = (issue.get("body") or "").strip()[:BODY_CHARS]
    return f"{issue['title']}\n\n{body}" if body else issue["title"]


def sanitize(text: str | None, limit: int = 140) -> str:
    """Make untrusted text safe to post: no @mentions, links, issue references or markup, capped in length.

    Markdown punctuation is backslash-escaped, so link syntax and HTML entities (such as &#64;) render as plain text.
    """
    text = _URL.sub("", text or "")
    text = _MENTION.sub("", text)
    text = _ISSUE_REF.sub("", text)
    text = _MARKUP.sub("", text)
    text = _SPACE.sub(" ", text).strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return _MARKDOWN.sub(r"\\\1", text)
