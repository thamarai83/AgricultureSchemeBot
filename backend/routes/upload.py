from fastapi import APIRouter, File, HTTPException, UploadFile, status

from models.schemas import UploadResponse
from services.pdf_loader import (
    MAX_UPLOAD_BYTES,
    make_stored_filename,
    validate_pdf_upload,
)
from services.storage import UPLOADED_PDFS_DIR, ensure_storage_directories


router = APIRouter(tags=["documents"])


@router.post(
    "/upload-pdf",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_pdf(file: UploadFile = File(...)) -> UploadResponse:
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="The PDF exceeds the 20 MB upload limit.",
        )
    try:
        document_name = validate_pdf_upload(file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    ensure_storage_directories()
    stored_filename = make_stored_filename(document_name)
    destination = UPLOADED_PDFS_DIR / stored_filename
    destination.write_bytes(content)
    return UploadResponse(
        document_name=document_name,
        status="uploaded",
        message="PDF saved locally and queued for processing.",
    )
