import json
from datetime import date
from pathlib import Path
from typing import Any

from services.embedding_service import get_embeddings
from services.pdf_loader import (
    extract_pdf_pages,
    get_content_sha256,
)
from services.storage import (
    UPLOADED_PDFS_DIR,
    SCRAPED_DOCUMENTS_DIR,
    ensure_storage_directories,
    load_document_registry,
    save_document_registry,
)
from services.text_splitter import split_documents
from services.vector_store import add_documents_to_store, has_persisted_index


def get_ingestion_status() -> dict[str, Any]:
    ensure_storage_directories()
    registry = load_document_registry()
    processed_files = {
        record["stored_filename"]
        for record in registry["documents"]
        if "stored_filename" in record
    }
    duplicate_files = set(registry["duplicate_uploads"])
    pending_files = [
        path
        for path in (
            *UPLOADED_PDFS_DIR.glob("*.pdf"),
            *SCRAPED_DOCUMENTS_DIR.glob("*.json"),
        )
        if path.name not in processed_files and path.name not in duplicate_files
    ]

    return {
        "status": "ready",
        "processed_documents": len(registry["documents"]),
        "pending_documents": len(pending_files),
        "total_chunks": sum(
            record.get("chunk_count", 0) for record in registry["documents"]
        ),
        "faiss_available": has_persisted_index(),
        "documents": [
            {
                "document_name": record["document_name"],
                "source_url": record.get("source_url"),
                "document_type": record.get("document_type", "pdf"),
                "ingestion_date": record["ingestion_date"],
                "chunk_count": record.get("chunk_count", 0),
            }
            for record in registry["documents"]
        ],
    }


def process_pending_pdfs(
    embeddings=None,
    vector_store=None,
) -> tuple[dict[str, int | str], Any, Any]:
    ensure_storage_directories()
    registry = load_document_registry()
    processed_files = {
        record["stored_filename"]
        for record in registry["documents"]
        if "stored_filename" in record
    }
    duplicate_files = set(registry["duplicate_uploads"])
    pending_files = sorted(
        path
        for path in (
            *UPLOADED_PDFS_DIR.glob("*.pdf"),
            *SCRAPED_DOCUMENTS_DIR.glob("*.json"),
        )
        if path.name not in processed_files and path.name not in duplicate_files
    )

    existing_hashes = {
        record["sha256"] for record in registry["documents"] if "sha256" in record
    }
    documents_to_add = []
    new_records = []
    duplicates_skipped = 0

    for pdf_path in pending_files:
        content = pdf_path.read_bytes()
        is_website = pdf_path.suffix.lower() == ".json"
        website_data = None
        if is_website:
            try:
                website_data = json.loads(content.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(
                    f"Could not read scraped page data from {pdf_path.name}."
                ) from exc
            if not isinstance(website_data, dict) or not website_data.get("text"):
                raise ValueError(f"Scraped page data is invalid in {pdf_path.name}.")
            content_hash = get_content_sha256(website_data["text"].encode("utf-8"))
            document_name = website_data.get("document_name", pdf_path.stem)
            source_url = website_data.get("source_url")
            department = website_data.get("department")
            document_type = "website"
            from langchain_core.documents import Document

            pages = [
                Document(
                    page_content=website_data["text"],
                    metadata={"page_number": None},
                )
            ]
        else:
            content_hash = get_content_sha256(content)
            document_name = pdf_path.name.split("_", 1)[-1]
            source_url = None
            department = None
            document_type = "pdf"

        if content_hash in existing_hashes:
            registry["duplicate_uploads"].append(pdf_path.name)
            duplicates_skipped += 1
            continue

        if not is_website:
            pages = extract_pdf_pages(pdf_path)
        for page in pages:
            page.metadata.update(
                {
                    "document_name": document_name,
                    "source_url": source_url,
                    "scheme_name": (
                        website_data.get("scheme_name") if website_data else None
                    ),
                    "department": department,
                    "document_type": document_type,
                    "ingestion_date": date.today().isoformat(),
                    "sha256": content_hash,
                }
            )

        chunks = split_documents(pages)
        if not chunks:
            raise ValueError(f"No text chunks could be created for {pdf_path.name}.")

        documents_to_add.extend(chunks)
        new_records.append(
            {
                "document_name": document_name,
                "stored_filename": pdf_path.name,
                "sha256": content_hash,
                "source_url": source_url,
                "scheme_name": website_data.get("scheme_name") if website_data else None,
                "department": department,
                "document_type": document_type,
                "ingestion_date": date.today().isoformat(),
                "chunk_count": len(chunks),
            }
        )
        existing_hashes.add(content_hash)

    if documents_to_add:
        embeddings = embeddings or get_embeddings()
        from services.vector_store import load_vector_store

        vector_store = vector_store or load_vector_store(embeddings)
        vector_store = add_documents_to_store(
            documents_to_add,
            embeddings,
            vector_store,
        )
        registry["documents"].extend(new_records)

    save_document_registry(registry)
    return (
        {
            "status": "completed",
            "processed_documents": len(new_records),
            "duplicates_skipped": duplicates_skipped,
            "chunks_created": len(documents_to_add),
        },
        vector_store,
        embeddings,
    )
