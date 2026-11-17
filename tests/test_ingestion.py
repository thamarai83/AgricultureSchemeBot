import unittest

from services.pdf_loader import (
    MAX_UPLOAD_BYTES,
    get_content_sha256,
    make_stored_filename,
    validate_pdf_upload,
)


class PdfValidationTests(unittest.TestCase):
    def test_accepts_pdf_and_returns_base_filename(self):
        name = validate_pdf_upload(
            r"C:\uploads\scheme.pdf",
            b"%PDF-1.7\nPDF content",
        )

        self.assertEqual(name, "scheme.pdf")

    def test_rejects_non_pdf_extension(self):
        with self.assertRaisesRegex(ValueError, r"\.pdf"):
            validate_pdf_upload("scheme.txt", b"%PDF-1.7\ncontent")

    def test_rejects_invalid_pdf_signature(self):
        with self.assertRaisesRegex(ValueError, "signature"):
            validate_pdf_upload("scheme.pdf", b"not a PDF")

    def test_rejects_file_over_size_limit(self):
        with self.assertRaisesRegex(ValueError, "20 MB"):
            validate_pdf_upload("scheme.pdf", b"%PDF-" + b"x" * MAX_UPLOAD_BYTES)

    def test_hash_is_stable_and_stored_name_has_no_path(self):
        content = b"%PDF-1.7\ncontent"

        self.assertEqual(get_content_sha256(content), get_content_sha256(content))
        stored_name = make_stored_filename(r"..\private\scheme.pdf")
        self.assertEqual(stored_name, stored_name.split("\\")[-1])
        self.assertTrue(stored_name.endswith("_scheme.pdf"))


if __name__ == "__main__":
    unittest.main()
