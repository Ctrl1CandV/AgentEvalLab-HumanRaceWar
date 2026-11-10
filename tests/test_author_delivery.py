from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from tools.receive_author_delivery import inventory, receive, relative_name


class AuthorDeliveryTests(unittest.TestCase):
    def fixture(self, root):
        source = root/'incoming'; (source/'bot').mkdir(parents=True)
        (source/'bot/main.py').write_bytes(b'# test fixture, never executed\n')
        (source/'NOTES.md').write_text('First delivery; claims unverified.\n')
        self.checksums(source)
        return source

    def checksums(self, source):
        (source/'SHA256SUMS').write_text(''.join(
            f'{sha256(p.read_bytes()).hexdigest()}  {p.relative_to(source).as_posix()}\n'
            for p in sorted((source/'bot').rglob('*')) if p.is_file()))

    def test_exact_archive_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = self.fixture(root)
            destination = root/'private/author/r01'; receipt = root/'private/receipt.json'
            r = receive(source, destination, receipt, root=root)
            self.assertEqual(inventory(source), inventory(destination))
            self.assertEqual(r['files'], 3)
            self.assertFalse(r['runtimeChecked'])
            with self.assertRaises(ValueError): receive(source, destination, receipt, root=root)
            with self.assertRaises(ValueError): receive(source, root/'public', root/'private/r.json', root=root)

    def test_mismatch_missing_extra_and_duplicate_checksums(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.fixture(Path(tmp)); good = (source/'SHA256SUMS').read_text()
            for text in ['', good+good, good.replace('bot/main.py','../main.py'), '0'*64+'  bot/main.py\n']:
                (source/'SHA256SUMS').write_text(text)
                with self.assertRaises(ValueError): inventory(source)
            (source/'SHA256SUMS').write_text(good)
            (source/'bot/unlisted.hpp').write_text('not listed')
            with self.assertRaises(ValueError): inventory(source)

    def test_links_special_files_and_metadata_extra(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.fixture(Path(tmp))
            link = source/'bot/link'; link.symlink_to(source/'bot/main.py')
            with self.assertRaises(ValueError): inventory(source)
            link.unlink()
            import os
            fifo = source/'bot/fifo'; os.mkfifo(fifo)
            with self.assertRaises(ValueError): inventory(source)
            fifo.unlink()
            (source/'extra').mkdir()
            with self.assertRaises(ValueError): inventory(source)

    def test_entry_format_and_size_limit(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            source = self.fixture(Path(tmp))
            (source/'bot/main.cpp').write_text('// not compiled\n'); self.checksums(source)
            with self.assertRaises(ValueError): inventory(source)
            (source/'bot/main.py').unlink(); self.checksums(source)
            self.assertIn('bot/main.cpp', inventory(source))
            with patch('tools.receive_author_delivery.MAX_FILE', 10):
                with self.assertRaises(ValueError): inventory(source)
            with patch('tools.receive_author_delivery.MAX_TOTAL', 10):
                with self.assertRaises(ValueError): inventory(source)

    def test_path_normalization(self):
        for name in ('', '.', '/bot/main.py', '../main.py', 'bot/../main.py', './bot/main.py', 'bot//main.py',
                     'bot\\main.py', 'bot/main.py\n'):
            with self.assertRaises(ValueError): relative_name(name)
        self.assertEqual(relative_name('bot/nested/helper.hpp'), 'bot/nested/helper.hpp')

    def test_no_execution_and_source_not_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = self.fixture(root)
            body = b'raise RuntimeError("must not execute")\n'
            (source/'bot/main.py').write_bytes(body); self.checksums(source)
            before = inventory(source)
            receive(source, root/'private/r01', root/'private/receipt.json', root=root)
            self.assertEqual(inventory(source), before)


if __name__ == '__main__': unittest.main()
