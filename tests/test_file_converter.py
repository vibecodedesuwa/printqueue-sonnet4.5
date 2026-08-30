import os
import tempfile
import unittest

from PIL import Image

from printqueue.services.file_converter import convert_if_needed


class FileConverterTests(unittest.TestCase):
    def test_png_is_normalized_to_a4_pdf(self):
        with tempfile.TemporaryDirectory() as directory:
            source = os.path.join(directory, "transparent.png")
            Image.new("RGBA", (160, 90), (255, 0, 0, 128)).save(source)

            result = convert_if_needed(source)

            self.assertTrue(result.endswith(".printq.pdf"))
            self.assertTrue(os.path.isfile(result))
            with open(result, "rb") as converted:
                self.assertEqual(converted.read(4), b"%PDF")

    def test_pdf_remains_direct(self):
        self.assertEqual(convert_if_needed("example.pdf"), "example.pdf")


if __name__ == "__main__":
    unittest.main()
