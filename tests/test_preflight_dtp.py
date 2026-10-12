import unittest
from io import BytesIO

from reportlab.pdfgen import canvas
from services.preflight_dtp import analyze_pdf, build_preflight_pdf


class PreflightDtpTests(unittest.TestCase):
    def test_invalid_file_is_blocked(self):
        report = analyze_pdf(b"not a pdf", "bad.pdf")
        self.assertEqual(report["overall_status"], "blokada")

    def test_pdf_report_is_generated(self):
        data = BytesIO(); page = canvas.Canvas(data); page.drawString(10, 10, "Test"); page.save()
        report = analyze_pdf(data.getvalue(), "test.pdf")
        self.assertEqual(report["metrics"]["pages"], 1)
        self.assertTrue(build_preflight_pdf(report).startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
