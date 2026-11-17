from typing import Literal

from pydantic import BaseModel, Field, field_validator


class UploadResponse(BaseModel):
    document_name: str
    status: str
    message: str


class DocumentSummary(BaseModel):
    document_name: str
    source_url: str | None = None
    document_type: str
    ingestion_date: str
    chunk_count: int


class IngestionStatusResponse(BaseModel):
    status: str
    processed_documents: int
    pending_documents: int
    total_chunks: int
    faiss_available: bool
    documents: list[DocumentSummary]


class ProcessDocumentsResponse(BaseModel):
    status: str
    processed_documents: int
    duplicates_skipped: int
    chunks_created: int


class WebsiteScrapeRequest(BaseModel):
    url: Literal[
        "https://aed.tn.gov.in/en/individual-based-subsidy-schemes/",
        "https://www.landreforms.tn.gov.in/UPT.html",
    ]


class WebsiteScrapeResponse(BaseModel):
    status: str
    document_name: str
    source_url: str
    characters_extracted: int
    message: str


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1200)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    history: list[ChatHistoryMessage] = Field(default_factory=list, max_length=10)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, question: str) -> str:
        question = question.strip()
        if not question:
            raise ValueError("Question must not be blank.")
        return question


class SourceCitation(BaseModel):
    source_id: int
    document_name: str
    page_number: int | None = None
    source_url: str | None = None
    document_type: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceCitation] = Field(default_factory=list)
