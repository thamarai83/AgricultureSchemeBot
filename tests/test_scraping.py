import json
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from services import ingestion_service, web_scraper


class WebsiteScraperTests(unittest.TestCase):
    def test_only_the_two_approved_page_urls_are_accepted(self):
        for url in web_scraper.APPROVED_SOURCES:
            self.assertEqual(web_scraper.validate_approved_source(url).url, url)

        with self.assertRaisesRegex(ValueError, "Only the configured"):
            web_scraper.validate_approved_source("https://example.com/")

    def test_page_text_normalization_removes_empty_lines_and_extra_spaces(self):
        text = web_scraper.normalize_page_text(" Scheme   Details \n\n Subsidy\t amount ")

        self.assertEqual(text, "Scheme Details\nSubsidy amount")

    def test_robots_policy_disallow_is_respected(self):
        response = SimpleNamespace(
            status_code=200,
            headers={},
            text="User-agent: *\nDisallow: /en/",
        )
        url = next(iter(web_scraper.APPROVED_SOURCES))

        with patch("services.web_scraper.requests.get", return_value=response):
            with self.assertRaisesRegex(PermissionError, "disallows"):
                web_scraper._check_robots_policy(url)

    def test_scraped_text_is_queued_and_processed_into_chunks(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_directory = Path(temporary_directory)
            scraped_directory = data_directory / "scraped_documents"
            uploads_directory = data_directory / "uploaded_pdfs"
            metadata_directory = data_directory / "metadata"
            registry_path = metadata_directory / "documents.json"
            fake_embeddings = object()
            fake_store = object()
            langchain_core = ModuleType("langchain_core")
            langchain_documents = ModuleType("langchain_core.documents")

            class FakeDocument:
                def __init__(self, page_content, metadata):
                    self.page_content = page_content
                    self.metadata = metadata

            langchain_documents.Document = FakeDocument
            langchain_core.documents = langchain_documents
            url = next(iter(web_scraper.APPROVED_SOURCES))

            with (
                patch("services.web_scraper._check_robots_policy"),
                patch(
                    "services.web_scraper._extract_page_text",
                    return_value=("Scheme page", "Eligibility information"),
                ),
                patch("services.web_scraper.SCRAPED_DOCUMENTS_DIR", scraped_directory),
                patch("services.storage.SCRAPED_DOCUMENTS_DIR", scraped_directory),
                patch("services.storage.UPLOADED_PDFS_DIR", uploads_directory),
                patch("services.storage.METADATA_DIR", metadata_directory),
                patch("services.storage.DOCUMENTS_FILE", registry_path),
            ):
                result = web_scraper.scrape_approved_website(url)
                staged_files = list(scraped_directory.glob("*.json"))
                self.assertEqual(result["status"], "queued")
                self.assertEqual(len(staged_files), 1)

                with (
                    patch.object(ingestion_service, "SCRAPED_DOCUMENTS_DIR", scraped_directory),
                    patch.object(ingestion_service, "UPLOADED_PDFS_DIR", uploads_directory),
                    patch.dict(
                        "sys.modules",
                        {
                            "langchain_core": langchain_core,
                            "langchain_core.documents": langchain_documents,
                        },
                    ),
                    patch.object(
                        ingestion_service,
                        "split_documents",
                        side_effect=lambda documents: documents,
                    ),
                    patch.object(
                        ingestion_service,
                        "add_documents_to_store",
                        return_value=fake_store,
                    ) as add_documents,
                ):
                    processed, saved_store, saved_embeddings = (
                        ingestion_service.process_pending_pdfs(
                            embeddings=fake_embeddings,
                        )
                    )

                self.assertEqual(processed["processed_documents"], 1)
                self.assertEqual(processed["chunks_created"], 1)
                self.assertIs(saved_store, fake_store)
                self.assertIs(saved_embeddings, fake_embeddings)
                added_document = add_documents.call_args.args[0][0]
                self.assertEqual(added_document.page_content, "Eligibility information")
                self.assertEqual(added_document.metadata["source_url"], url)
                self.assertEqual(added_document.metadata["document_type"], "website")

                stored_registry = json.loads(registry_path.read_text(encoding="utf-8"))
                self.assertEqual(stored_registry["documents"][0]["source_url"], url)


if __name__ == "__main__":
    unittest.main()
