import json

from openai import OpenAI

from .contracts import (
    CatalogFilterAmbiguous,
    ChatModelUnavailable,
    ChatTextResult,
)
from .modes import WebSearchMode
from .prompts import (
    ANSWER_PROMPT,
    CATALOG_CLARIFICATION_PROMPT,
    SYSTEM_PROMPT,
    TITLE_MATCH_PROMPT,
    get_list_extraction_prompt,
)
from .schemas import (
    ChatAnswerContext,
    ChatPlan,
    ChatRequest,
    TitleMatchResult,
    WebListExtraction,
    WebSearchItem,
)


class OpenAIChatModelProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout: float,
        plan_max_output_tokens: int = 1_200,
        clarification_max_output_tokens: int = 500,
        answer_max_output_tokens: int = 1_600,
        list_max_output_tokens: int = 6_000,
        title_match_max_output_tokens: int = 3_000,
        client=None,
    ):
        self.model = model
        self.timeout = timeout
        self.plan_max_output_tokens = plan_max_output_tokens
        self.clarification_max_output_tokens = clarification_max_output_tokens
        self.answer_max_output_tokens = answer_max_output_tokens
        self.list_max_output_tokens = list_max_output_tokens
        self.title_match_max_output_tokens = title_match_max_output_tokens
        self.client = client or OpenAI(api_key=api_key, timeout=timeout)

    def create_plan(self, chat_request: ChatRequest) -> ChatPlan:
        input_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        input_messages.extend(
            {"role": item.role, "content": item.content}
            for item in chat_request.history
        )
        input_messages.append({"role": "user", "content": chat_request.message})

        try:
            response = self.client.responses.parse(
                model=self.model,
                input=input_messages,
                text_format=ChatPlan,
                max_output_tokens=self.plan_max_output_tokens,
            )
        except Exception as error:
            raise ChatModelUnavailable from error

        self._require_completed_response(response)
        if response.output_parsed is None:
            raise ChatModelUnavailable
        return response.output_parsed

    def create_catalog_clarification(
        self,
        chat_request: ChatRequest,
        ambiguity: CatalogFilterAmbiguous,
    ) -> ChatTextResult:
        input_messages = [
            {"role": "system", "content": CATALOG_CLARIFICATION_PROMPT}
        ]
        input_messages.extend(
            {"role": item.role, "content": item.content}
            for item in chat_request.history
        )
        input_messages.extend(
            [
                {"role": "user", "content": chat_request.message},
                {
                    "role": "developer",
                    "content": (
                        f"Entity: {ambiguity.entity}\n"
                        f"Requested value: {ambiguity.requested}\n"
                        f"Candidates: {ambiguity.candidates}"
                    ),
                },
            ]
        )
        try:
            response = self.client.responses.create(
                model=self.model,
                input=input_messages,
                max_output_tokens=self.clarification_max_output_tokens,
            )
        except Exception as error:
            raise ChatModelUnavailable from error

        question = self._text_response(response)
        if not question.text:
            raise ChatModelUnavailable
        return question

    def create_answer(
        self,
        chat_request: ChatRequest,
        context: ChatAnswerContext,
    ) -> ChatTextResult:
        input_messages = [{"role": "system", "content": ANSWER_PROMPT}]
        input_messages.extend(
            {"role": item.role, "content": item.content}
            for item in chat_request.history
        )
        input_messages.extend(
            [
                {"role": "user", "content": chat_request.message},
                {
                    "role": "developer",
                    "content": f"Evidence:\n{context.model_dump_json()}",
                },
            ]
        )

        try:
            response = self.client.responses.create(
                model=self.model,
                input=input_messages,
                timeout=max(self.timeout, 60),
                max_output_tokens=self.answer_max_output_tokens,
            )
        except Exception as error:
            raise ChatModelUnavailable from error

        answer = self._text_response(response)
        if not answer.text:
            raise ChatModelUnavailable
        return answer

    def extract_web_list(
        self,
        chat_request: ChatRequest,
        web_results: list[WebSearchItem],
        mode: WebSearchMode = "complete_list",
    ) -> WebListExtraction:
        evidence = [
            {
                "title": item.title,
                "url": str(item.url),
                "content": item.content,
            }
            for item in web_results
        ]
        input_messages = [
            {
                "role": "system",
                "content": get_list_extraction_prompt(mode),
            }
        ]
        input_messages.extend(
            {"role": item.role, "content": item.content}
            for item in chat_request.history
        )
        input_messages.extend(
            [
                {"role": "user", "content": chat_request.message},
                {
                    "role": "developer",
                    "content": (
                        "Web evidence:\n"
                        + json.dumps(evidence, ensure_ascii=False)
                    ),
                },
            ]
        )
        try:
            response = self.client.responses.parse(
                model=self.model,
                input=input_messages,
                text_format=WebListExtraction,
                timeout=max(self.timeout, 90),
                max_output_tokens=self.list_max_output_tokens,
            )
        except Exception as error:
            raise ChatModelUnavailable from error

        self._require_completed_response(response)
        if response.output_parsed is None:
            raise ChatModelUnavailable
        return response.output_parsed

    def match_titles(
        self,
        external_names: list[str],
        local_titles: list[str],
    ) -> TitleMatchResult:
        try:
            response = self.client.responses.parse(
                model=self.model,
                input=[
                    {"role": "system", "content": TITLE_MATCH_PROMPT},
                    {
                        "role": "developer",
                        "content": json.dumps(
                            {
                                "external_names": external_names,
                                "local_titles": local_titles,
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
                text_format=TitleMatchResult,
                timeout=max(self.timeout, 60),
                max_output_tokens=self.title_match_max_output_tokens,
            )
        except Exception as error:
            raise ChatModelUnavailable from error

        self._require_completed_response(response)
        if response.output_parsed is None:
            raise ChatModelUnavailable
        return response.output_parsed

    @staticmethod
    def _require_completed_response(response) -> None:
        status = getattr(response, "status", None)
        if status is not None and status != "completed":
            raise ChatModelUnavailable

    @staticmethod
    def _text_response(response) -> ChatTextResult:
        text = getattr(response, "output_text", "").strip()
        status = getattr(response, "status", None)
        if status == "incomplete":
            details = getattr(response, "incomplete_details", None)
            reason = (
                details.get("reason")
                if isinstance(details, dict)
                else getattr(details, "reason", None)
            )
            if reason == "max_output_tokens" and text:
                return ChatTextResult(text=text, truncated=True)
            raise ChatModelUnavailable
        if status is not None and status != "completed":
            raise ChatModelUnavailable
        return ChatTextResult(text=text)
