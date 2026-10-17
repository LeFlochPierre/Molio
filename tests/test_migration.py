"""Protect existing data and the sequence used by the reference protocol."""
from pathlib import Path
import tempfile
import unittest
from molio.paths import default_project_dir
from molio.experiments import target_sequence
from molio.sequence import domain_sequence


class MigrationTests(unittest.TestCase):
    def test_storage_selection_preserves_existing_projects(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertEqual(default_project_dir(root), root/'work/molio')
            (root/'work/whatif').mkdir(parents=True)
            self.assertEqual(default_project_dir(root), root/'work/whatif')
            (root/'work/molio').mkdir()
            self.assertEqual(default_project_dir(root), root/'work/molio')

    def test_reference_sequence_unchanged(self):
        sequence, source = target_sequence()
        self.assertEqual(len(sequence), 125)
        self.assertEqual(source['sequence_sha256'], '7772c2640312283ecb713a7f52e9ffee3c33c9196e69fccdaf0767e26884c8f4')
        self.assertEqual(source['expression_tags_removed'], [42, 43])
        for accession, start, end, chain in [('WRONG',44,168,'A'), ('O60885',1,168,'A'), ('O60885',44,168,'Z')]:
            with self.subTest(accession=accession, start=start, chain=chain):
                with self.assertRaises(ValueError):
                    domain_sequence(source['path'], accession, start=start, end=end, chain=chain)
