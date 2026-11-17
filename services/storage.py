import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
UPLOADED_PDFS_DIR = DATA_DIR / "uploaded_pdfs"
SCRAPED_DOCUMENTS_DIR = DATA_DIR / "scraped_documents"
METADATA_DIR = DATA_DIR / "metadata"
DOCUMENTS_FILE = METADATA_DIR / "documents.json"


def ensure_storage_directories() -> None:
    UPLOADED_PDFS_DIR.mkdir(parents=True, exist_ok=True)
    SCRAPED_DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)


def load_document_registry() -> dict[str, Any]:
    if not DOCUMENTS_FILE.exists():
        return {"documents": [], "duplicate_uploads": []}

    try:
        registry = json.loads(DOCUMENTS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not read document metadata: {exc}") from exc

    if not isinstance(registry, dict) or not isinstance(registry.get("documents"), list):
        raise RuntimeError("Document metadata has an invalid format.")
    if not isinstance(registry.get("duplicate_uploads", []), list):
        raise RuntimeError("Duplicate-upload metadata has an invalid format.")
    registry.setdefault("duplicate_uploads", [])
    return registry


def save_document_registry(registry: dict[str, Any]) -> None:
    ensure_storage_directories()
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=METADATA_DIR,
            prefix="documents_",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(registry, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        temporary_path.replace(DOCUMENTS_FILE)
    except OSError as exc:
        raise RuntimeError(f"Could not save document metadata: {exc}") from exc
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
