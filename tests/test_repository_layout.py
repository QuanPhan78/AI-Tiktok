"""Check the files needed when cloning the combined repository on another machine."""
import json
from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit

from scripts.package_manifest import ROOT as AUTOMATION, package_files, digest

ROOT = Path(__file__).resolve().parents[1]


class RepositoryLayoutTests(unittest.TestCase):
    def test_packaged_source_manifest_is_complete_and_current(self):
        manifest = json.loads((AUTOMATION / "SOURCE_MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["hash_format"], "sha256-utf8-lf")
        self.assertEqual(manifest["files_sha256"], {name: digest(path) for name, path in package_files()})

    def test_all_eight_characters_have_packaged_images(self):
        folder = ROOT / "knowledge_base/characters"
        characters = json.loads((folder / "library.json").read_text(encoding="utf-8"))
        self.assertEqual([row["id"] for row in characters], [f"NV{i}" for i in range(1, 9)])
        for row in characters:
            self.assertTrue((folder / "images" / row["image_filename"]).is_file(), row["id"])

    def test_documentation_links_resolve_inside_the_clone(self):
        documents = [ROOT / "README.md", AUTOMATION / "README.md", ROOT / "extensions/gemini/README.md"]
        documents += list((ROOT / "docs").glob("*.md"))
        for document in documents:
            for target in re.findall(r"\]\((<[^>]+>|[^\s)]+)\)", document.read_text(encoding="utf-8")):
                target = target.strip("<>")
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                path = (document.parent / unquote(parsed.path)).resolve()
                with self.subTest(document=document.name, target=target):
                    self.assertTrue(path.is_relative_to(ROOT), "Link depends on a path outside this repo")
                    self.assertTrue(path.exists(), "Missing linked file")

    def test_extension_scripts_exist_in_the_release(self):
        folder = ROOT / "extensions/gemini"
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        resources = [manifest["background"]["service_worker"], manifest["action"]["default_popup"]]
        resources += [path for script in manifest["content_scripts"] for path in script["js"]]
        for resource in resources:
            self.assertTrue((folder / resource).is_file(), resource)


if __name__ == "__main__":
    unittest.main()
