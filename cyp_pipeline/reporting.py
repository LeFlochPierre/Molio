"""Readable, self-contained reports with technical records available on demand."""
import html
import json
from pathlib import Path


def esc(value):
    return html.escape(str(value))


STYLE = '''
:root{color-scheme:light;--ink:#183343;--muted:#536776;--line:#dce5e9;--teal:#116c66}
*{box-sizing:border-box}body{margin:0;background:#f3f6f7;color:var(--ink);font:17px/1.65 system-ui,sans-serif}
main{max-width:1100px;margin:auto;padding:48px 24px 72px}h1{font-size:clamp(30px,5vw,46px);line-height:1.15;letter-spacing:-1.4px;margin:12px 0 20px}h2{font-size:25px;line-height:1.3;margin:0 0 16px}h3{font-size:18px;margin:0 0 8px}p{margin:8px 0 16px}.eyebrow{font-size:12px;letter-spacing:2px;text-transform:uppercase;font-weight:750;color:var(--teal)}.lead{max-width:780px;font-size:20px}.muted,small{color:var(--muted)}a{color:#09675f;text-underline-offset:3px}nav{display:flex;gap:20px;flex-wrap:wrap;margin:24px 0 32px}section{background:white;border:1px solid var(--line);border-radius:16px;padding:28px;margin:20px 0;scroll-margin-top:20px}.notice{border-left:5px solid #c48419;background:#fff6e3;padding:18px 22px;border-radius:6px;margin:24px 0}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px}.card{background:#f5f8f9;border-radius:10px;padding:18px}.metric{font-size:32px;font-weight:750;display:block;line-height:1.3}.badge{display:inline-block;font-size:12px;font-weight:750;border-radius:20px;padding:3px 10px;background:#e3efed;color:#145e58}.pending{background:#fff0d4;color:#775116}.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:15px}th{text-align:left;font-size:12px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted)}td,th{padding:14px 12px;border-bottom:1px solid var(--line);vertical-align:top}td:first-child,th:first-child{padding-left:0}.formula{background:#eaf3f2;border-radius:10px;padding:18px;font-weight:650}.steps{padding-left:24px}.steps li{padding-left:8px;margin:18px 0}.steps strong{display:block}.callout{background:#183f4b;color:white;border-radius:12px;padding:22px}.callout p{margin-bottom:0}details{border-top:1px solid var(--line);padding:14px 0}summary{cursor:pointer;font-weight:650}summary:focus-visible,a:focus-visible{outline:3px solid #c48419;outline-offset:4px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f7f8;padding:18px;font-size:12px;line-height:1.6;border-radius:8px}footer{font-size:14px;color:var(--muted);margin-top:24px}@media(max-width:600px){main{padding:24px 14px}section{padding:20px}td,th{padding:10px 8px}}@media print{body{background:white}main{padding:0}section{break-inside:avoid}nav{display:none}}
'''


