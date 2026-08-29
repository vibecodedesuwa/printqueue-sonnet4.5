import pathlib
import unittest


class QuickA4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        templates = pathlib.Path(__file__).parents[1] / "templates"
        cls.desktop = (templates / "editor.html").read_text(encoding="utf-8")
        cls.mobile = (templates / "qr_upload.html").read_text(encoding="utf-8")

    def test_thai_rendering_keeps_combining_marks_in_one_text_run(self):
        for template in (self.desktop, self.mobile):
            self.assertIn("letter-spacing: 0 !important", template)
            self.assertIn("document.fonts.load", template)
            self.assertIn("ทดสอบการพิมพ์ภาษาไทย", template)

    def test_only_qr_page_requests_direct_printing(self):
        self.assertIn('name="submission_source" value="qr_file_upload"', self.mobile)
        self.assertIn("formData.append('submission_source', 'qr_a4_editor')", self.mobile)
        self.assertNotIn("submission_source", self.desktop)


if __name__ == "__main__":
    unittest.main()
