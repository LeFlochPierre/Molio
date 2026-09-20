import copy
import json
from pathlib import Path
import tempfile
import unittest

from cyp_pipeline.benchmark import (METHODS, assay_pairs, compare_assays, compare_scores,
                                    experiment_cases, load_boltz, load_observations,
                                    load_uma, main, source)
from cyp_pipeline.core import ValidationError


CASES = experiment_cases(json.loads(Path('configs/experiment.json').read_text()))


def observation(isoform, value, method='Boltz-2', seed='42', **extra):
    return {'system_id': f'S-fadrozole-{isoform}', 'method': method, 'metric': METHODS[method]['metric'],
            'value': value, 'replicate': seed, 'protocol_id': 'same-protocol', 'model_version': 'test-version',
            'status': 'completed', 'synthetic': False, 'source': {'sha256': 'test-native-output'}, **extra}


def comparison(rows, method='Boltz-2'):
    return next(r for r in compare_scores(CASES, rows) if r['ligand'] == 'S-fadrozole' and r['method'] == method)


class BenchmarkTests(unittest.TestCase):
    def test_model_native_signs_and_boltz_ratio(self):
        for method, spec in METHODS.items():
            with self.subTest(method=method):
                rows = [observation('CYP11B1', -1, method), observation('CYP11B2', -2, method)]
                result = comparison(rows, method)
                self.assertEqual(result['preference'], 'CYP11B2' if spec['lower_is_better'] else 'CYP11B1')
                self.assertEqual(result['mean_delta_B2_minus_B1'], -1)
                self.assertEqual(result['status'], 'single_replicate_pilot')
                self.assertIsNone(result['delta_sample_sd'])
                if method == 'Boltz-2':
                    self.assertEqual(result['predicted_IC50_ratio_B1_over_B2'], 10)
                else:
                    self.assertNotIn('predicted_IC50_ratio_B1_over_B2', result)

    def test_missing_or_differently_seeded_pairs_remain_unresolved(self):
        one = observation('CYP11B1', -1)
        for rows in ([one], [one, observation('CYP11B2', -2, seed='43')],
                     [one, observation('CYP11B2', -2), observation('CYP11B1', -3, seed='43')]):
            result = comparison(rows)
            self.assertEqual(result['status'], 'unresolved')
            self.assertIsNone(result['preference'])
            self.assertNotIn('mean_delta_B2_minus_B1', result)

    def test_mismatched_protocol_and_model_not_pooled(self):
        for key in ('protocol_id', 'model_version'):
            rows = [observation('CYP11B1', -1), observation('CYP11B2', -2, **{key: 'different'})]
            variants = [r for r in compare_scores(CASES, rows) if r['ligand'] == 'S-fadrozole' and r['method'] == 'Boltz-2']
            self.assertEqual(len(variants), 2)
            self.assertTrue(all(r['status'] == 'unresolved' and r['preference'] is None for r in variants))

    def test_replicate_disagreement_is_visible(self):
        rows = [observation('CYP11B1', 0), observation('CYP11B2', -1),
                observation('CYP11B1', 0, seed='43'), observation('CYP11B2', 2, seed='43')]
        result = comparison(rows)
        self.assertIsNone(result['preference'])
        self.assertEqual(result['delta_range'], [-1, 2])
        self.assertAlmostEqual(result['delta_sample_sd'], 2.12132034356)

    def test_wrong_stereochemistry_not_paired(self):
        rows = [observation('CYP11B1', -1),
                observation('CYP11B2', -2, system_id='R-fadrozole-CYP11B2')]
        self.assertEqual(comparison(rows)['status'], 'unresolved')

    def test_ineligible_scores_rejected(self):
        for update in ({'synthetic': True}, {'synthetic': None}, {'status': 'failed'},
                       {'value': float('nan')}, {'value': float('inf')}, {'value': True},
                       {'metric': 'affinity_probability_binary'}, {'metric': 'plddt'},
                       {'method': 'RFdiffusion'}, {'system_id': 'unknown'},
                       {'protocol_id': ''}, {'model_version': ''}, {'replicate': True}, {'source': {}}):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                compare_scores(CASES, [{**observation('CYP11B1', -1), **update}])

    def test_duplicate_replicates_rejected(self):
        row = observation('CYP11B1', -1)
        with self.assertRaises(ValidationError):
            compare_scores(CASES, [row, copy.deepcopy(row)])
        with self.assertRaises(ValidationError):
            compare_scores(CASES, [row, {**row, 'replicate': 42}])

    def test_native_source_hashed_and_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            native = root / 'native.txt'
            native.write_text('CNNaffinity: 7.0\n')
            row = observation('CYP11B1', 7, method='GNINA', source_path='native.txt')
            path = root / 'records.json'
            path.write_text(json.dumps({'observations': [row]}))
            rows = load_observations(path)
            self.assertEqual(rows[0]['source']['path'], str(native))
            self.assertEqual(len(rows[0]['source']['sha256']), 64)
            native.unlink()
            with self.assertRaises(FileNotFoundError):
                load_observations(path)

    def test_generic_import_cannot_bypass_native_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'records.json'
            for method in ('UMA-exchange', 'Boltz-2'):
                path.write_text(json.dumps({'observations': [observation('CYP11B1', -1, method)]}))
                with self.assertRaises(ValidationError):
                    load_observations(path)

    def test_boltz_native_import_retains_confidence_without_scoring_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / 'input.yaml'
            input_path.write_text('version: 1\n')
            manifest_path = root / 'manifest.json'
            manifest_path.write_text('{}')
            affinity = root / 'affinity.json'
            affinity.write_text(json.dumps({'affinity_pred_value': -2, 'affinity_probability_binary': 0.8}))
            run = {'schema_version': 1, 'model': 'boltz2', 'status': 'completed', 'model_version': '2.2.1',
                   'protocol_id': 'test', 'seeds': [42], 'checkpoints': [{'sha256': 'checkpoint'}],
                   'source_manifest': source(manifest_path),
                   'cases': [{**next(c for c in CASES if c['system_id'] == 'S-fadrozole-CYP11B1'),
                              'input_path': str(input_path), 'input_sha256': source(input_path)['sha256']}],
                   'runs': [{'seed': 42, 'status': 'completed', 'returncode': 0,
                             'predictions': [{'system_id': 'S-fadrozole-CYP11B1', 'affinity_path': str(affinity),
                                              'affinity_sha256': source(affinity)['sha256']}]}]}
            path = root / 'run_manifest.json'
            path.write_text(json.dumps(run))
            rows = load_boltz(root, CASES)
            self.assertEqual(rows[0]['value'], -2)
            self.assertEqual(rows[0]['binder_probability'], 0.8)
            self.assertTrue(rows[0]['provisional'])
            input_path.write_text('changed')
            with self.assertRaises(ValidationError):
                load_boltz(root, CASES)

    def test_assay_comparison_does_not_convert_uma_energy_to_ic50(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'assays.json'
            path.write_text(json.dumps({'schema_version': 1, 'measurements': [
                {'ligand': 'S-fadrozole', 'isoform': iso, 'endpoint': 'IC50', 'species': 'Homo sapiens',
                 'value_nM': value, 'source_url': 'https://example.test/study', 'assay_id': 'fixture'}
                for iso, value in [('CYP11B1', 40), ('CYP11B2', 160)]]}))
            pairs = assay_pairs(path, CASES)
            self.assertEqual(pairs[0]['preference'], 'CYP11B1')
            rows = [observation('CYP11B1', -2, 'UMA-exchange'), observation('CYP11B2', -1, 'UMA-exchange')]
            evaluation = next(r for r in compare_assays(compare_scores(CASES, rows), pairs) if r['method'] == 'UMA-exchange')
            self.assertTrue(evaluation['direction_agrees'])
            self.assertIsNone(evaluation['predicted_minus_observed_log10_ratio'])

    def test_raw_uma_or_synthetic_result_cannot_become_selectivity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'result.json'
            for data in ({'energy_eV': -100, 'status': 'completed'},
                         {'descriptor': 'ligand_water_exchange_eV', 'synthetic': True},
                         {'descriptor': 'ligand_water_exchange_eV', 'synthetic': False,
                          'backend': {'synthetic': False}, 'status': 'unresolved'}):
                path.write_text(json.dumps(data))
                with self.assertRaises(ValidationError):
                    load_uma(path, CASES)

    def test_report_lists_all_cases_without_fabricating_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'report'
            self.assertEqual(main(['report', '--out', str(out)]), 0)
            result = json.loads((out / 'benchmark.json').read_text())
            self.assertEqual(len(result['cases']), 4)
            self.assertEqual(len(result['comparisons']), 8)
            self.assertEqual(result['observations'], [])
            self.assertTrue(all(r['status'] == 'not_run' for r in result['comparisons']))
            self.assertEqual(main(['report', '--out', str(out)]), 2)


if __name__ == '__main__':
    unittest.main()
