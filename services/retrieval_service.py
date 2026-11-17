from typing import Any

from models.schemas import (
    ChatHistoryMessage,
    ChatResponse,
    SourceCitation,
)
from services.llm_service import generate_grounded_answer


RESULT_COUNT = 5
MAX_CONTEXT_CHARACTERS = 16_000
NO_INFORMATION_ANSWER = (
    "I couldn't find enough information to answer that in the indexed documents. "
    "Please try another question or process a relevant official PDF or webpage.\n\n"
    "குறியிடப்பட்ட ஆவணங்களில் இதற்குப் போதுமான தகவல் இல்லை. "
    "தொடர்புடைய அரசு PDF அல்லது இணையப் பக்கத்தைச் சேர்த்து மீண்டும் முயற்சிக்கவும்."
)


def build_retrieval_query(
    question: str,
    history: list[ChatHistoryMessage],
) -> str:
    previous_user_question = next(
        (
            message.content
            for message in reversed(history)
            if message.role == "user"
        ),
        None,
    )
    if previous_user_question:
        return (
            f"Previous user question: {previous_user_question}\n"
            f"Follow-up question: {question}"
        )
    return question


def _citation_for_document(
    source_id: int,
    metadata: dict[str, Any],
) -> SourceCitation:
    page_number = metadata.get("page_number")
    if not isinstance(page_number, int):
        page_number = None
    return SourceCitation(
        source_id=source_id,
        document_name=str(metadata.get("document_name") or "Government document"),
        page_number=page_number,
        source_url=metadata.get("source_url"),
        document_type=str(metadata.get("document_type") or "document"),
    )


def answer_question(
    question: str,
    history: list[ChatHistoryMessage],
    vector_store: Any,
) -> ChatResponse:
    query = build_retrieval_query(question, history)
    documents = vector_store.similarity_search(query, k=RESULT_COUNT)
    if not documents:
        return ChatResponse(answer=NO_INFORMATION_ANSWER)

    citations: list[SourceCitation] = []
    citation_ids: dict[tuple[str, int | None, str | None], int] = {}
    context_parts: list[str] = []
    context_characters = 0

    for document in documents:
        remaining_characters = MAX_CONTEXT_CHARACTERS - context_characters
        if remaining_characters <= 0:
            break

        metadata = document.metadata
        citation = _citation_for_document(len(citations) + 1, metadata)
        citation_key = (
            citation.document_name,
            citation.page_number,
            citation.source_url,
        )
        source_id = citation_ids.get(citation_key)
        if source_id is None:
            source_id = len(citations) + 1
            citation_ids[citation_key] = source_id
            citations.append(citation.model_copy(update={"source_id": source_id}))

        excerpt = document.page_content.strip()
        excerpt = excerpt[:remaining_characters]
        context_parts.append(f"[{source_id}]\n{excerpt}")
        context_characters += len(excerpt)

    if not context_parts:
        return ChatResponse(answer=NO_INFORMATION_ANSWER)

    answer = generate_grounded_answer(
        question=question,
        history=history,
        context="\n\n".join(context_parts),
    )
    return ChatResponse(answer=answer, sources=citations)
