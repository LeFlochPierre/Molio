"""Small scientific contracts shared by the fixture builder and API."""
import math


def normalize_observation(record):
    value = float(record['standard_value'])
    scales = {'nM': 1e-9, 'uM': 1e-6, 'µM': 1e-6, 'mM': 1e-3, 'M': 1}
    if not math.isfinite(value) or value <= 0:
        raise ValueError('Activity must be finite and positive')
    if record['standard_units'] not in scales:
        raise ValueError('Unsupported activity units')
    molar = value * scales[record['standard_units']]
    return dict(activity_id=record['activity_id'], assay_id=record['assay_chembl_id'],
        target_id=record['target_chembl_id'], document_id=record['document_chembl_id'],
        endpoint=record['standard_type'], relation=record['standard_relation'],
        value=value, units=record['standard_units'], value_M=molar,
        p_activity=-math.log10(molar) if record['standard_relation'] == '=' else None,
        validity_comment=record.get('data_validity_comment'),
        potential_duplicate=record.get('potential_duplicate'))


def compare_observations(left, right):
    if left['endpoint'] != 'IC50' or right['endpoint'] != 'IC50':
        raise ValueError('This comparison workflow supports IC50 only')
    for key in ('assay_id', 'target_id', 'endpoint', 'document_id'):
        if left[key] != right[key]:
            raise ValueError(f'Incomparable {key}')
    if left['relation'] != '=' or right['relation'] != '=':
        raise ValueError('Censored measurements cannot yield an exact ratio')
    if left.get('validity_comment') or right.get('validity_comment'):
        raise ValueError('Flagged measurements require review')
    for value in (left['value_M'], right['value_M']):
        if not math.isfinite(value) or value <= 0:
            raise ValueError('Invalid concentration')
    return dict(fold_lower_ic50_right=left['value_M'] / right['value_M'],
        delta_p_activity_right=math.log10(left['value_M'] / right['value_M']))
