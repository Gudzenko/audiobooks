from django.urls import reverse

from .schemas import ChatAnswerContext, ChatEvidenceItem


def build_answer_context(
    *,
    local_books,
    web_response=None,
    web_search_unavailable=False,
) -> ChatAnswerContext:
    return ChatAnswerContext(
        local_items=[
            ChatEvidenceItem(
                title=book.title,
                subtitle=", ".join(author.name for author in book.authors),
                url=reverse("book_detail", kwargs={"slug": book.slug}),
            )
            for book in local_books
        ],
        web_items=[
            ChatEvidenceItem(
                title=item.title,
                subtitle=(
                    ""
                    if web_response.extracted_items
                    else item.content or item.subtitle
                ),
                url=str(item.url),
            )
            for item in (web_response.results if web_response else [])
        ],
        web_extracted_items=(
            web_response.extracted_items if web_response else []
        ),
        web_coverage=(
            web_response.coverage if web_response else "not_applicable"
        ),
        web_limitations=web_response.limitations if web_response else "",
        web_search_unavailable=web_search_unavailable,
    )
