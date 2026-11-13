"""Pure archive/ledger checks; never compile, import bots, step games or launch bots."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from tools import archive_round as archive


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        parent = archive.ROOT / 'runs/unit-temp'
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self.temp.name)
        (self.root / 'private').mkdir()
        self.legacy = self.root / 'private/HIDDEN.sha256'
        self.legacy.write_text(hashlib.sha256(b'legacy').hexdigest() + '  private/old.txt\n')
        archive.baseline('private/HIDDEN.sha256', 1, 6, root=self.root)
        self.round = self.root / 'private/new-round'
        self.round.mkdir()
        (self.round / 'evidence.bin').write_bytes(b'new opaque evidence')

    def tearDown(self):
        for parent, dirs, files in os.walk(self.root):
            Path(parent).chmod(0o700)
            for name in dirs:
                p = Path(parent) / name
                if not p.is_symlink():
                    p.chmod(0o700)
            for name in files:
                p = Path(parent) / name
                if not p.is_symlink():
                    p.chmod(0o600)
        self.temp.cleanup()

    def test_seal_verify_and_legacy_preserved(self):
        old = self.legacy.read_bytes()
        entry = archive.seal(self.round, 'round01', root=self.root)
        self.assertEqual(entry['files'], 1)
        self.assertEqual(archive.verify_round('round01', root=self.root)['bytes'], 19)
        self.assertEqual(self.legacy.read_bytes(), old)
        self.assertEqual(len(archive.chain(self.root)[0]), 2)

    def test_duplicate_does_not_rewrite_prefix(self):
        archive.seal(self.round, 'round01', root=self.root)
        before = (self.root / 'private/ledger.jsonl').read_bytes()
        with self.assertRaises(ValueError):
            archive.seal(self.round, 'round01', root=self.root)
        self.assertEqual((self.root / 'private/ledger.jsonl').read_bytes(), before)

    def test_changed_bytes_rejected(self):
        archive.seal(self.round, 'round01', root=self.root)
        target = self.round / 'evidence.bin'
        target.chmod(0o600)
        target.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            archive.verify_round('round01', root=self.root)

    def test_added_file_rejected(self):
        archive.seal(self.round, 'round01', root=self.root)
        self.round.chmod(0o700)
        (self.round / 'extra').write_bytes(b'extra')
        with self.assertRaises(ValueError):
            archive.verify_round('round01', root=self.root)

    def test_writable_archive_rejected(self):
        archive.seal(self.round, 'round01', root=self.root)
        (self.round / 'evidence.bin').chmod(0o600)
        with self.assertRaises(ValueError):
            archive.verify_round('round01', root=self.root)

    def test_links_and_special_files_rejected(self):
        link = self.round / 'linked'
        link.symlink_to(self.legacy)
        with self.assertRaises(ValueError):
            archive.seal(self.round, 'linked', root=self.root)
        link.unlink()
        fifo = self.round / 'fifo'
        os.mkfifo(fifo)
        with self.assertRaises(ValueError):
            archive.seal(self.round, 'fifo', root=self.root)

    def test_unsafe_paths_and_self_inclusion(self):
        for name in ('../escape', '/absolute', 'private/../escape', 'private\\escape'):
            with self.assertRaises(ValueError):
                archive.local_path(self.root, name)
        with self.assertRaises(ValueError):
            archive.seal(self.root / 'private', 'whole-private', root=self.root)
        with self.assertRaises(ValueError):
            archive.seal(self.round, '../escape', root=self.root)

    def test_truncated_and_tampered_chain(self):
        ledger = self.root / 'private/ledger.jsonl'
        original = ledger.read_bytes()
        ledger.write_bytes(original[:-1])
        with self.assertRaises(ValueError):
            archive.chain(self.root)
        row = json.loads(original)
        row['previousSha256'] = 'f' * 64
        ledger.write_bytes(archive.encoded(row) + b'\n')
        with self.assertRaises(ValueError):
            archive.chain(self.root)

    def test_changed_manifest_blocks_publication(self):
        archive.seal(self.round, 'round01', root=self.root)
        manifest = self.root / 'private/manifests/round01.json'
        manifest.chmod(0o600)
        manifest.write_bytes(b'{}')
        with self.assertRaises(ValueError):
            archive.hidden_digests(self.root)

    def test_publication_guard_includes_new_rounds(self):
        archive.seal(self.round, 'round01', root=self.root)
        hidden = archive.hidden_digests(self.root)
        self.assertIn(hashlib.sha256(b'legacy').hexdigest(), hidden)
        self.assertIn(hashlib.sha256(b'new opaque evidence').hexdigest(), hidden)
        self.assertIn(archive.sha_file(self.root / 'private/manifests/round01.json'), hidden)
        self.assertIn(archive.sha_file(self.root / 'private/ledger.jsonl'), hidden)


if __name__ == '__main__':
    unittest.main()
