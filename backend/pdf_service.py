
import json
import re
import uuid
from pathlib import Path

import fitz


def safe_filename(filename: str) -> str:
    """Keep a safe version of the original filename."""
    name = Path(filename).name
    name = re.sub(r"[^a-zA-Z0-9._-]", "_", name)
    return name or "document.pdf"


def process_pdf(
    file_bytes: bytes,
    filename: str,
    originals_dir: Path,
    extracted_dir: Path
):
    if not filename.lower().endswith(".pdf"):
        raise ValueError("Only PDF files are allowed.")

    if not file_bytes.startswith(b"%PDF-"):
        raise ValueError("Invalid PDF file.")

    originals_dir.mkdir(parents=True, exist_ok=True)
    extracted_dir.mkdir(parents=True, exist_ok=True)

    document_id = str(uuid.uuid4())
    original_filename = safe_filename(filename)

    saved_filename = f"{document_id}_{original_filename}"
    pdf_path = originals_dir / saved_filename

    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as pdf:

            if pdf.is_encrypted:
                raise ValueError("Password-protected PDFs are not supported.")

            if pdf.page_count == 0:
                raise ValueError("PDF contains no pages.")

            pdf_metadata = pdf.metadata or {}

            pages = []

            for page_index, page in enumerate(pdf):
                page_text = page.get_text("text")

                pages.append({
                    "page_number": page_index + 1,
                    "text": page_text.strip()
                })

            document_data = {
                "document_id": document_id,
                "filename": filename,
                "saved_filename": saved_filename,
                "page_count": pdf.page_count,
                "metadata": pdf_metadata,
                "pages": pages
            }

    except ValueError:
        raise
    except Exception as error:
        raise ValueError(f"Unable to read PDF: {error}")

    # Save the original PDF only after successful extraction.
    pdf_path.write_bytes(file_bytes)

    json_path = extracted_dir / f"{document_id}.json"

    try:
        json_path.write_text(
            json.dumps(document_data, ensure_ascii=False, indent=4),
            encoding="utf-8"
        )
    except Exception:
        pdf_path.unlink(missing_ok=True)
        raise

    return document_data
