"""Auditable reanalysis of the team's two-compound retrospective UMA fit.

No model is executed here, and the calibration is deliberately NOT attached to
arbitrary live UMA energies. Inputs are the scoped, supplied relaxed exchanges.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
import math
from pathlib import Path

HANDOFF = Path(__file__).with_name('data') / 'selectivity_handoff.json'
COMPONENTS = {'cluster_ligand', 'cluster_water', 'free_water', 'free_ligand'}


def handoff_catalog():
    source = json.loads(HANDOFF.read_text())
    return {key: {'id': key, 'label': row['label']} for key, row in source['compounds'].items()}


def exchange_energy(components):
    """Subtract full-precision decimal terms before converting to JSON floats."""
    if not isinstance(components, dict) or set(components) != COMPONENTS:
        raise ValueError('Exactly four matched exchange components are required')
    try:
        with localcontext() as context:
            context.prec = 40
            terms = {key: Decimal(str(value)) for key, value in components.items()}
            if any(not value.is_finite() or abs(value) > Decimal('1e12') for value in terms.values()):
                raise ValueError('Exchange energies must be finite and within the supported range')
            return terms['cluster_ligand'] + terms['free_water'] - terms['cluster_water'] - terms['free_ligand']
    except InvalidOperation as error:
        raise ValueError('Exchange energies must be numeric') from error


def empirical_ratio(advantage_eV, coefficient):
    """Signed ratio; no absolute value that could silently reverse preference."""
    with localcontext() as context:
        context.prec = 40
        value, slope = Decimal(str(advantage_eV)), Decimal(str(coefficient))
        if not value.is_finite() or not slope.is_finite() or slope <= 0:
            raise ValueError('Finite energy advantage and positive coefficient required')
        exponent = float(value * slope)
    if abs(exponent) > 300:
        raise ValueError('Empirical ratio outside supported numeric range')
    ratio = 10 ** exponent
    return {'S_B1_over_B2': ratio, 'log10_S': exponent,
            'preferred': 'CYP11B2' if exponent > 0 else 'CYP11B1' if exponent < 0 else None,
            'fold_preference': max(ratio, 1 / ratio)}


def boltz_rows(source, candidate_id):
    rows = []
    for row in source['boltz']['rows']:
        if row['compound'] != candidate_id:
            continue
        raw_ratio = 10 ** (row['y_B1'] - row['y_B2'])
        rows.append({**row, 'raw_ratio_from_rounded_y': raw_ratio,
                     'usable_ratio': raw_ratio if row['geometry_valid'] else None,
                     'geometry_scope': 'Supplied audit only; not independently rechecked'})
    return rows


def analyze_calibrated(payload):
    if not isinstance(payload, dict) or set(payload) != {'candidate_id', 'pose_policy'}:
        raise ValueError('Expected candidate_id and pose_policy only')
    candidate_id, policy = payload['candidate_id'], payload['pose_policy']
    source_bytes = HANDOFF.read_bytes()
    source = json.loads(source_bytes)
    if not isinstance(candidate_id, str) or candidate_id not in source['compounds']:
        raise ValueError('This empirical calibration only covers the supplied pilot candidates')
    if policy not in ('selected_fit', 'original_minima'):
        raise ValueError('pose_policy must be selected_fit or original_minima')
    compound = source['compounds'][candidate_id]
    result = {
        'schema_version': 1, 'kind': 'retrospective_calibrated_selectivity',
        'candidate_id': candidate_id, 'label': compound['label'], 'pose_policy': policy,
        'source': {**source['source'], 'artifact_sha256': hashlib.sha256(source_bytes).hexdigest()},
        'calibration': source['calibration'], 'limitations': source['limitations'],
        'execution': {'operation': 'recompute_supplied_UMA_outputs', 'new_UMA_inference': False,
                      'new_pose_generation': False, 'component_arithmetic_independently_checked': True,
                      'geometry_independently_checked': False},
        'quality': compound['quality'], 'fit_assay': compound['fit_assay'],
        'other_assays': compound['other_assays'], 'boltz': boltz_rows(source, candidate_id),
        'boltz_source': {key: source['boltz'][key] for key in ('source', 'convention')}, 'fold_selectivity': None,
        'validated_selectivity': False, 'overall_status': 'unresolved',
        'empirical_fit': None, 'selected_exchange': None,
        'original_minima': None, 'weighted': None,
        'screen': {'threshold': 10, 'status': 'unresolved', 'scope': 'Illustrative fitted-ratio screen, not a validated acceptance gate'},
        'pipeline_steps': [{'label': 'Load UMA outputs', 'state': 'done', 'detail': 'Supplied team handoff'}],
    }
    if compound['selected'] is None:
        result['execution']['component_arithmetic_independently_checked'] = False
        result['pipeline_steps'] += [
            {'label': 'Build exchange', 'state': 'warning', 'detail': 'B2 convergence failed'},
            {'label': 'Convert to fold', 'state': 'warning', 'detail': 'No ratio inferred'},
            {'label': 'Cross-check', 'state': 'warning', 'detail': 'Reprepare and rerun B2'}]
        return result
    energies = {}
    for enzyme, row in compound['selected'].items():
        energy = exchange_energy(row['components_eV'])
        if not math.isclose(float(energy), row['reported_exchange_eV'], abs_tol=2e-9, rel_tol=0):
            raise ValueError(f'{enzyme} component arithmetic disagrees with the supplied exchange score')
        energies[enzyme] = energy
    advantage = energies['CYP11B1'] - energies['CYP11B2']
    coefficient = source['calibration']['coefficient_per_eV']
    selected = {enzyme: {**row, 'exchange_eV': float(energies[enzyme])}
                for enzyme, row in compound['selected'].items()}
    result['selected_exchange'] = {'enzymes': selected, 'B1_minus_B2_eV': float(advantage),
                                   'B2_minus_B1_eV': -float(advantage),
                                   **empirical_ratio(advantage, coefficient)}
    for name, source_key in (('original_minima', 'original_minima_delta_B2_minus_B1_eV'),
                             ('weighted', 'weighted_delta_B2_minus_B1_eV')):
        delta = compound[source_key]
        result[name] = {'B2_minus_B1_eV': delta, 'B1_minus_B2_eV': -delta,
                        'source': 'Reported summary delta; underlying individual pose energies not supplied',
                        **empirical_ratio(-delta, coefficient)}
    chosen = result['selected_exchange' if policy == 'selected_fit' else 'original_minima']
    result['empirical_fit'] = {key: chosen[key] for key in
                              ('S_B1_over_B2', 'log10_S', 'preferred', 'fold_preference', 'B1_minus_B2_eV', 'B2_minus_B1_eV')}
    result['empirical_fit']['status'] = 'training_fit' if policy == 'selected_fit' else 'same_coefficient_pose_sensitivity'
    result['empirical_fit']['relative_residual_percent'] = 100 * abs(chosen['S_B1_over_B2'] / compound['fit_assay']['ratio'] - 1)
    result['screen']['status'] = 'above_threshold' if chosen['S_B1_over_B2'] >= 10 else 'below_threshold'
    result['pipeline_steps'] += [
        {'label': 'Build exchange', 'state': 'done', 'detail': 'Eight energy terms checked'},
        {'label': 'Convert to fold', 'state': 'done', 'detail': 'Shared empirical coefficient'},
        {'label': 'Cross-check', 'state': 'warning', 'detail': 'Pose robustness unresolved'}]
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate_id', choices=tuple(handoff_catalog()))
    parser.add_argument('--pose-policy', choices=('selected_fit', 'original_minima'), default='selected_fit')
    args = parser.parse_args(argv)
    print(json.dumps(analyze_calibrated(vars(args)), indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