def report(results, comparisons, path):
    synthetic = sum(bool(r.get('synthetic')) for r in results)
    real = len(results) - synthetic
    scores = sum(r.get('descriptor_eV') is not None and not r.get('synthetic') for r in results)
    all_demo = bool(results) and synthetic == len(results)
    headline = 'The software demo works. The science result is still ahead.' if all_demo else 'What these calculations tell us'
    introduction = ('We tested the calculation workflow using tiny, artificial examples. '
                    'We have not yet calculated how real fadrozole molecules behave inside either CYP enzyme.'
                    if all_demo else 'Review the calculation status and geometry checks before interpreting any energy. '
                    'These exploratory scores do not establish drug selectivity.')
    banner = ('This report contains synthetic test data only. The four labels describe the planned experiment; '
              'the atoms and energies do not represent those molecules.' if all_demo else
              'Synthetic entries, if present, are software tests only. Real entries are exploratory calculations, '
              'not measured affinities or validated selectivity predictions.')
    cards = f'''<div class="cards"><div class="card"><span class="metric">{synthetic}</span>Synthetic test runs</div>
<div class="card"><span class="metric">{real}</span>Real molecular runs in this report</div>
<div class="card"><span class="metric">{scores}</span>Real deformation scores available</div></div>'''
    rows = []
    for r in results:
        demo = r.get('synthetic', False)
        label = 'Synthetic example' if demo else {'experimental': 'Experimental starting pose', 'modeled': 'Modeled starting pose'}.get(r['pose']['kind'], r['pose']['kind'])
        status = {'synthetic_demo': 'Software test completed', 'exploratory': 'Exploratory score available',
                  'failed': 'Calculation failed', 'unresolved': 'Needs investigation'}.get(r['status'], r['status'])
        score = 'No usable score' if r.get('descriptor_eV') is None else f"{r['descriptor_eV']:.4f} eV"
        issue = '; '.join(r.get('reasons', []))
        rows.append(f'<tr><td><strong>{esc(r["ligand"])}</strong><br>{esc(r["isoform"])}</td>'
                    f'<td>{esc(label)}</td><td>{esc(status)}'
                    + (f'<br><small>{esc(issue)}</small>' if issue else '')
                    + f'</td><td>{esc(score)}<br><small>{"Test value only" if demo else "Not binding affinity"}</small></td></tr>')
    demo_explanation = '''<p><strong>Why are the four numbers the same?</strong> The demo repeats the same four-atom,
 spring-like test under four different labels. It is designed to check the software, so equal values do not
 mean the two drugs or enzymes behave alike.</p>''' if all_demo else ''
    comparison_cards = []
    for c in comparisons:
        group = [r for r in results if r['ligand'] == c['ligand']]
        if any(r.get('synthetic') for r in group):
            answer = 'No enzyme preference calculated'
            explanation = 'Only synthetic test data is available for this comparison.'
        elif c.get('descriptor_preference'):
            answer = 'Exploratory score favors ' + c['descriptor_preference']
            explanation = 'This is a deformation-energy hypothesis. Experimental assay comparison and sensitivity checks are still needed.'
        else:
            answer = 'No interpretable preference yet'
            explanation = c.get('reason', 'A complete, comparable pair of calculations is required.')
        comparison_cards.append(f'<div class="card"><h3>{esc(c["ligand"])}</h3><strong>{esc(answer)}</strong><p>{esc(explanation)}</p></div>')
    details = ''.join(f'<details><summary>{esc(r["ligand"])} · {esc(r["isoform"])} — technical record</summary>'
                      f'<pre>{esc(json.dumps(r, indent=2))}</pre></details>' for r in results)
    document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>CYP study — results explained</title><style>{STYLE}</style></head><body><main>
