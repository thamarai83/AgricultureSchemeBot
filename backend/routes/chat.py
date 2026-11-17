from fastapi import APIRouter, HTTPException, Request

from models.schemas import ChatRequest, ChatResponse
from services.retrieval_service import answer_question


router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, api_request: Request) -> ChatResponse:
    vector_store = api_request.app.state.vector_store
    if vector_store is None:
        raise HTTPException(
            status_code=409,
            detail="No documents are indexed yet. Upload or scrape sources, then process documents.",
        )

    try:
        return answer_question(
            question=request.question,
            history=request.history,
            vector_store=vector_store,
        )
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Required package is missing: {exc.name}. Install project requirements.",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
