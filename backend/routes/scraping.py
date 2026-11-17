from fastapi import APIRouter, HTTPException, status

from models.schemas import WebsiteScrapeRequest, WebsiteScrapeResponse
from services.web_scraper import scrape_approved_website


router = APIRouter(tags=["website scraping"])


@router.post(
    "/scrape-website",
    response_model=WebsiteScrapeResponse,
    status_code=status.HTTP_201_CREATED,
)
def scrape_website(request: WebsiteScrapeRequest) -> WebsiteScrapeResponse:
    try:
        result = scrape_approved_website(request.url)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return WebsiteScrapeResponse(
        **result,
        message="Page text was saved locally; click Process documents to add it to FAISS.",
    )
