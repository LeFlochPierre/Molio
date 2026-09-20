"""Numerical and provenance gates for the hypothetical energy-fold display."""
import copy
import json
import math
import unittest

from cyp_pipeline.interpretation import (
    BOLTZMANN_EV_K, DEFAULT_TEMPERATURE_K, energy_fold_proxy, exchange_preference,
)


def exchange_result(delta=-.1):
    """An arithmetic fixture; no molecular energies are represented as measured."""
    def enzyme(energy):
        values = {'cluster_ligand': energy, 'free_water': 0.,
                  'cluster_water': 0., 'free_ligand': 0.}
        return {'exchange_energy_eV': energy, 'components': {
            name: {'status': 'completed', 'energy_eV': value} for name, value in values.items()}}
    return {'descriptor': 'ligand_water_exchange_eV', 'synthetic': False,
            'status': 'exploratory', 'delta_B2_minus_B1_eV': delta,
            'enzymes': {'CYP11B1': enzyme(0.), 'CYP11B2': enzyme(delta)}}


class EnergyProxyTests(unittest.TestCase):
    def test_sign_magnitude_and_three_significant_digit_display(self):
        for sign, preferred in ((-1, 'CYP11B2'), (1, 'CYP11B1')):
            delta = sign * BOLTZMANN_EV_K * DEFAULT_TEMPERATURE_K * math.log(100)
            result = exchange_preference(exchange_result(delta))
            proxy = result['energy_fold_proxy']
            self.assertEqual(proxy['status'], 'hypothetical_energy_proxy')
            self.assertEqual(proxy['preferred_in_energy_model'], preferred)
            self.assertAlmostEqual(proxy['log10_B2_over_B1'], -sign * 2)
            self.assertAlmostEqual(proxy['log10_fold_magnitude'], 2)
            self.assertAlmostEqual(proxy['fold_magnitude'], 100)
            self.assertEqual(proxy['scientific_notation'], '1 × 10^2')
            self.assertIsNone(result['fold_selectivity'])
            self.assertEqual(result['fold_status'], 'not_identifiable_from_potential_energy')
            self.assertIn('Not binding selectivity', proxy['scope'])

    def test_tie_and_temperature_dependence(self):
        zero = energy_fold_proxy(exchange_result(0))
        self.assertEqual(zero['fold_magnitude'], 1)
        self.assertEqual(zero['scientific_notation'], '1')
        self.assertIsNone(zero['preferred_in_energy_model'])
        cold = energy_fold_proxy(exchange_result(), 298.15)
        warm = energy_fold_proxy(exchange_result(), 596.3)
        self.assertAlmostEqual(cold['log10_fold_magnitude'], warm['log10_fold_magnitude'] * 2)
        self.assertAlmostEqual(cold['fold_magnitude'], warm['fold_magnitude'] ** 2)

    def test_temperature_rejects_invalid_nonfinite_and_bool(self):
        for temperature in (0, -1, True, False, '298.15', None,
                            float('inf'), float('-inf'), float('nan'), 10 ** 400):
            with self.subTest(temperature=temperature), self.assertRaisesRegex(ValueError, 'finite positive'):
                energy_fold_proxy(exchange_result(), temperature)

    def test_status_descriptor_synthetic_and_nonfinite_gates(self):
        cases = []
        for delta in (True, False, None, '0.1', float('nan'), float('inf'), 10 ** 400):
            cases.append({'delta_B2_minus_B1_eV': delta})
        cases += [{'descriptor': 'total_potential_energy'}, {'synthetic': True},
                  {'synthetic': None}, {'status': 'unresolved'}, {'status': 'synthetic_demo'}]
        for changes in cases:
            with self.subTest(changes=changes):
                result = exchange_result()
                result.update(changes)
                proxy = energy_fold_proxy(result)
                self.assertEqual(proxy['status'], 'unavailable')
                self.assertIsNone(proxy['fold_magnitude'])
                self.assertIsNone(proxy['scientific_notation'])

    def test_incomplete_inconsistent_and_synthetic_component_contracts_rejected(self):
        base = exchange_result()
        mutations = [
            lambda r: r.pop('enzymes'),
            lambda r: r['enzymes'].pop('CYP11B1'),
            lambda r: r['enzymes']['CYP11B2']['components'].pop('free_water'),
            lambda r: r['enzymes']['CYP11B1']['components']['free_water'].update(status='failed'),
            lambda r: r['enzymes']['CYP11B1']['components']['free_water'].update(energy_eV=float('nan')),
            lambda r: r['enzymes']['CYP11B1'].update(exchange_energy_eV=1),
            lambda r: r.update(delta_B2_minus_B1_eV=10),
            lambda r: r.update(backend={'synthetic': True}),
            lambda r: r.update(reasons=['Failed preparation']),
        ]
        for mutate in mutations:
            result = copy.deepcopy(base)
            mutate(result)
            proxy = energy_fold_proxy(result)
            self.assertEqual(proxy['status'], 'unavailable')
            self.assertTrue(proxy['reason'])
            self.assertIsNone(proxy['fold_magnitude'])

    def test_old_direction_fixtures_work_but_do_not_unlock_proxy(self):
        result = exchange_result()
        result.pop('enzymes')
        summary = exchange_preference(result)
        self.assertEqual(summary['preferred_in_energy_model'], 'CYP11B2')
        self.assertEqual(summary['energy_fold_proxy']['reason'], 'missing_matched_pair')

    def test_realistic_large_value_carries_warning_not_a_selectivity_verdict(self):
        proxy = energy_fold_proxy(exchange_result(-9.584489277847297))
        self.assertEqual(proxy['status'], 'hypothetical_energy_proxy')
        self.assertEqual(proxy['scientific_notation'], '1.03 × 10^162')
        self.assertTrue(proxy['extreme_magnitude'])
        self.assertIn('unvalidated', proxy['warnings'][0])
        self.assertIn('not', proxy['warnings'][0].lower())
        self.assertNotIn('selective', proxy)
        self.assertNotIn('passed', proxy)

    def test_exponential_overflow_stays_in_log_space_without_infinity_json(self):
        proxy = energy_fold_proxy(exchange_result(-100))
        self.assertEqual(proxy['status'], 'hypothetical_energy_proxy')
        self.assertIsNone(proxy['fold_magnitude'])
        self.assertGreater(proxy['log10_fold_magnitude'], 308)
        self.assertIsInstance(proxy['scientific_notation'], str)
        self.assertTrue(proxy['extreme_magnitude'])
        json.dumps(proxy, allow_nan=False)

    def test_extreme_finite_inputs_and_subnormal_temperature_are_bounded(self):
        for delta, temperature in ((-1e308, 1e-300), (-1, 5e-324)):
            proxy = energy_fold_proxy(exchange_result(delta), temperature)
            self.assertEqual(proxy['status'], 'unavailable')
            self.assertEqual(proxy['reason'], 'numeric_range_exceeded')
            self.assertIsNone(proxy['scientific_notation'])
            self.assertTrue(proxy['extreme_magnitude'])
            self.assertLess(len(json.dumps(proxy, allow_nan=False)), 2500)
        # A large delta and a large temperature cancel; intermediates must not
        # overflow and incorrectly suppress an otherwise representable log.
        proxy = energy_fold_proxy(exchange_result(-1e308), 1e308)
        self.assertEqual(proxy['status'], 'hypothetical_energy_proxy')
        self.assertGreater(proxy['log10_fold_magnitude'], 5000)
        json.dumps(proxy, allow_nan=False)

    def test_display_rounding_renormalizes_mantissa(self):
        delta = -BOLTZMANN_EV_K * DEFAULT_TEMPERATURE_K * math.log(999.99)
        self.assertEqual(energy_fold_proxy(exchange_result(delta))['scientific_notation'], '1 × 10^3')


if __name__ == '__main__':
    unittest.main()
