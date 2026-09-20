import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cyp_pipeline.benchmark_boltz import _domain_sequence, prepare_boltz, run_boltz


def pdb_record(fields, width=80):
    record = [' '] * width
    for offset, text in fields:
        record[offset:offset + len(text)] = text
    return ''.join(record)


def write_pdb(path, pdb_id, accession, db_start, terminal_histidines):
    tags = [(number, residue) for number, residue in zip(range(db_start - 7, db_start),
             ['MET', 'ALA', 'LYS', 'LYS', 'THR', 'SER', 'SER'])]
    tags.extend((number, 'HIS') for number in range(504, 504 + terminal_histidines))
    core = ['ARG'] * (34 - db_start) + ['ALA'] * 470
    residues = [residue for _, residue in tags[:7]] + core + ['HIS'] * terminal_histidines
    lines = [pdb_record([(0, 'DBREF '), (7, pdb_id), (12, 'A'), (14, f'{db_start:4d}'),
                        (20, ' 503'), (26, 'UNP'), (33, accession),
                        (55, f'{db_start:5d}'), (62, '  503')])]
    lines.extend(pdb_record([(0, 'SEQADV'), (7, pdb_id), (12, residue), (16, 'A'),
                             (18, f'{number:4d}'), (49, 'EXPRESSION TAG')])
                 for number, residue in tags)
    lines.extend(pdb_record([(0, 'SEQRES'), (7, f'{index // 13 + 1:3d}'), (11, 'A'),
                             (13, f'{len(residues):4d}'), (19, ' '.join(residues[index:index + 13]))])
                 for index in range(0, len(residues), 13))
    path.write_text('\n'.join(lines) + '\n')


class BoltzBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = self.root / 'data/raw'
        self.raw.mkdir(parents=True)
        write_pdb(self.raw / '6M7X.pdb', '6M7X', 'P15538', 31, 4)
        write_pdb(self.raw / '4FDH.pdb', '4FDH', 'P19099', 34, 6)
        self.experiment = self.root / 'configs/experiment.json'
        self.experiment.parent.mkdir()
        self.experiment.write_text(json.dumps({'systems': [
            {'system_id': f'{ligand}-{isoform}', 'ligand': ligand, 'isoform': isoform,
             'starting_pdb': '6M7X' if isoform == 'CYP11B1' else '4FDH'}
            for ligand in ('R-fadrozole', 'S-fadrozole') for isoform in ('CYP11B1', 'CYP11B2')
        ]}))

    def prepare(self, mode='server'):
        return prepare_boltz(self.experiment, self.root / 'prepared', mode)

    def test_matching_domain_and_stereochemistry_preserve_heme(self):
        manifest = self.prepare()
        self.assertEqual(manifest['status'], 'prepared_not_run')
        self.assertEqual(len(manifest['cases']), 4)
        for case in manifest['cases']:
            document = json.loads(Path(case['input_path']).read_text())
            self.assertEqual(document['sequences'][0]['protein']['sequence'], 'A' * 470)
            self.assertNotIn('msa', document['sequences'][0]['protein'])
            self.assertEqual(document['sequences'][1], {'ligand': {'id': 'H', 'ccd': 'HEM'}})
            self.assertEqual(document['sequences'][2]['ligand']['ccd'],
                             'JD7' if case['ligand'].startswith('S-') else '0T3')
            self.assertEqual(document['properties'], [{'affinity': {'binder': 'L'}}])
            self.assertNotIn('constraints', document)
            self.assertNotIn('templates', document)
            self.assertEqual(case['sequence_source']['sequence_length'], 470)
        with self.assertRaises(FileExistsError):
            self.prepare()

    def test_empty_msa_is_explicit_separate_protocol(self):
        manifest = self.prepare('empty')
        self.assertEqual(manifest['recipe']['msa_mode'], 'empty')
        document = json.loads(Path(manifest['cases'][0]['input_path']).read_text())
        self.assertEqual(document['sequences'][0]['protein']['msa'], 'empty')

    def test_unmapped_or_incomplete_sequence_is_rejected(self):
        path = self.raw / '6M7X.pdb'
        path.write_text('\n'.join(line for line in path.read_text().splitlines()
                                 if not line.startswith('SEQADV')))
        with self.assertRaisesRegex(ValueError, 'cannot be mapped'):
            _domain_sequence(path, 'P15538')

    def test_modified_input_is_rejected_before_execution(self):
        manifest = self.prepare()
        Path(manifest['cases'][0]['input_path']).write_text('{}')
        with self.assertRaisesRegex(ValueError, 'input changed'):
            run_boltz(self.root / 'prepared/manifest.json', self.root / 'run')
        self.assertFalse((self.root / 'run').exists())

    @patch('cyp_pipeline.benchmark_boltz._installed_version', return_value='2.2.1')
    def test_zero_exit_without_predictions_is_not_success(self, version):
        self.prepare()
        with patch('cyp_pipeline.benchmark_boltz.subprocess.run', return_value=subprocess.CompletedProcess([], 0)) as run:
            result = run_boltz(self.root / 'prepared/manifest.json', self.root / 'run',
                               boltz_executable=sys.executable)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['runs'][0]['status'], 'incomplete_outputs')
        argv = run.call_args.args[0]
        self.assertIn('--use_msa_server', argv)
        self.assertEqual(argv[argv.index('--seed') + 1], '42')
        self.assertTrue((self.root / 'run/run_manifest.json').is_file())

    @patch('cyp_pipeline.benchmark_boltz._installed_version', return_value='2.2.1')
    def test_timeout_is_recorded_and_remaining_seeds_not_started(self, version):
        self.prepare()
        with patch('cyp_pipeline.benchmark_boltz.subprocess.run', side_effect=subprocess.TimeoutExpired('boltz', 1)):
            result = run_boltz(self.root / 'prepared/manifest.json', self.root / 'run',
                               boltz_executable=sys.executable, seeds=[42, 43, 44], timeout_seconds=1)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(len(result['runs']), 1)
        self.assertEqual(result['runs'][0]['status'], 'timed_out')
        self.assertIsNone(result['runs'][0]['returncode'])


if __name__ == '__main__':
    unittest.main()
