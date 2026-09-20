"""Energy direction and an explicitly hypothetical, uncalibrated energy-fold proxy.

The exponential transform is a visual scale for a matched UMA exchange-energy
difference. It does not turn that potential energy into a binding free energy,
affinity, equilibrium constant, or predicted selectivity.
"""
from decimal import Decimal, localcontext
import math


DEFAULT_TEMPERATURE_K = 298.15
# These SI constants are exact; the quotient is rounded only for float metadata.
BOLTZMANN_EV_K = 1.380649e-23 / 1.602176634e-19
_COMPONENTS = ('cluster_ligand', 'free_water', 'cluster_water', 'free_ligand')
_NIST_REFERENCE = 'https://physics.nist.gov/cuu/Constants/Table/allascii.txt'
_IUPAC_REFERENCE = 'https://goldbook.iupac.org/terms/view/S05915'


def _finite_number(value):
    # In particular, do not accept True, strings, NaN or integers too large for
    # JSON/IEEE numeric consumers. bool is a subclass of int.
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _valid_direction(result):
    delta = result.get('delta_B2_minus_B1_eV')
    return (result.get('descriptor') == 'ligand_water_exchange_eV' and
            result.get('status') == 'exploratory' and result.get('synthetic') is False and
            _finite_number(delta))


def _matched_pair_error(result):
    """Check the completed exchange result contract, not chemical applicability."""
    enzymes = result.get('enzymes')
    if not isinstance(enzymes, dict) or set(enzymes) != {'CYP11B1', 'CYP11B2'}:
        return 'missing_matched_pair'
    exchanges = {}
    for name in ('CYP11B1', 'CYP11B2'):
        row = enzymes[name]
        if not isinstance(row, dict):
            return 'missing_matched_pair'
        components = row.get('components')
        if not isinstance(components, dict) or set(components) != set(_COMPONENTS):
            return 'incomplete_exchange_components'
        energies = []
        for component_name in _COMPONENTS:
            component = components[component_name]
            if (not isinstance(component, dict) or component.get('status') != 'completed' or
                    not _finite_number(component.get('energy_eV'))):
                return 'invalid_exchange_component'
            energies.append(component['energy_eV'])
        exchange = row.get('exchange_energy_eV')
        if not _finite_number(exchange):
            return 'invalid_exchange_energy'
        try:
            expected = math.fsum((energies[0], energies[1], -energies[2], -energies[3]))
        except (OverflowError, ValueError):
            return 'invalid_exchange_energy'
        # The absolute tolerance accommodates cancellation of large molecular
        # totals while remaining much smaller than the displayed eV precision.
        if not math.isclose(exchange, expected, rel_tol=1e-10, abs_tol=1e-8):
            return 'inconsistent_exchange_energy'
        exchanges[name] = exchange
    expected_delta = exchanges['CYP11B2'] - exchanges['CYP11B1']
    if not _finite_number(expected_delta) or not math.isclose(
            result['delta_B2_minus_B1_eV'], expected_delta, rel_tol=1e-10, abs_tol=1e-8):
        return 'inconsistent_exchange_delta'
    if isinstance(result.get('backend'), dict) and result['backend'].get('synthetic') is True:
        return 'synthetic_backend'
    if result.get('reasons'):
        return 'unresolved_exchange_reasons'
    return None


