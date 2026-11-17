import asyncio
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException, UploadFile

from backend.main import app
from backend.routes.chat import chat
from backend.routes.upload import upload_pdf
from models.schemas import ChatRequest, ChatResponse


class UploadApiTests(unittest.TestCase):
    def test_upload_endpoint_saves_valid_pdf(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            upload_directory = Path(temporary_directory) / "uploaded_pdfs"
            metadata_directory = Path(temporary_directory) / "metadata"
            with (
                patch("backend.routes.upload.UPLOADED_PDFS_DIR", upload_directory),
                patch("services.storage.UPLOADED_PDFS_DIR", upload_directory),
                patch("services.storage.METADATA_DIR", metadata_directory),
            ):
                upload = UploadFile(
                    filename="scheme.pdf",
                    file=BytesIO(b"%PDF-1.7\ncontent"),
                )
                response = asyncio.run(upload_pdf(upload))

            saved_files = list(upload_directory.glob("*.pdf"))
            self.assertEqual(response.status, "uploaded")
            self.assertEqual(response.document_name, "scheme.pdf")
            self.assertEqual(len(saved_files), 1)
            self.assertEqual(saved_files[0].read_bytes(), b"%PDF-1.7\ncontent")

    def test_upload_endpoint_rejects_non_pdf(self):
        upload = UploadFile(filename="notes.txt", file=BytesIO(b"text"))

        with self.assertRaises(HTTPException) as error:
            asyncio.run(upload_pdf(upload))

        self.assertEqual(error.exception.status_code, 400)

    def test_upload_endpoint_rejects_oversized_pdf(self):
        from services.pdf_loader import MAX_UPLOAD_BYTES

        upload = UploadFile(
            filename="large.pdf",
            file=BytesIO(b"%PDF-" + b"x" * MAX_UPLOAD_BYTES),
        )

        with self.assertRaises(HTTPException) as error:
            asyncio.run(upload_pdf(upload))

        self.assertEqual(error.exception.status_code, 413)

    def test_required_ingestion_routes_are_registered(self):
        routes = app.openapi()["paths"]
        required_routes = {
            "/upload-pdf": {"post"},
            "/scrape-website": {"post"},
            "/process-documents": {"post"},
            "/ingestion-status": {"get"},
            "/documents": {"get"},
            "/chat": {"post"},
            "/health": {"get"},
        }

        for path, methods in required_routes.items():
            self.assertTrue(methods.issubset(routes.get(path, {})), path)

    def test_chat_requires_an_indexed_document_store(self):
        request = SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(vector_store=None))
        )

        with self.assertRaises(HTTPException) as error:
            chat(ChatRequest(question="Who can apply?"), request)

        self.assertEqual(error.exception.status_code, 409)

    def test_chat_returns_grounded_answer_and_source_metadata(self):
        vector_store = object()
        request = SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(vector_store=vector_store))
        )
        expected = ChatResponse(
            answer="Eligible farmers are described in the cited document. [1]",
            sources=[
                {
                    "source_id": 1,
                    "document_name": "Scheme PDF",
                    "page_number": 2,
                    "source_url": None,
                    "document_type": "pdf",
                }
            ],
        )

        with patch("backend.routes.chat.answer_question", return_value=expected):
            response = chat(
                ChatRequest(question="Who can apply?"),
                request,
            )

        self.assertEqual(response.answer, expected.answer)
        self.assertEqual(response.sources[0].page_number, 2)


if __name__ == "__main__":
    unittest.main()
