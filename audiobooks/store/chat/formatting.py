import re

import markdown
import nh3


ALLOWED_TAGS = {
    "a",
    "blockquote",
    "br",
    "code",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "li",
    "ol",
    "p",
    "pre",
    "strong",
    "ul",
}
ALLOWED_ATTRIBUTES = {"a": {"href", "title"}}


def render_chat_markdown(value: str) -> str:
    normalized = re.sub(r"\s+•\s+", "\n\n- ", value.strip())
    rendered = markdown.markdown(
        normalized,
        extensions=["nl2br", "sane_lists"],
        output_format="html",
    )
    return nh3.clean(
        rendered,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes={"http", "https"},
        link_rel="noopener noreferrer",
    )


def make_source_excerpt(value: str, *, max_length: int = 500) -> str:
    before_table = value.split("|", 1)[0].strip()
    excerpt = before_table or value
    excerpt = re.sub(r"#{1,6}\s*", "", excerpt)
    excerpt = re.sub(r"\*\*(.*?)\*\*", r"\1", excerpt)
    excerpt = re.sub(r"\[(.*?)]\([^)]*\)", r"\1", excerpt)
    excerpt = re.sub(r"\s+", " ", excerpt).strip(" -|")
    if len(excerpt) <= max_length:
        return excerpt
    return f"{excerpt[:max_length].rstrip()}…"
