"""Exercise the public template exporter from a ZIP, as shipped in an apworld."""

import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile


WORKSPACE = Path(__file__).resolve().parents[1]


class PublicYamlTests(unittest.TestCase):
    def test_zipped_export_preserves_public_template_and_existing_edits(self):
        source = WORKSPACE / "release" / "Dungeon Defenders.yaml"
        content = source.read_bytes()
        self.assertIn(b"name: PlayerName", content)
        self.assertNotIn(b"Haywire", content)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            archive = folder / "template-test.apworld"
            package = "dd1_yaml_export_test"
            with ZipFile(archive, "w") as bundle:
                bundle.writestr(package + "/__init__.py", "")
                bundle.write(WORKSPACE / "apworld" / "dungeon_defenders" / "public_yaml.py",
                             package + "/public_yaml.py")
                bundle.write(source, package + "/Dungeon Defenders.yaml")
            sys.path.insert(0, str(archive))
            try:
                exporter = importlib.import_module(package + ".public_yaml")
                destination = folder / "Player options.yaml"
                exporter.export_template(destination)
                self.assertEqual(destination.read_bytes(), content)
                destination.write_text("name: MyEditedSlot\n", encoding="utf-8")
                with self.assertRaises(FileExistsError):
                    exporter.export_template(destination)
                self.assertEqual(destination.read_text(encoding="utf-8"), "name: MyEditedSlot\n")
            finally:
                sys.path.remove(str(archive))
                sys.modules.pop(package + ".public_yaml", None)
                sys.modules.pop(package, None)


if __name__ == "__main__":
    unittest.main()
