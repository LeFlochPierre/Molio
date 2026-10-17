"""Descriptive within-protocol variation; never calibrated model uncertainty."""
import statistics


def summarize(job):
    seeds = job.get('seeds', [job['settings']['seed']])
    groups = {}
    for case in job['cases']:
        key = case.get('candidate_id', case['id'])
        group = groups.setdefault(key, {'id': key, 'name': case['source']['name'], 'smiles': case['smiles'],
                                       'values': {}, 'expected': len(seeds), 'pose_review_count': 0, 'pose_unchecked_count': 0})
        if case['status'] == 'complete' and case.get('prediction'):
            checks = case['prediction'].get('pose_checks')
            if not checks or checks['status'] in ('unavailable', 'limited'): group['pose_unchecked_count'] += 1
            elif checks['status'] == 'review': group['pose_review_count'] += 1
            seed = case.get('seed', job['settings']['seed'])
            if seed in group['values']:
                raise ValueError('Duplicate seed within candidate')
            group['values'][seed] = case['prediction']['affinity']['affinity_pred_value']
    candidates, comparisons = [], []
    for group in groups.values():
        values = list(group['values'].values())
        candidates.append({k:v for k,v in group.items() if k != 'values'} | {
            'completed': len(values), 'mean': statistics.mean(values) if values else None,
            'min': min(values) if values else None, 'max': max(values) if values else None,
            'sample_sd': statistics.stdev(values) if len(values) > 1 else None})
    baseline = next(iter(groups.values()), None)
    for candidate in list(groups.values())[1:]:
        matched = sorted(set(baseline['values']) & set(candidate['values']))
        deltas = [candidate['values'][seed] - baseline['values'][seed] for seed in matched]
        complete = len(matched) == len(seeds)
        direction = 'incomplete' if not complete else 'single_run' if len(seeds) < 3 else (
            'consistently_lower' if all(d < 0 for d in deltas) else
            'consistently_higher' if all(d > 0 for d in deltas) else 'mixed_or_tied')
        comparisons.append({'baseline_id': baseline['id'], 'candidate_id': candidate['id'],
            'matched_seeds': matched, 'expected': len(seeds), 'paired_deltas': deltas,
            'mean_delta': statistics.mean(deltas) if deltas else None, 'direction': direction})
    return {'candidates': candidates, 'comparisons': comparisons,
            'interpretation': 'Variation across random seeds under one fixed protocol. Not experimental replicates, a confidence interval, or calibrated prediction uncertainty. Negative paired deltas favour the candidate over the first selected molecule.'}
