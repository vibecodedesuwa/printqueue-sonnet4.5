import pathlib
import sys
import types
import unittest


package = sys.modules.setdefault("printqueue", types.ModuleType("printqueue"))
package.__path__ = [str(pathlib.Path(__file__).parents[1] / "printqueue")]

from printqueue.filenames import clean_display_filename, unique_storage_filename


class FilenameTests(unittest.TestCase):
    def test_thai_display_filename_is_preserved(self):
        self.assertEqual(clean_display_filename(r"..\รายงานประจำเดือน.pdf"), "รายงานประจำเดือน.pdf")

    def test_storage_filename_keeps_extension_without_exposing_path(self):
        stored = unique_storage_filename("รายงานประจำเดือน.pdf", prefix="abc")
        self.assertEqual(stored, "abc_document.pdf")
        self.assertNotIn("/", stored)
        self.assertNotIn("\\", stored)


if __name__ == "__main__":
    unittest.main()
