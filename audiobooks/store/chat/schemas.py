from ipaddress import ip_address
from typing import Annotated, Literal
from urllib.parse import urlparse

from django.utils.translation import gettext as _
from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from .formatting import render_chat_markdown
from .modes import WebSearchMode
from .constants import (
    MAX_CHAT_HISTORY_ITEM_CHARS,
    MAX_CHAT_HISTORY_ITEMS,
    MAX_CHAT_HISTORY_TOTAL_CHARS,
    MAX_WEB_LIST_ITEMS,
)


class ChatHistoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(
        min_length=1,
        max_length=MAX_CHAT_HISTORY_ITEM_CHARS,
    )


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatHistoryItem] = Field(
        default_factory=list,
        max_length=MAX_CHAT_HISTORY_ITEMS,
    )

    @model_validator(mode="after")
    def validate_total_history_size(self):
        if (
            sum(len(item.content) for item in self.history)
            > MAX_CHAT_HISTORY_TOTAL_CHARS
        ):
            raise ValueError("chat history is too large")
        return self


class CatalogSearchFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str | None = Field(default=None, max_length=500)
    author_names: list[str] = Field(default_factory=list, max_length=10)
    genre_names: list[str] = Field(default_factory=list, max_length=10)
    series_names: list[str] = Field(default_factory=list, max_length=10)
    is_read: bool | None = None
    has_audio: bool | None = None
    authors_match: Literal["any", "all"] = "any"
    genres_match: Literal["any", "all"] = "any"


class ChatPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["catalog", "web", "catalog_and_web", "clarification"]
    catalog_filters: CatalogSearchFilters = Field(
        default_factory=CatalogSearchFilters
    )
    web_query: str = Field(default="", max_length=4000)
    web_objective: str = Field(default="", max_length=4096)
    web_mode: WebSearchMode = "lookup"
    site_url: str | None = Field(default=None, max_length=2048)
    clarification: str = Field(default="", max_length=2000)

    @field_validator("site_url")
    @classmethod
    def validate_site_url(cls, value):
        if value is None:
            return value
        parsed = urlparse(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.hostname.casefold() == "localhost"
        ):
            raise ValueError("site_url must be a public HTTP or HTTPS URL")
        try:
            address = ip_address(parsed.hostname)
        except ValueError:
            pass
        else:
            if not address.is_global:
                raise ValueError("site_url must be a public HTTP or HTTPS URL")
        return value

    @model_validator(mode="after")
    def validate_action_fields(self):
        if self.action in {"web", "catalog_and_web"}:
            if not self.web_query.strip():
                raise ValueError("web_query is required for web actions")
            if not self.web_objective.strip():
                raise ValueError("web_objective is required for web actions")
        if self.action == "clarification" and not self.clarification.strip():
            raise ValueError("clarification is required for clarification")
        return self


class WebSearchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    subtitle: str = ""
    content: str = ""
    url: AnyHttpUrl


class WebExtractedItem(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    alternative_names: list[
        Annotated[str, Field(min_length=1, max_length=300)]
    ] = Field(default_factory=list, max_length=5)
    source_url: str = Field(default="", max_length=2048)


class WebListExtraction(BaseModel):
    items: list[WebExtractedItem] = Field(default_factory=list)
    coverage: Literal["complete", "partial"]
    limitations: str = Field(default="", max_length=4000)
    truncated: bool = False

    @model_validator(mode="before")
    @classmethod
    def truncate_oversized_list(cls, value):
        if not isinstance(value, dict):
            return value
        items = value.get("items")
        if not isinstance(items, list):
            return value
        value = dict(value)
        value["truncated"] = (
            bool(value.get("truncated"))
            or len(items) > MAX_WEB_LIST_ITEMS
        )
        if len(items) <= MAX_WEB_LIST_ITEMS:
            return value
        value["items"] = items[:MAX_WEB_LIST_ITEMS]
        value["coverage"] = "partial"
        return value


class TitleMatch(BaseModel):
    external_name: str = Field(min_length=1, max_length=500)
    local_title: str = Field(min_length=1, max_length=500)


class TitleMatchResult(BaseModel):
    matches: list[TitleMatch] = Field(default_factory=list, max_length=100)


class WebSearchResponse(BaseModel):
    results: list[WebSearchItem] = Field(default_factory=list)
    extracted_items: list[WebExtractedItem] = Field(default_factory=list)
    coverage: Literal["not_applicable", "complete", "partial"] = "not_applicable"
    limitations: str = ""
    full_content_unavailable: bool = False


class ChatEvidenceItem(BaseModel):
    title: str
    subtitle: str = ""
    url: str = ""


class ChatAnswerContext(BaseModel):
    local_items: list[ChatEvidenceItem] = Field(default_factory=list)
    web_items: list[ChatEvidenceItem] = Field(default_factory=list)
    web_extracted_items: list[WebExtractedItem] = Field(default_factory=list)
    web_coverage: Literal["not_applicable", "complete", "partial"] = "not_applicable"
    web_limitations: str = ""
    web_search_unavailable: bool = False


class ChatLink(BaseModel):
    label: str
    url: str
    is_demo: bool = False

    @field_validator("url")
    @classmethod
    def validate_url(cls, value):
        if value.startswith("/") and not value.startswith("//"):
            return value
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("link must be relative or use HTTP/HTTPS")
        return value


class ChatResultItem(BaseModel):
    title: str
    subtitle: str = ""
    status: str = ""
    links: list[ChatLink] = Field(default_factory=list)


class ChatSection(BaseModel):
    title: str
    items: list[ChatResultItem] = Field(default_factory=list)


class ChatResponse(BaseModel):
    kind: Literal["answer", "clarification", "partial", "error"]
    message: str
    message_html: str = ""
    history_content: str = ""
    sections: list[ChatSection] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def render_message(self):
        if not self.message_html:
            self.message_html = render_chat_markdown(self.message)
        if not self.history_content:
            lines = [self.message]
            for section in self.sections:
                lines.append(section.title)
                lines.extend(
                    f"- {item.title}"
                    + (f" — {item.subtitle}" if item.subtitle else "")
                    for item in section.items
                )
            base_history_content = "\n\n".join(lines)
            if len(base_history_content) > MAX_CHAT_HISTORY_ITEM_CHARS:
                warning = _(
                    "This answer is too long to retain fully in the chat context. "
                    "Refine the next request by author, series, genre, or combine "
                    "several filters."
                )
                if warning not in self.warnings:
                    self.warnings.append(warning)
            warning_lines = [
                f"{_('Warning')}: {warning}"
                for warning in self.warnings
            ]
            history_content = "\n\n".join(
                [*warning_lines, base_history_content]
            )
            self.history_content = history_content[:MAX_CHAT_HISTORY_ITEM_CHARS]
        return self
