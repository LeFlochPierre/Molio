"""Frame the original pipeline artwork in self-contained SVG cards for GitHub.

SVG supplies rounded borders, shadows, labels and connectors without README CSS.
The original generated PNG illustrations remain unchanged.
"""
from pathlib import Path
import base64
from html import escape

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'docs/media/pipeline'
STAGES = [
    ('protein', 'Choose a protein', ['Find a target, its sequence', 'and an available 3D model.']),
    ('molecule', 'Add a molecule', ['Search PubChem, paste SMILES', 'or try an example.']),
    ('design', 'Explore designs', ['Edit your molecule or explore', 'suggested variations.']),
    ('predict', 'Compare predictions', ['Choose a baseline and designs.', 'Run Boltz-2 with 1 or 3 seeds.']),
    ('inspect', 'Inspect the results', ['Explore scores, probabilities,', 'seed variation and 3D poses.']),
    ('save', 'Save & plan next', ['Export your record and choose', 'the next question to test.']),
]


def main():
    for index, (name, title, lines) in enumerate(STAGES, 1):
        data = base64.b64encode((ASSETS / f'{name}.png').read_bytes()).decode('ascii')
        description = ' '.join(lines)
        labels = ''.join(f'<text x="128" y="{282 + n*18}">{escape(line)}</text>' for n, line in enumerate(lines))
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="256" height="344" viewBox="0 0 256 344" role="img" aria-labelledby="title description">
<title id="title">{index:02d} · {escape(title)}</title><desc id="description">{escape(description)}</desc>
<defs>
  <filter id="shadow" x="-20%" y="-15%" width="140%" height="140%"><feDropShadow dx="0" dy="5" stdDeviation="5" flood-color="#665389" flood-opacity=".18"/></filter>
  <clipPath id="art"><rect x="24" y="18" width="208" height="204" rx="20"/></clipPath>
</defs>
<rect x="10" y="8" width="236" height="320" rx="27" fill="#fff" filter="url(#shadow)"/>
<image x="26" y="18" width="204" height="204" clip-path="url(#art)" xlink:href="data:image/png;base64,{data}"/>
<rect x="10" y="8" width="236" height="320" rx="27" fill="none" stroke="#e3dced" stroke-width="1.2"/>
<g text-anchor="middle" font-family="Arial, Helvetica, sans-serif">
  <text x="128" y="235" fill="#8c75b0" font-size="12" font-weight="700" letter-spacing="2">{index:02d}</text>
  <text x="128" y="256" fill="#3d4153" font-size="15" font-weight="700">{escape(title)}</text>
  <g fill="#716b7d" font-size="12">{labels}</g>
</g>
</svg>
'''
        (ASSETS / f'{name}-card.svg').write_text(svg)
    (ASSETS / 'arrow-right.svg').write_text('''<svg xmlns="http://www.w3.org/2000/svg" width="28" height="344" viewBox="0 0 28 344"><path d="M3 172h20m-7-7 7 7-7 7" fill="none" stroke="#a395bd" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>\n''')
    (ASSETS / 'arrow-next-row.svg').write_text('''<svg xmlns="http://www.w3.org/2000/svg" width="720" height="56" viewBox="0 0 720 56"><path d="M604 2v10q0 12-12 12H128q-12 0-12 12v15m-6-7 6 7 6-7" fill="none" stroke="#a395bd" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>\n''')


if __name__ == '__main__':
    main()
