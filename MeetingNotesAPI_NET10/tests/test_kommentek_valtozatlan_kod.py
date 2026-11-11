"""A tananyag-kommentek eltávolításával az eredeti programutasításoknak kell visszaállniuk."""
from pathlib import Path
import hashlib
import json
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
HASHES = json.loads((ROOT / 'tests' / 'eredeti_utasitasok_sha256.json').read_text(encoding='utf-8'))


def remove_new_teacher_comments(path: Path) -> str:
    """Csak az új TANANYAG és oktatói címsorokat szedi ki; a régi kommentek érintetlenek."""
    cleaned = []
    for line in path.read_text(encoding='utf-8-sig').splitlines(keepends=True):
        s = line.strip()
        if path.suffix == '.cs' and (
            s.startswith('// TANANYAG –') or s.startswith('// =====') or
            s.startswith('// OKTATÓI FORRÁSKÓD') or
            s.startswith('// A magyarázó kommentek') or
            s.startswith('// A működő programutasításokat')
        ): continue
        if path.suffix == '.ps1' and (
            s.startswith('# TANANYAG –') or s.startswith('# ====') or
            s.startswith('# OKTATÓI MAGYARÁZAT') or
            s.startswith('# A megjegyzések bemutatják') or
            s.startswith('# Az eredeti futtatási')
        ): continue
        if path.suffix == '.bat' and (
            s.startswith('REM TANANYAG -') or s.startswith('REM ===') or
            s.startswith('REM OKTATOI MAGYARAZAT') or
            s.startswith('REM A kommentek oktatasi') or
            s.startswith('REM A CMD kulonosebb')
        ): continue
        if path.suffix == '.csproj' and s.startswith('<!-- TANANYAG:'): continue
        cleaned.append(line)
    return ''.join(cleaned)


class TeacherCommentIntegrityTests(unittest.TestCase):
    def test_original_program_statements_unchanged(self):
        """Közel soronként kommenteltünk, de a futó utasításokat egyáltalán nem írtuk át."""
        for rel, expected in HASHES.items():
            with self.subTest(path=rel):
                source = remove_new_teacher_comments(ROOT / rel)
                digest = hashlib.sha256(source.encode('utf-8')).hexdigest()
                self.assertEqual(digest, expected)

    def test_project_xml_is_valid(self):
        ET.parse(ROOT / 'MeetingNotesAPI' / 'MeetingNotesAPI.csproj')
        ET.parse(ROOT / 'MeetingNotesAPI.slnx')

    def test_batch_encoding_and_first_line(self):
        for path in (ROOT / 'MeetingNotesAPI' / 'scripts').glob('*.bat'):
            with self.subTest(path=path.name):
                raw = path.read_bytes()
                self.assertFalse(raw.startswith(b'\xef\xbb\xbf'))
                self.assertTrue(raw.startswith(b'@echo off'))
                self.assertTrue(all(b < 128 for b in raw))

    def test_powershell_51_utf8_bom(self):
        for path in (ROOT / 'MeetingNotesAPI' / 'scripts').glob('*.ps1'):
            with self.subTest(path=path.name):
                self.assertTrue(path.read_bytes().startswith(b'\xef\xbb\xbf'))

    def test_explanations_present(self):
        app = ROOT / 'MeetingNotesAPI'
        for path in app.rglob('*.cs'):
            with self.subTest(path=path.name):
                self.assertIn('// TANANYAG –', path.read_text(encoding='utf-8'))

    def test_private_secrets_absent(self):
        self.assertFalse((ROOT / 'MeetingNotesAPI' / 'private' / 'meetingnotes.secrets.json').exists())

if __name__ == '__main__':
    unittest.main(verbosity=2)
