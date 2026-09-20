"""Compare matched CYP isoform scores without mixing model-native units."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

from .core import digest, require
from .exchange import COMPONENTS, exchange_energy, validate_manifest
from .workflow import save


METHODS = {
    'UMA-exchange': {'metric': 'ligand_water_exchange_eV', 'unit': 'eV', 'lower_is_better': True},
    'Boltz-2': {'metric': 'log10_IC50_uM', 'unit': 'log10(IC50 / uM)', 'lower_is_better': True},
    'GNINA': {'metric': 'CNNaffinity_pK', 'unit': 'pK', 'lower_is_better': False},
    'Vina': {'metric': 'docking_score_kcal_mol', 'unit': 'kcal/mol', 'lower_is_better': True},
}
POSE_METHODS = ['Chai-1', 'AlphaFold 3', 'DiffDock-L']
INHIBITION_ENDPOINTS = {'IC50', 'Ki'}


def read(path):
    return json.loads(Path(path).read_text())


def source(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def experiment_cases(experiment):
    cases = experiment['systems']
    require(bool(cases), 'No experiment cases')
    require(len({c['system_id'] for c in cases}) == len(cases), 'Duplicate system IDs')
    require(len({(c['ligand'], c['isoform']) for c in cases}) == len(cases), 'Duplicate ligand/isoform cases')
    for case in cases:
        require(case['isoform'] in ('CYP11B1', 'CYP11B2'), 'Unknown isoform')
        require(bool(case['ligand']), 'Explicit ligand/stereochemistry required')
    return cases


def validate_observations(observations, cases):
    case_ids = {c['system_id'] for c in cases}
    seen = set()
    for row in observations:
        require(row['system_id'] in case_ids, 'Unknown case; preserve ligand stereochemistry in system_id')
        require(row['method'] in METHODS, 'Unsupported affinity/energy method; pose confidence is not affinity')
        require(row['metric'] == METHODS[row['method']]['metric'], 'Wrong metric for method')
        require(row.get('synthetic') is False, 'Synthetic or unlabeled observations cannot be benchmarked')
        require(row.get('status') == 'completed', 'Only completed observations may be scored')
        require(finite_number(row['value']), 'Score must be a finite number')
        for field in ('protocol_id', 'model_version'):
            require(isinstance(row.get(field), str) and bool(row[field].strip()), f'{field} required')
        require(type(row.get('replicate')) in (str, int) and str(row['replicate']) != '', 'Replicate/seed required')
        require(bool(row.get('source', {}).get('sha256')), 'Native output provenance required')
        key = tuple(str(row[k]) for k in ('system_id', 'method', 'protocol_id', 'model_version', 'replicate'))
        require(key not in seen, 'Duplicate observation for the same case/protocol/model/replicate')
        seen.add(key)


def load_observations(path):
    """Read explicit, model-native scores exported by external docking workflows."""
    rows = read(path)['observations']
    for row in rows:
        require(row.get('method') in ('GNINA', 'Vina'),
                'Use native --uma-result or --boltz-run imports for UMA-exchange and Boltz-2')
        native = Path(row.pop('source_path'))
        if not native.is_absolute():
            native = Path(path).parent / native
        row['source'] = source(native)
        row['import_manifest'] = source(path)
    return rows


def load_uma(path, cases):
    result = read(path)
    require(result.get('descriptor') == 'ligand_water_exchange_eV',
            'Expected complete exchange-cycle result, not raw total energy or legacy deformation')
    require(result.get('synthetic') is False and result.get('backend', {}).get('synthetic') is False,
            'Synthetic exchange results cannot be benchmarked')
    require(result.get('status') == 'exploratory' and not result.get('reasons'), 'Exchange cycle unresolved')
    require(result.get('geometry_mode') == 'relax', 'Benchmark requires the requested relaxed exchange cycle')
    manifest = validate_manifest(read(Path(path).parent / 'input.json'))
    require(digest(manifest) == result['input_sha256'], 'Exchange input hash mismatch')
    require(manifest['ligand'] == result['ligand'], 'Exchange ligand mismatch')
    require(manifest['geometry_mode'] == 'relax', 'Exchange input geometry mode mismatch')
    backend = result['backend']
    require(bool(backend.get('version')) and bool(backend.get('checkpoint_sha256')), 'Backend version/checkpoint required')
    require(set(result.get('enzymes', {})) == {'CYP11B1', 'CYP11B2'}, 'Both enzymes required')
    energies = {}
    for enzyme, row in result['enzymes'].items():
        components = row['components']
        require(set(components) == set(COMPONENTS), 'Four exchange components required')
        require(all(c['status'] == 'completed' and finite_number(c['energy_eV']) for c in components.values()),
                'Incomplete exchange component')
        value = exchange_energy({k: c['energy_eV'] for k, c in components.items()})
        require(finite_number(row['exchange_energy_eV']) and
                math.isclose(value, row['exchange_energy_eV'], rel_tol=0, abs_tol=1e-8), 'Exchange arithmetic mismatch')
        energies[enzyme] = value
    require(finite_number(result.get('delta_B2_minus_B1_eV')) and
            math.isclose(energies['CYP11B2'] - energies['CYP11B1'], result['delta_B2_minus_B1_eV'],
                         rel_tol=0, abs_tol=1e-8), 'Exchange delta mismatch')
    cluster_contracts = {}
    for enzyme, parts in manifest['enzymes'].items():
        cluster_contracts[enzyme] = {}
        for name in ('cluster_ligand', 'cluster_water'):
            part = parts[name]
            cluster_contracts[enzyme][name] = {
                'atoms': sorted((a['id'], a['element']) for a in part['atoms']),
                'state': part['state'], 'scaffold_ids': sorted(part['scaffold_ids']),
                'fixed_atoms': sorted((a['id'], a['position']) for a in part['atoms'] if a['id'] in part['fixed_ids']),
                'coordination': part['coordination'], 'preparation': part['preparation'],
                'covalent_bounds': part.get('covalent_bounds', []), 'chirality_checks': part.get('chirality_checks', [])}
    protocol = digest({'preparation_protocol': manifest['preparation_protocol'], 'optimizer': manifest['optimizer'],
                       'geometry_mode': manifest['geometry_mode'], 'backend': backend,
                       'cluster_contracts': cluster_contracts,
                       'references': {k: manifest['enzymes']['CYP11B1'][k] for k in ('free_ligand', 'free_water')}})
    rows = []
    for enzyme, value in energies.items():
        matches = [c for c in cases if c['ligand'] == result['ligand'] and c['isoform'] == enzyme]
        require(len(matches) == 1, 'Exchange result has no unique experiment case')
        rows.append({'system_id': matches[0]['system_id'], 'method': 'UMA-exchange',
                     'metric': 'ligand_water_exchange_eV', 'value': value,
                     'replicate': result['input_sha256'], 'protocol_id': protocol,
                     'model_version': f"{backend['name']}:{backend['version']}:{backend['checkpoint_sha256']}",
                     'status': 'completed', 'synthetic': False, 'source': source(path),
                     'provisional': any(p['review'].get('approved') is not True
                                        for parts in manifest['enzymes'].values() for p in parts.values()),
                     'input_sha256': result['input_sha256']})
    return rows


def load_boltz(path, cases, ccd_dir=None):
    from .benchmark_geometry import analyze_boltz_structure
    path = Path(path)
    if path.is_dir():
        path = path / 'run_manifest.json'
    run = read(path)
    require(run.get('schema_version') == 1 and run.get('model') == 'boltz2', 'Expected native Boltz-2 run manifest')
    case_lookup = {c['system_id']: c for c in cases}
    inputs = {c['system_id']: c for c in run['cases']}
    require(len(inputs) == len(run['cases']), 'Duplicate Boltz input cases')
    source_manifest = run['source_manifest']
    require(source(source_manifest['path'])['sha256'] == source_manifest['sha256'], 'Boltz source manifest changed')
    for case in inputs.values():
        expected = case_lookup.get(case['system_id'])
        require(expected and all(expected[k] == case[k] for k in ('ligand', 'isoform')), 'Boltz case identity mismatch')
        require(source(case['input_path'])['sha256'] == case['input_sha256'], 'Boltz input changed after execution')
    rows = []
    for replicate in run['runs']:
        require(replicate['seed'] in run['seeds'], 'Undeclared Boltz seed')
        # A failed invocation is kept in the execution inventory, never scored.
        if replicate['status'] != 'completed' or replicate['returncode'] != 0:
            continue
        for prediction in replicate['predictions']:
            require(prediction['system_id'] in inputs, 'Unknown Boltz prediction case')
            affinity_path = prediction.get('affinity_path')
            if not affinity_path:
                continue
            require(bool(run.get('model_version')) and bool(run.get('checkpoints')),
                    'Boltz package version and checkpoint provenance required')
            require(all(c.get('sha256') for c in run['checkpoints']), 'Missing Boltz checkpoint hash')
            output = read(affinity_path)
            require(source(affinity_path)['sha256'] == prediction.get('affinity_sha256'),
                    'Boltz affinity output changed after execution')
            require(finite_number(output.get('affinity_pred_value')), 'Missing finite native Boltz affinity_pred_value')
            probability = output.get('affinity_probability_binary')
            require(finite_number(probability) and 0 <= probability <= 1, 'Invalid Boltz binder probability')
            quality = []
            for confidence_path in prediction.get('confidence_paths', []):
                confidence = read(confidence_path)
                quality.append({'source': source(confidence_path), 'scores': {
                    k: confidence[k] for k in ('confidence_score', 'ligand_iptm', 'complex_plddt') if k in confidence}})
            geometry = []
            for structure_path in prediction.get('structure_paths', []):
                try:
                    check = analyze_boltz_structure(structure_path, inputs[prediction['system_id']]['ligand'], ccd_dir=ccd_dir)
                except (ValueError, RuntimeError) as error:
                    check = {'status': 'unresolved', 'reason': str(error)}
                geometry.append({'source': source(structure_path), 'diagnostics': check,
                                 'rank_zero': str(structure_path).endswith('_model_0.cif')})
            invalid_pose = any(g['rank_zero'] and (
                g['diagnostics'].get('status') == 'unresolved' or
                g['diagnostics'].get('ligand_ccd_matches_expected') is False or
                g['diagnostics'].get('chirality', {}).get('status') == 'mismatch_or_unassigned' or
                g['diagnostics'].get('chirality', {}).get('coordinates_match_expected') is False) for g in geometry)
            rows.append({'system_id': prediction['system_id'], 'method': 'Boltz-2', 'metric': 'log10_IC50_uM',
                         'value': output['affinity_pred_value'], 'replicate': str(replicate['seed']),
                         'protocol_id': run['protocol_id'],
                         'model_version': run['model_version'] + ':' + digest(sorted(c['sha256'] for c in run['checkpoints'])),
                         'status': 'completed', 'synthetic': False, 'provisional': True,
                         'source': source(affinity_path), 'run_manifest': source(path),
                         'input_sha256': inputs[prediction['system_id']]['input_sha256'],
                         'binder_probability': probability, 'structural_confidence': quality,
                         'geometry_checks': geometry, 'pose_invalid': invalid_pose,
                         'pose_validation': 'invalid_or_unresolved' if invalid_pose else 'unreviewed; inspect geometry diagnostics',
                         'structure_sources': [source(p) for p in prediction.get('structure_paths', [])]})
    return rows


def assay_pairs(path, cases):
    data = read(path)
    require(data.get('schema_version') == 1, 'Unsupported assay schema')
    known = {(c['ligand'], c['isoform']) for c in cases}
    groups = defaultdict(dict)
    for row in data['measurements']:
        require((row['ligand'], row['isoform']) in known, 'Unknown assay ligand/isoform')
        require(row['endpoint'] in INHIBITION_ENDPOINTS and row['species'] == 'Homo sapiens',
                'Expected a supported paired human inhibition reference')
        require(finite_number(row['value_nM']) and row['value_nM'] > 0,
                'Inhibition value must be positive and expressed in nM')
        require(bool(row.get('source_url')) and bool(row.get('assay_id')), 'Assay provenance required')
        group = groups[(row['ligand'], row['assay_id'], row['endpoint'])]
        require(row['isoform'] not in group, 'Duplicate assay entry')
        group[row['isoform']] = row
    pairs = []
    for (ligand, assay_id, endpoint), group in groups.items():
        require(set(group) == {'CYP11B1', 'CYP11B2'}, 'Both isoforms required for assay comparison')
        b1, b2 = (group[iso]['value_nM'] for iso in ('CYP11B1', 'CYP11B2'))
        log_ratio = math.log10(b1) - math.log10(b2)
        pair = {'ligand': ligand, 'assay_id': assay_id, 'endpoint': endpoint,
                'values_nM': {'CYP11B1': b1, 'CYP11B2': b2}, 'ratio_B1_over_B2': b1 / b2,
                'log10_ratio_B1_over_B2': log_ratio,
                'preference': 'CYP11B2' if log_ratio > 0 else 'CYP11B1' if log_ratio < 0 else None,
                'measurements': group, 'source': source(path)}
        # Retain these fields for compatibility with existing IC50 reports.
        if endpoint == 'IC50':
            pair.update(IC50_nM=pair['values_nM'], IC50_ratio_B1_over_B2=pair['ratio_B1_over_B2'],
                        log10_IC50_ratio_B1_over_B2=pair['log10_ratio_B1_over_B2'])
        pairs.append(pair)
    return pairs


def compare_assays(comparisons, pairs):
    results = []
    for pair in pairs:
        for row in comparisons:
            if row['ligand'] != pair['ligand']:
                continue
            result = {'ligand': pair['ligand'], 'method': row['method'], 'assay_id': pair['assay_id'],
                      'protocol_id': row.get('protocol_id'), 'model_version': row.get('model_version'),
                      'experimental_preference': pair['preference'], 'score_preference': row['preference'],
                      'direction_agrees': row['preference'] == pair['preference'] if row['preference'] else None,
                      'predicted_minus_observed_log10_ratio': None}
            if pair['endpoint'] == 'IC50' and 'predicted_log10_IC50_ratio_B1_over_B2' in row:
                result['predicted_minus_observed_log10_ratio'] = (
                    row['predicted_log10_IC50_ratio_B1_over_B2'] - pair['log10_IC50_ratio_B1_over_B2'])
            results.append(result)
    return results


def compare_scores(cases, observations):
    validate_observations(observations, cases)
    lookup = {c['system_id']: c for c in cases}
    groups = defaultdict(list)
    for obs in observations:
        groups[(lookup[obs['system_id']]['ligand'], obs['method'], obs['protocol_id'], obs['model_version'])].append(obs)
    comparisons = []
    for ligand in sorted({c['ligand'] for c in cases}):
        for method, spec in METHODS.items():
            variants = [(key, group) for key, group in groups.items() if key[:2] == (ligand, method)]
            if not variants:
                comparisons.append({'ligand': ligand, 'method': method, 'metric': spec['metric'], 'unit': spec['unit'],
                                    'status': 'not_run', 'preference': None, 'reason': 'No model outputs imported'})
                continue
            for key, group in variants:
                by_isoform = {iso: {str(o['replicate']): o for o in group if lookup[o['system_id']]['isoform'] == iso}
                              for iso in ('CYP11B1', 'CYP11B2')}
                b1, b2 = by_isoform['CYP11B1'], by_isoform['CYP11B2']
                row = {'ligand': ligand, 'method': method, 'metric': spec['metric'], 'unit': spec['unit'],
                       'protocol_id': key[2], 'model_version': key[3], 'status': 'unresolved', 'preference': None,
                       'available_replicates': {iso: sorted(values) for iso, values in by_isoform.items()},
                       'provisional': any(o.get('provisional', False) for o in group)}
                if any(o.get('pose_invalid') for o in group):
                    row['reason'] = 'Predicted score pose has wrong ligand identity/chirality or unresolved required geometry'
                elif not b1 or not b2 or set(b1) != set(b2):
                    row['reason'] = 'Both isoforms require the same complete set of replicates/seeds'
                else:
                    seeds = sorted(b1)
                    deltas = [b2[s]['value'] - b1[s]['value'] for s in seeds]
                    require(all(finite_number(d) for d in deltas), 'Score difference overflow')
                    mean = statistics.mean(deltas)
                    oriented = [-d if spec['lower_is_better'] else d for d in deltas]
                    row.update(status='single_replicate_pilot' if len(seeds) == 1 else 'exploratory',
                               n_pairs=len(seeds), paired_replicates=seeds,
                               mean_scores={iso: statistics.mean(v['value'] for v in values.values())
                                            for iso, values in by_isoform.items()},
                               deltas_B2_minus_B1=deltas, mean_delta_B2_minus_B1=mean,
                               delta_range=[min(deltas), max(deltas)],
                               delta_sample_sd=statistics.stdev(deltas) if len(deltas) > 1 else None,
                               preference='CYP11B2' if min(oriented) > 0 else 'CYP11B1' if max(oriented) < 0 else None,
                               reason='Model score direction only; replicate spread is not calibrated uncertainty')
                    if row['preference'] is None:
                        row['reason'] = 'Tie or replicate directions disagree'
                    if method == 'Boltz-2':
                        row['predicted_log10_IC50_ratio_B1_over_B2'] = -mean
                        row['predicted_IC50_ratio_B1_over_B2'] = 10 ** (-mean) if -300 <= -mean <= 300 else None
                comparisons.append(row)
    return comparisons


def inventory(paths):
    """List existing results for context without promoting them into model scores."""
    records = []
    for path in sorted({str(p.resolve()) for root in paths for name in ('result.json', 'candidate_result.json')
                        for p in Path(root).rglob(name)}):
        try:
            result = read(path)
        except (OSError, json.JSONDecodeError):
            records.append({'path': path, 'status': 'unreadable',
                            'classification': 'Unavailable or being written; no score imported'})
            continue
        if result.get('synthetic') or result.get('status') == 'synthetic_demo':
            reason = 'Synthetic software test'
        elif result.get('descriptor') == 'ligand_water_exchange_eV':
            reason = 'Exchange candidate; import explicitly with --uma-result after validation'
        elif 'descriptor_eV' in result:
            reason = 'Legacy deformation calculation, outside the current exchange benchmark'
        else:
            reason = 'Component or diagnostic result; not paired selectivity'
        records.append({**source(path), 'status': result.get('status', 'unknown'), 'classification': reason})
    return records


def markdown_report(report):
    def cell(value):
        return str(value).replace('|', '\\|').replace('\n', ' ')
    lines = ['# CYP11B1 / CYP11B2 model benchmark', '',
             'Status: exploratory pilot. Model predictions and experimental measurements are identified separately.', '',
             '| Ligand | Method | B1 score | B2 score | B2 - B1 | Unit | Pairs | Preference | Status |',
             '|---|---|---:|---:|---:|---|---:|---|---|']
    for row in report['comparisons']:
        def number(value):
            return f'{value:.6g}' if value is not None else '-'
        means = row.get('mean_scores', {})
        values = [row['ligand'], row['method'], number(means.get('CYP11B1')), number(means.get('CYP11B2')),
                  number(row.get('mean_delta_B2_minus_B1')), row['unit'], row.get('n_pairs', 0),
                  row.get('preference') or '-', row['status'] + ('; provisional' if row.get('provisional') else '')]
        lines.append('| ' + ' | '.join(cell(v) for v in values) + ' |')
    lines += ['', 'Lower scores favor binding for Boltz-2 and Vina, and lower potential energy for UMA exchange. '
              'Higher CNNaffinity favors binding for GNINA. Values from different methods are not averaged.', '',
              'A single replicate is a pilot. Multiple seeds measure sampling variability, not model accuracy. '
              'Agreement among models is not experimental validation. Heme/metal selectivity remains unvalidated.', '',
              'Chai-1, AlphaFold 3 and DiffDock-L are pose comparisons. Structural confidence is not affinity. '
              'RFdiffusion is a protein-design model and has no comparable selectivity endpoint here.', '',
              'See docs/BENCHMARKING.md for the protocol, sources and additional model limitations.', '',
              '## Comparison Details', '']
    for row in report['comparisons']:
        lines.append(f"- {cell(row['ligand'])}, {cell(row['method'])}: {cell(row['reason'])}"
                     + (f"; delta range {row['delta_range']}, SD {row['delta_sample_sd']}" if 'delta_range' in row else '')
                     + (f"; protocol {row['protocol_id']}; model {cell(row['model_version'])}" if 'protocol_id' in row else ''))
    if report['experimental_validation']['pairs']:
        lines += ['', '## Experimental References', '',
                  '| Ligand | Endpoint | B1 (nM) | B2 (nM) | B1 / B2 | Preference |',
                  '|---|---|---:|---:|---:|---|']
        for pair in report['experimental_validation']['pairs']:
            lines.append(f"| {cell(pair['ligand'])} | {pair['endpoint']} | {pair['values_nM']['CYP11B1']:g} | "
                         f"{pair['values_nM']['CYP11B2']:g} | {pair['ratio_B1_over_B2']:.4g} | {pair['preference']} |")
        lines += ['', 'These are source-specific inhibition measurements, not binding free energies. '
                  'Only a matched IC50 reference is eligible for a numerical Boltz IC50-ratio error; '
                  'all other endpoints are direction-only comparisons. Small panels do not establish general model accuracy.', '']
        for assay_id, url in sorted({(p['assay_id'], p['measurements']['CYP11B1']['source_url'])
                                     for p in report['experimental_validation']['pairs']}):
            lines.append(f"- [{cell(assay_id)}]({url})")
        for result in report['experimental_validation']['comparisons']:
            if result['direction_agrees'] is not None:
                lines.append(f"- {cell(result['ligand'])}, {cell(result['method'])}: direction "
                             + ('agrees' if result['direction_agrees'] else 'disagrees') + ' with this assay.'
                             + (f" Log10-ratio error: {result['predicted_minus_observed_log10_ratio']:.4g}."
                                if result['predicted_minus_observed_log10_ratio'] is not None else ''))
    else:
        lines += ['', 'No experimental assay references imported.', '']
    if report['external_runs']:
        lines += ['', '## Model Executions', '']
        for run in report['external_runs']:
            lines.append(f"- {cell(run['path'])}: {cell(run['status'])}")
        lines += ['', 'Failed or incomplete executions do not contribute selectivity scores.', '']
    geometry_rows = [(o, g) for o in report['observations'] for g in o.get('geometry_checks', []) if g['rank_zero']]
    if geometry_rows:
        lines += ['', '## Pose Diagnostics', '',
                  '| Case | Seed | Nearest ligand N to Fe (A) | Nearest cysteine S to Fe (A) | Chirality |',
                  '|---|---|---:|---:|---|']
        for observation, check in geometry_rows:
            diagnostics = check['diagnostics']
            distances = [(diagnostics.get(k) or {}).get('distance_A') for k in
                         ('nearest_ligand_nitrogen', 'nearest_protein_cysteine_sulfur')]
            values = [observation['system_id'], observation['replicate'],
                      *(f'{d:.3f}' if d is not None else '-' for d in distances),
                      diagnostics.get('chirality', {}).get('status', diagnostics['status'])]
            lines.append('| ' + ' | '.join(cell(v) for v in values) + ' |')
        lines += ['', 'Nearest-atom distances are descriptive, not proof of metal coordination. '
                  'Chirality or identity failures exclude the pair from selectivity scoring.', '']
    if report['inventory']:
        lines += ['', '## Existing Artifacts', '',
                  'These files were inventoried only. They are not automatically treated as benchmark scores.', '']
        for row in report['inventory']:
            lines.append(f"- {cell(row['path'])}: {cell(row['classification'])} ({cell(row['status'])})")
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    command = sub.add_parser('report')
    command.add_argument('--experiment', default='configs/experiment.json')
    command.add_argument('--observations', action='append', default=[])
    command.add_argument('--uma-result', action='append', default=[])
    command.add_argument('--boltz-run', action='append', default=[])
    command.add_argument('--assays', action='append', default=[],
                         help='Curated paired human IC50/Ki measurement JSON; repeat for multiple sources')
    command.add_argument('--geometry-ccd-cache', help='Trusted Boltz molecule cache for optional RDKit chirality checks')
    command.add_argument('--inventory-root', action='append', default=[])
    command.add_argument('--out', required=True)
    args = parser.parse_args(argv)
    try:
        cases = experiment_cases(read(args.experiment))
        observations = []
        for path in args.observations:
            observations.extend(load_observations(path))
        for path in args.uma_result:
            observations.extend(load_uma(path, cases))
        for path in args.boltz_run:
            observations.extend(load_boltz(path, cases, args.geometry_ccd_cache))
        comparisons = compare_scores(cases, observations)
        pairs = [pair for path in args.assays for pair in assay_pairs(path, cases)]
        report = {'schema_version': 1, 'created_at_utc': datetime.now(timezone.utc).isoformat(),
                  'experiment_source': source(args.experiment), 'cases': cases, 'methods': METHODS,
                  'observations': observations, 'comparisons': comparisons,
                  'pose_only_methods': POSE_METHODS, 'excluded_methods': {'RFdiffusion': 'Protein design, not affinity prediction'},
                  'experimental_validation': {'status': 'references_available' if pairs else 'unavailable',
                                              'pairs': pairs, 'comparisons': compare_assays(comparisons, pairs)},
                  'external_runs': [{**source(Path(p) / 'run_manifest.json' if Path(p).is_dir() else p),
                                     'status': read(Path(p) / 'run_manifest.json' if Path(p).is_dir() else p)['status']}
                                    for p in args.boltz_run],
                  'inventory': inventory(args.inventory_root)}
        output = Path(args.out)
        output.mkdir(parents=True, exist_ok=False)
        save(output / 'benchmark.json', report)
        (output / 'report.md').write_text(markdown_report(report))
        print(output / 'report.md')
        return 0
    except (ValueError, KeyError, TypeError, OSError, ImportError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
