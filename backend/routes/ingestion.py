from fastapi import APIRouter, HTTPException, Request

from models.schemas import (
    DocumentSummary,
    IngestionStatusResponse,
    ProcessDocumentsResponse,
)
from services.ingestion_service import get_ingestion_status, process_pending_pdfs


router = APIRouter(tags=["ingestion"])


@router.post("/process-documents", response_model=ProcessDocumentsResponse)
def process_documents(request: Request) -> ProcessDocumentsResponse:
    try:
        result, vector_store, embeddings = process_pending_pdfs(
            embeddings=request.app.state.embeddings,
            vector_store=request.app.state.vector_store,
        )
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Required package is missing: {exc.name}. Install project requirements.",
        ) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    request.app.state.vector_store = vector_store
    request.app.state.embeddings = embeddings
    return ProcessDocumentsResponse(**result)


@router.get("/ingestion-status", response_model=IngestionStatusResponse)
def ingestion_status() -> IngestionStatusResponse:
    status_data = get_ingestion_status()
    status_data["documents"] = [
        DocumentSummary(**document) for document in status_data["documents"]
    ]
    return IngestionStatusResponse(**status_data)


@router.get("/documents", response_model=list[DocumentSummary])
def list_documents() -> list[DocumentSummary]:
    return ingestion_status().documents
