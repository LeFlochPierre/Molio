import json
import unittest
from decimal import Decimal

from cyp_pipeline.calibrated_selectivity import (
    HANDOFF, analyze_calibrated, boltz_rows, empirical_ratio, exchange_energy,
)


class CalibratedSelectivityTests(unittest.TestCase):
    def analyze(self, candidate='osilodrostat', policy='selected_fit'):
        return analyze_calibrated({'candidate_id': candidate, 'pose_policy': policy})

    def test_supplied_component_arithmetic_and_expected_fits(self):
        for candidate, expected, gap in [('osilodrostat', 3.229576543, .238037109),
                                         ('baxdrostat', 103.364756449, .941764831)]:
            with self.subTest(candidate=candidate):
                result = self.analyze(candidate)
                fit = result['empirical_fit']
                self.assertAlmostEqual(fit['S_B1_over_B2'], expected, places=5)
                self.assertAlmostEqual(fit['B1_minus_B2_eV'], gap, places=8)
                self.assertEqual(fit['preferred'], 'CYP11B2')
                self.assertEqual(fit['status'], 'training_fit')
                self.assertIsNone(result['fold_selectivity'])
                self.assertFalse(result['validated_selectivity'])
                self.assertFalse(result['execution']['new_UMA_inference'])
                self.assertFalse(result['source']['independently_audited'])
                self.assertEqual(result['overall_status'], 'unresolved')
                json.dumps(result, allow_nan=False)

    def test_decimal_subtraction_retains_precision(self):
        energies = {'cluster_ligand': '-532769.5394522406', 'cluster_water': '-514016.4731526081',
                    'free_water': '-2079.8650510885', 'free_ligand': '-20830.9563605019'}
        self.assertEqual(exchange_energy(energies), Decimal('-1.9749902191'))

    def test_minima_not_silently_replaced_by_fit_selection(self):
        result = self.analyze('baxdrostat', 'original_minima')
        self.assertAlmostEqual(result['empirical_fit']['S_B1_over_B2'], 5.864, places=2)
        self.assertGreater(result['selected_exchange']['S_B1_over_B2'], 100)
        self.assertEqual(result['empirical_fit']['status'], 'same_coefficient_pose_sensitivity')
        self.assertEqual(result['screen']['status'], 'below_threshold')
        self.assertEqual(self.analyze('baxdrostat')['screen']['status'], 'above_threshold')

    def test_missing_convergence_stops_ratio(self):
        for policy in ('selected_fit', 'original_minima'):
            result = self.analyze('metyrapone', policy)
            self.assertIsNone(result['empirical_fit'])
            self.assertEqual(result['quality']['accepted_B2'], 0)
            self.assertEqual(result['screen']['status'], 'unresolved')
            self.assertFalse(result['execution']['component_arithmetic_independently_checked'])

    def test_sign_ratio_and_tie(self):
        forward = empirical_ratio(.2, 2)
        reverse = empirical_ratio(-.2, 2)
        self.assertAlmostEqual(forward['S_B1_over_B2'] * reverse['S_B1_over_B2'], 1)
        self.assertEqual(reverse['preferred'], 'CYP11B1')
        self.assertIsNone(empirical_ratio(0, 2)['preferred'])
        for value in ('NaN', 'Infinity', '1000'):
            with self.assertRaises(ValueError):
                empirical_ratio(value, 2)

    def test_reject_arbitrary_candidates_fields_policies_and_component_errors(self):
        for payload in ({}, [], {'candidate_id': 'r_fadrozole', 'pose_policy': 'selected_fit'},
                        {'candidate_id': 'osilodrostat', 'pose_policy': 'best'},
                        {'candidate_id': 'osilodrostat', 'pose_policy': 'selected_fit', 'coefficient': 10}):
            with self.assertRaises(ValueError):
                analyze_calibrated(payload)
        valid = {key: '0' for key in ('cluster_ligand', 'cluster_water', 'free_ligand', 'free_water')}
        for invalid in ({}, {**valid, 'free_water': 'NaN'}, {**valid, 'free_water': True}, {**valid, 'free_water': 'x'}):
            with self.assertRaises(ValueError):
                exchange_energy(invalid)

    def test_invalid_boltz_is_retained_only_for_audit(self):
        source = json.loads(HANDOFF.read_text())
        rows = boltz_rows(source, 's_fadrozole')
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row['usable_ratio'] is None for row in rows))
        self.assertTrue(all(row['raw_ratio_from_rounded_y'] > 0 for row in rows))
        self.assertAlmostEqual(self.analyze()['boltz'][0]['usable_ratio'], 6.27769, places=4)

    def test_assays_and_selection_provenance_remain_separate(self):
        osilo, bax = self.analyze(), self.analyze('baxdrostat')
        self.assertEqual(osilo['fit_assay']['id'], 'O01')
        self.assertEqual(osilo['other_assays'][0]['id'], 'O02')
        self.assertEqual(osilo['fit_assay']['endpoint'], 'IC50')
        self.assertEqual(bax['fit_assay']['endpoint'], 'Ki')
        self.assertEqual(bax['calibration']['searched_combinations'], 360)
        self.assertEqual(bax['selected_exchange']['enzymes']['CYP11B2']['start'], 3)
        self.assertFalse(bax['calibration']['transfer_validated'])


if __name__ == '__main__':
    unittest.main()