<header><div class="eyebrow">CYP11B1 / CYP11B2 · Feasibility study</div><h1>{headline}</h1>
<p class="lead">{introduction}</p></header>
<nav aria-label="Report sections"><a href="#results">Results</a><a href="#meaning">What the score means</a><a href="#data">Where data comes from</a><a href="#next">What is missing</a></nav>
<div class="notice"><strong>Before reading the numbers</strong><br>{banner}</div>{cards}
<section id="results"><h2>1. What was calculated?</h2>
<p>Our planned experiment has two versions of fadrozole (R and S), each tested against two enzymes. That makes four combinations.</p>
<div class="table-wrap"><table><thead><tr><th>Planned combination</th><th>Data used in this run</th><th>What happened</th><th>Deformation score</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
{demo_explanation}<div class="cards">{''.join(comparison_cards)}</div></section>
<section id="meaning"><h2>2. What does the energy number mean?</h2>
<p>Imagine a molecule being bent to fit inside a protein pocket. We want to estimate the energy cost of that shape change.</p>
<div class="formula">Deformation score = energy in the pocket-imposed shape − energy after the same fragment relaxes</div>
<p>We compare the same atoms using the same model and electronic state. An <strong>electronvolt (eV)</strong> is a unit of energy.
A smaller score means less deformation cost under this model.</p>
<p>In the demo, the “molecule” is an artificial four-atom system governed by a simple spring-like energy function.
Its score of about 0.02 eV only confirms that the calculation steps work together.</p>
<p><strong>What it cannot tell us:</strong> this number alone cannot tell us which drug binds more strongly, how potent it is,
or whether it selectively inhibits one enzyme. Other physical effects and experimental evidence matter.</p>
<details><summary>How would we compare the enzymes?</summary><p>For each ligand, subtract the CYP11B1 deformation score from the CYP11B2 score.
A negative difference would favor CYP11B2 under the lower-deformation hypothesis; a positive difference would favor CYP11B1.
That interpretation needs valid geometry, comparable preparation, sensitivity checks and assay evidence. Synthetic runs receive no preference.</p></details></section>
<section id="data"><h2>3. Where will the real data come from?</h2>
<p>We need three different kinds of data. A protein structure gives us a starting shape; it does not give us a selectivity answer.</p>
<ol class="steps"><li><strong>Download experimentally measured structures</strong>
The starting coordinates come from the public Protein Data Bank:
<a href="https://www.rcsb.org/structure/6M7X">6M7X: CYP11B1 with S-fadrozole</a> and
<a href="https://www.rcsb.org/structure/4FDH">4FDH: CYP11B2 with fadrozole</a>.
The <a href="https://doi.org/10.1074/jbc.RA118.006214">comparative structural study</a> identifies the R form in CYP11B2.
Both PDB files were downloaded during initial project setup, with source records and file hashes.</li>
<li><strong>Prepare the structures and model the missing combinations</strong>
A chemistry reviewer selects a protein chain, resolves missing atoms and alternate positions, adds hydrogens,
and defines charge, spin and the pocket boundary. We also need modeled poses for R-fadrozole in CYP11B1 and S-fadrozole in CYP11B2.
Those two poses must be labeled as modeled and checked, not presented as experimental measurements.</li>
<li><strong>Generate calculated energies with a suitable model</strong>
A compatible machine-learned interatomic potential takes the prepared atomic coordinates and returns energies and forces.
Our workflow uses those outputs to relax structures and calculate deformation scores.
These numbers will be generated by the model; they are not values downloaded from the PDB.</li>
<li><strong>Collect experimental measurements for comparison</strong>
We need published inhibition or binding assays for the specific ligand form and enzyme.
Record the source, species, assay conditions, units and uncertainty. Measurements such as IC50, Ki and Kd
cannot simply be mixed. No quantitative assay table has been curated yet.</li></ol></section>
<section id="next"><h2>4. What is missing, and how do we get it?</h2>
<p class="muted">Initial project setup status, recorded 19 September 2026. This checklist is not a live check of compute or preparation progress.</p>
<div class="table-wrap"><table><thead><tr><th>Needed</th><th>Current status</th><th>Next action</th></tr></thead><tbody>
<tr><td>Starting structures</td><td><span class="badge">Downloaded</span></td><td>Inspect the raw 6M7X and 4FDH structures and select the starting chain/pose.</td></tr>
<tr><td>One calculation-ready complex</td><td><span class="badge pending">Missing</span></td><td>Have the chemistry owner review atoms, caps, protonation, charge, spin and coordination limits; complete the prepared-system input.</td></tr>
<tr><td>A suitable energy model</td><td><span class="badge pending">Not connected</span></td><td>Confirm a checkpoint or BioNeMo service, verify its element/state support, then connect it through the backend adapter.</td></tr>
<tr><td>Working model compute</td><td><span class="badge pending">Needs verification</span></td><td>The initial NVIDIA check failed. Restore GPU access or use another verified model environment, and confirm memory and budget.</td></tr>
<tr><td>The two crossed poses</td><td><span class="badge pending">Not modeled</span></td><td>Use a consistent pose-generation method and inspect stereochemistry and heme coordination.</td></tr>
<tr><td>Experimental selectivity evidence</td><td><span class="badge pending">Not curated</span></td><td>Find comparable, sourced assays for each enantiomer and both enzymes.</td></tr>
<tr><td>Confidence in the interpretation</td><td><span class="badge pending">Not tested</span></td><td>Check alternative poses and preparation choices, compare geometry baselines, and assess feasible quantum reference calculations.</td></tr>
</tbody></table></div>
<div class="callout"><strong>The next milestone is one real complex.</strong><p>Prepare and review the experimental S-fadrozole–CYP11B1 complex,
connect a compatible model, run it, and inspect the resulting geometry and energies together. Then expand to all four combinations.</p></div></section>
<section><h2>5. Technical details, if you need them</h2><p>You can skip this section. These records retain the exact calculation values, checks and provenance.</p>
{details}<details><summary>Comparison records</summary><pre>{esc(json.dumps(comparisons, indent=2))}</pre></details></section>
<footer>This is a feasibility study. Software success is a first milestone; it is not evidence of scientifically accurate selectivity predictions.</footer>
</main></body></html>'''
    Path(path).write_text(document)
