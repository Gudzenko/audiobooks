from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from store.mcp.text_matching import normalize_text


def format_list_comparison(comparison, limitations: str) -> str:
    parts = [
        _section(_("Found in the catalog by title"), comparison.matched),
        _section(_("Not found as separate catalog entries"), comparison.missing),
    ]
    if comparison.unmatched_local:
        parts.append(
            _section(_("Other catalog entries"), comparison.unmatched_local)
        )
    parts.append(
        _(
            "The comparison uses catalog card titles. "
            "Collection contents are not stored in the catalog."
        )
    )
    if limitations:
        parts.append(f"**{_('Source limitation')}:** {limitations}")
    return "\n\n".join(parts)


def format_external_list(items, limitations: str) -> str:
    parts = [
        _section(
            _("Found in external sources"),
            [item.name for item in items],
        )
    ]
    if limitations:
        parts.append(f"**{_('Source limitation')}:** {limitations}")
    return "\n\n".join(parts)


def format_site_inventory(items, limitations: str, site_url: str | None) -> str:
    site_name = site_url or _("the requested site")
    item_lines = "\n".join(f"- **{item.name}**" for item in items)
    count = len(items)
    count_text = ngettext(
        "Found %(count)d separate page.",
        "Found %(count)d separate pages.",
        count,
    ) % {"count": count}
    parts = [
        f"## {_('Found on %(site)s') % {'site': site_name}}",
        item_lines or _("Nothing found."),
        count_text,
    ]
    if limitations:
        parts.append(f"**{_('Note')}:** {limitations}")
    return "\n\n".join(parts)


def format_site_comparison(
    comparison,
    limitations: str,
    site_url: str | None,
) -> str:
    site_name = site_url or _("the requested site")
    matched_lines = []
    for external_name, local_title in comparison.matched:
        if normalize_text(external_name) == normalize_text(local_title):
            matched_lines.append(f"- **{external_name}**")
        else:
            matched_lines.append(
                f"- **{external_name}** — {_('in the library')}: "
                f"**{local_title}**"
            )

    parts = [
        _line_section(
            _("Found both on %(site)s and in the library") % {"site": site_name},
            matched_lines,
        ),
        _section(
            _("Found on %(site)s, but not in the library") % {"site": site_name},
            comparison.site_only,
        ),
        _section(
            _("Found in the library, but not on %(site)s") % {"site": site_name},
            comparison.local_only,
        ),
    ]
    if limitations:
        parts.append(f"**{_('Note')}:** {limitations}")
    return "\n\n".join(parts)


def _section(title: str, values: list[str]) -> str:
    return _line_section(title, [f"- **{value}**" for value in values])


def _line_section(title: str, lines: list[str]) -> str:
    body = "\n".join(lines) if lines else _("Nothing found.")
    return f"## {title}\n\n{body}"
