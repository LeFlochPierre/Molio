"""Render the SVG pipeline cards to portable PNGs and a complete overview.

Run after build_molio_pipeline_cards.py using an environment with Playwright.
Only renders the code-native card layout; original generated artwork is retained.
"""
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'docs/media/pipeline'
NAMES = ['protein', 'molecule', 'design', 'predict', 'inspect', 'save']


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=shutil.which('google-chrome'), args=['--allow-file-access-from-files'])
        page = browser.new_page(viewport={'width':800,'height':800}, device_scale_factor=2)
        for name in [*(name+'-card' for name in NAMES), 'arrow-right', 'arrow-next-row']:
            page.goto((ASSETS/(name+'.svg')).as_uri())
            page.locator('svg').screenshot(path=str(ASSETS/(name+'.png')), omit_background=True)
        # Render the actual README arrangement as a standalone, high-resolution image.
        rows=[]
        for start in (0,3):
            items=[]
            for index,name in enumerate(NAMES[start:start+3]):
                if index:items.append(f'<img class="arrow" src="{(ASSETS/"arrow-right.png").as_uri()}" alt="then">')
                items.append(f'<img class="card" src="{(ASSETS/(name+"-card.png")).as_uri()}" alt="{name}">')
            rows.append('<div class="row">'+''.join(items)+'</div>')
        bridge=f'<img class="bridge" src="{(ASSETS/"arrow-next-row.png").as_uri()}" alt="continue on next row">'
        html='''<html><head><style>
body{margin:0;background:transparent}#pipeline{box-sizing:border-box;width:780px;padding:20px 24px;background:white;border-radius:28px}
.row{display:flex;justify-content:center;align-items:center;gap:4px}.card{width:220px;height:296px}.arrow{width:24px;height:296px}.bridge{display:block;width:720px;height:56px;margin:14px auto}
</style></head><body><div id="pipeline">'''+bridge.join(rows)+'''</div></body></html>'''
        with TemporaryDirectory(prefix='molio-pipeline-') as directory:
            preview=Path(directory)/'pipeline.html'
            preview.write_text(html)
            page.goto(preview.as_uri())
            page.wait_for_function('Array.from(document.images).every(i=>i.complete && i.naturalWidth>0)')
            page.locator('#pipeline').screenshot(path=str(ASSETS/'molio-pipeline-overview.png'), omit_background=True)
        browser.close()


if __name__ == '__main__':
    main()
