import hashlib
import re
from pathlib import Path


MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def validate_pdf_upload(filename: str | None, content: bytes) -> str:
    if not filename or Path(filename.replace("\\", "/")).suffix.lower() != ".pdf":
        raise ValueError("Only files with a .pdf extension are accepted.")
    if not content:
        raise ValueError("The uploaded PDF is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("The PDF exceeds the 20 MB upload limit.")
    if not content.startswith(b"%PDF-"):
        raise ValueError("The uploaded file does not have a valid PDF signature.")

    return Path(filename.replace("\\", "/")).name


def get_content_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def make_stored_filename(original_filename: str) -> str:
    import uuid

    safe_name = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        Path(original_filename.replace("\\", "/")).name,
    ).strip("._")
    return f"{uuid.uuid4().hex}_{safe_name or 'document.pdf'}"


def extract_pdf_pages(pdf_path: Path) -> list:
    import fitz
    from langchain_core.documents import Document

    documents = []
    with fitz.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf, start=1):
            text = page.get_text("text")
            cleaned_text = re.sub(r"[ \t]+", " ", text).strip()
            if cleaned_text:
                documents.append(
                    Document(
                        page_content=cleaned_text,
                        metadata={"page_number": page_number},
                    )
                )

    if not documents:
        raise ValueError(f"No extractable text was found in {pdf_path.name}.")
    return documents
