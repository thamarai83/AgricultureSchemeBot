import unittest
from types import SimpleNamespace
from unittest.mock import patch

from models.schemas import ChatHistoryMessage
from services.retrieval_service import (
    NO_INFORMATION_ANSWER,
    answer_question,
    build_retrieval_query,
)


class RetrievalTests(unittest.TestCase):
    def test_follow_up_query_includes_previous_user_question(self):
        history = [
            ChatHistoryMessage(role="user", content="Tell me about the subsidy."),
            ChatHistoryMessage(role="assistant", content="The source describes it."),
        ]

        query = build_retrieval_query("Who is eligible?", history)

        self.assertIn("Tell me about the subsidy.", query)
        self.assertIn("Who is eligible?", query)

    def test_answer_includes_pdf_page_and_website_url_citations(self):
        documents = [
            SimpleNamespace(
                page_content="Small and marginal farmers are eligible.",
                metadata={
                    "document_name": "farmer-scheme.pdf",
                    "page_number": 3,
                    "document_type": "pdf",
                },
            ),
            SimpleNamespace(
                page_content="Eligibility is described by the department.",
                metadata={
                    "document_name": "Uzhavar Pathukappu Thittam",
                    "page_number": None,
                    "source_url": "https://www.landreforms.tn.gov.in/UPT.html",
                    "document_type": "website",
                },
            ),
        ]
        vector_store = SimpleNamespace(
            similarity_search=lambda query, k: documents
        )

        with patch(
            "services.retrieval_service.generate_grounded_answer",
            return_value="Small and marginal farmers are eligible. [1]",
        ) as generate_answer:
            response = answer_question("Who is eligible?", [], vector_store)

        self.assertEqual(len(response.sources), 2)
        self.assertEqual(response.sources[0].page_number, 3)
        self.assertEqual(
            response.sources[1].source_url,
            "https://www.landreforms.tn.gov.in/UPT.html",
        )
        self.assertIn("[1]", generate_answer.call_args.kwargs["context"])

    def test_empty_index_returns_unavailable_answer_without_llm_call(self):
        vector_store = SimpleNamespace(
            similarity_search=lambda query, k: []
        )

        with patch("services.retrieval_service.generate_grounded_answer") as generate:
            response = answer_question("What is the benefit?", [], vector_store)

        self.assertEqual(response.answer, NO_INFORMATION_ANSWER)
        self.assertEqual(response.sources, [])
        generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