def energy_fold_proxy(result, temperature_K=DEFAULT_TEMPERATURE_K):
    """Return a hypothetical Boltzmann energy transform, never fold selectivity.

    Both completed four-component exchange cycles must be present and internally
    consistent. Temperature is an explicit scale parameter, not an assertion
    that thermodynamic sampling has been performed. Calculations use log space;
    overflow of the exponential leaves a readable scientific representation.
    """
    if not _finite_number(temperature_K) or temperature_K <= 0:
        raise ValueError('temperature_K must be a finite positive number')
    proxy = {
        'status': 'unavailable',
        'label': 'Hypothetical energy-fold proxy',
        'temperature_K': temperature_K,
        'boltzmann_constant_eV_per_K': BOLTZMANN_EV_K,
        'preferred_in_energy_model': None,
        'log10_B2_over_B1': None,
        'log10_fold_magnitude': None,
        'fold_magnitude': None,
        'scientific_notation': None,
        'extreme_magnitude': False,
        'reason': None,
        'warnings': [],
        'formula': 'proxy magnitude = exp(abs(delta_B2_minus_B1_eV)/(k_B*T)); log10(B2/B1) = -delta_B2_minus_B1_eV/(k_B*T*ln(10))',
        'scope': 'Uncalibrated, hypothetical Boltzmann energy proxy only. Not binding selectivity, an affinity/Kd prediction, or an equilibrium population ratio. Potential energy has not been established as binding free energy; experimental cross-checks and thermodynamic validation are required.',
        'references': {'boltzmann_constant': _NIST_REFERENCE, 'free_energy_requirement': _IUPAC_REFERENCE},
    }
    if not _valid_direction(result):
        proxy['reason'] = 'invalid_or_nonreal_exchange_result'
        return proxy
    error = _matched_pair_error(result)
    if error:
        proxy['reason'] = error
        return proxy
    delta = result['delta_B2_minus_B1_eV']
    # Decimal prevents an underflowing kB*T or overflowing delta/T from raising
    # for finite input values. We do not materialize gigantic exponent strings.
    with localcontext() as context:
        context.prec = 50
        k_b = Decimal('1.380649e-23') / Decimal('1.602176634e-19')
        signed_log = -Decimal(str(delta)) / (k_b * Decimal(str(temperature_K)) * Decimal(10).ln())
        magnitude_log = abs(signed_log)
        if magnitude_log > Decimal('1e12'):
            proxy['reason'] = 'numeric_range_exceeded'
            proxy['extreme_magnitude'] = True
            proxy['warnings'] = ['Extreme, unvalidated magnitude exceeds the supported display range. No fold value is reported; this is not evidence of extreme biological selectivity.']
            return proxy
        log10_ratio = float(signed_log)
        log10_magnitude = float(magnitude_log)
    exponent = math.floor(log10_magnitude)
    mantissa = float(f'{10 ** (log10_magnitude - exponent):.3g}')
    if mantissa >= 10:  # Keep scientific notation normalized after rounding.
        mantissa /= 10
        exponent += 1
    scientific = '1' if delta == 0 else f'{mantissa:.3g} × 10^{exponent}'
    try:
        fold = 10 ** log10_magnitude
    except OverflowError:
        fold = None
    # This numerical display warning is not a selectivity acceptance threshold.
    extreme = log10_magnitude >= 6
    warnings = []
    if extreme:
        warnings.append('Extreme, unvalidated magnitude: exponentiation amplifies the exchange-energy difference. Do not interpret this number as biological selectivity or confidence.')
    proxy.update(
        status='hypothetical_energy_proxy',
        preferred_in_energy_model='CYP11B2' if delta < 0 else 'CYP11B1' if delta > 0 else None,
        log10_B2_over_B1=log10_ratio,
        log10_fold_magnitude=log10_magnitude,
        fold_magnitude=fold,
        scientific_notation=scientific,
        extreme_magnitude=extreme,
        warnings=warnings,
    )
    return proxy


def exchange_preference(result, temperature_K=DEFAULT_TEMPERATURE_K):
    delta = result.get('delta_B2_minus_B1_eV')
    valid = _valid_direction(result)
    preferred = ('CYP11B2' if delta < 0 else 'CYP11B1' if delta > 0 else None) if valid else None
    return {
        'status': 'energy_direction_only' if valid else 'unavailable',
        'preferred_in_energy_model': preferred,
        'delta_B2_minus_B1_eV': delta if valid else None,
        'energy_gap_eV': abs(delta) if valid else None,
        'fold_selectivity': None,
        'fold_status': 'not_identifiable_from_potential_energy',
        'headline': (f'UMA exchange favors {preferred}' if preferred else
                     'No exchange-energy difference' if valid else 'No interpretable energy preference'),
        'scope': 'Direction for this prepared exchange calculation only; not a binding or selectivity verdict. Robustness across poses/states has not been established.',
        'why_no_fold': 'An equilibrium fold ratio requires a binding free-energy difference and temperature. This UMA exchange potential energy omits the required thermodynamic sampling / contributions; exponentiating it or dividing total energies does not yield selectivity.',
        'thermodynamics_reference': 'https://goldbook.iupac.org/terms/view/S05915',
        'energy_fold_proxy': energy_fold_proxy(result, temperature_K),
    }
