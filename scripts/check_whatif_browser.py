"""Real browser acceptance for the local what-if slice; no GPU or internet needed.

Run with a Python environment containing Playwright and installed Chromium.
"""
import argparse
import json
from pathlib import Path
import sys
import threading
import tempfile
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from molecular_lab.server import Handler
from molecular_lab.proposals import ProposalStore
from playwright.sync_api import sync_playwright


class QuietHandler(Handler):
    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--screenshots', type=Path)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler)
    temp = tempfile.TemporaryDirectory()
    server.proposal_store = ProposalStore(Path(temp.name) / 'proposals.sqlite3')
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    errors, external = [], []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=['--enable-unsafe-swiftshader'])
            context = browser.new_context(viewport={'width':1440,'height':1100}, device_scale_factor=1)
            def route(request):
                if request.request.url.startswith(base + '/'):
                    request.continue_()
                else:
                    external.append(request.request.url)
                    request.abort()
            context.route('**/*', route)
            page = context.new_page()
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.on('console', lambda m: errors.append(m.text) if m.type == 'error' and not ('400 (Bad Request)' in m.text and m.location.get('url', '').endswith('/api/preview')) else None)
            page.goto(base+'/?workspace=brd4#/explore')
            page.wait_for_function('() => window.whatifViewerReady === true')
            assert page.locator('#pair-list button').count() == 7
            assert page.locator('#fold').inner_text() == '2.5×'
            assert page.locator('#edit-insight .edit-example').count() == 2
            assert page.locator('#comparison .molecule-canvas[data-ready=true]').count() == 2
            assert page.locator('#viewer canvas').count() >= 1
            assert page.locator('#residues button').count() == 8
            assert not page.evaluate('() => document.documentElement.scrollWidth > innerWidth')
            if args.screenshots:
                args.screenshots.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(args.screenshots/'whatif-desktop.png'), full_page=True)
            # Pick actual projected atoms to exercise hover highlighting.
            point = page.evaluate("() => {const v=moleculeViewers.get('compound-CHEMBL1828980').viewer;return v.modelToScreen(v.selectedAtoms({})[0]);}")
            page.mouse.move(point['x'], point['y']-page.evaluate('() => scrollY'))
            page.wait_for_function("() => document.getElementById('compound-CHEMBL1828980').dataset.hoveredAtom !== undefined")
            page.mouse.move(2,2)
            page.locator('#mode-2d').click()
            assert page.locator('#comparison .molecule-2d').first.is_visible()
            page.locator('#mode-3d').click()
            assert page.locator('#comparison .molecule-canvas').first.is_visible()
            # Activity map preserves measurement identity and hands off to guided design.
            page.locator('#open-map').click()
            assert page.locator('.map-row').count() == 9
            page.locator('.map-row[data-compound="CHEMBL1828980"]').click()
            assert page.locator('#map-value').inner_text() == '24,600 nM IC₅₀'
            assert page.locator('#map-molecule[data-ready=true]').count() == 1
            if args.screenshots:
                page.screenshot(path=str(args.screenshots/'whatif-activity-map.png'), full_page=True)
            page.locator('#map-design').click()
            page.wait_for_selector('.guided-option')
            assert 'Already measured' in page.locator('.guided-option').first.inner_text()
            page.locator('.guided-option').first.click()
            page.wait_for_function("() => latestPreview?.edit_evidence?.status === 'evidence_found' && !latestPreview.same_as_parent")
            assert page.locator('#variant-hypothesis').input_value().startswith('Does the ketone')
            assert page.locator('#save-variant').is_enabled()
            if args.screenshots:
                page.screenshot(path=str(args.screenshots/'whatif-guided-edit.png'), full_page=True)
            page.locator('#close-variant').click()
            page.locator('#open-pocket-page').click()
            page.locator('#expand-protein').click()
            assert page.locator('#expand-protein').get_attribute('aria-expanded') == 'true'
            assert page.locator('#viewer').bounding_box()['height'] > 500
            page.keyboard.press('Escape')
            assert page.locator('#expand-protein').get_attribute('aria-expanded') == 'false'
            page.locator('#open-explore').click()
            # Test both ratio directions and the stereo-specific reference distinction.
            page.locator('[data-pair="pair-5"]').click()
            assert page.locator('#fold').inner_text() == '6.6×'
            assert page.locator('#fold-label').inner_text() == 'higher IC₅₀ for compound B'
            page.locator('[data-pair="pair-4"]').click()
            assert 'not an exact assay-to-pose match' in page.locator('#reference-note').inner_text()
            assert '3SVG' in page.locator('.pdb-pill').inner_text()
            page.locator('#search').fill('nothing_matches')
            assert page.locator('#no-results').is_visible()
            page.locator('#search').fill('carboxylic')
            assert page.locator('#pair-list button').count() == 1
            page.locator('#search').fill('')
            page.locator('#open-library').click()
            assert page.locator('#library').is_visible()
            assert page.locator('.library-card').count() == 9
            page.keyboard.press('Escape')
            assert not page.locator('#library').is_visible()
            # Notes survive comparison switches and reloads; export retains raw evidence.
            page.locator('[data-pair="pair-1"]').click()
            page.locator('#open-evidence').click()
            page.locator('#hypothesis').fill('Test the same ethoxy edit on a second scaffold.')
            page.locator('#close-evidence').click()
            page.locator('#pin').click()
            page.locator('[data-pair="pair-2"]').click()
            assert page.locator('#hypothesis').input_value() == ''
            page.reload()
            page.wait_for_function('() => window.whatifViewerReady === true')
            page.locator('[data-pair="pair-1"]').click()
            assert page.locator('#pin-count').inner_text() == '1'
            assert page.locator('#hypothesis').input_value().startswith('Test the same ethoxy')
            with page.expect_download() as download_info:
                page.locator('#export').click()
            export = json.loads(Path(download_info.value.path()).read_text())
            assert export['comparisons'][0]['id'] == 'pair-1'
            assert export['comparisons'][0]['user_hypothesis'].startswith('Test the same ethoxy')
            assert export['predictions'] == []
            assert len(export['provenance']['sources']) == 5
            # Exercise actual rendering controls and atom picking, not mocked canvas output.
            page.locator('#open-pocket-page').click()
            page.locator('#protein').click()
            page.locator('#pocket').click()
            page.locator('#surface').click()
            page.wait_for_timeout(800)
            assert page.locator('#surface').get_attribute('aria-pressed') == 'true'
            page.locator('#surface').click()
            page.locator('#waters').click()
            page.locator('#residues button').first.click()
            page.locator('#reset').click()
            page.locator('#measure').click()
            page.locator('#viewer').scroll_into_view_if_needed()
            points = page.evaluate('''() => state.viewer.selectedAtoms({resn:'ODR'}).slice(0,2).map(a => state.viewer.modelToScreen(a))''')
            for point in points:
                page.mouse.click(point['x'], point['y'] - page.evaluate('() => scrollY'))
            assert 'Å' in page.locator('#atom-info').inner_text(), page.locator('#atom-info').inner_text()
            assert page.locator('#viewer').get_attribute('data-hovered-residue') is not None
            page.locator('#reset').click()
            page.locator('#open-explore').click()
            # Rapid selection never relabels the reference as a selected ligand.
            for i in [7,2,6,1]:
                page.locator(f'[data-pair="pair-{i}"]').click()
            assert page.locator('#pair-title').inner_text() == 'Add an ethoxy group'
            assert 'Neither selected compound' in page.locator('#reference-note').inner_text()
            # Automatic rotation pauses for interaction and reduced-motion is respected.
            page.locator('#open-pocket-page').click()
            page.locator('#rotate').click()
            assert page.locator('#rotate').get_attribute('aria-pressed') == 'true'
            before = page.evaluate('() => state.viewer.getView()')
            page.wait_for_timeout(250)
            assert page.evaluate('() => state.viewer.getView()') != before
            page.locator('#measure').click()
            assert page.locator('#rotate').get_attribute('aria-pressed') == 'false'
            page.locator('#open-explore').click()
            # Actual RDKit preview, invalidation, local save, and exported provenance.
            page.locator('.create-variant').first.click()
            page.wait_for_function('() => latestPreview !== null')
            assert page.locator('#save-variant').is_disabled()
            page.locator('#variant-smiles').fill('this is not a molecule')
            assert page.locator('#save-variant').is_disabled()
            page.wait_for_function("() => document.getElementById('variant-status').classList.contains('error')")
            page.locator('#variant-smiles').fill('Cc1noc(C)c1-c1ccccc1F')
            page.wait_for_function('() => latestPreview !== null && !latestPreview.same_as_parent')
            assert page.locator('#variant-preview img').count() == 2
            assert page.locator('#variant-preview .molecule-canvas[data-ready=true]').count() == 2
            assert 'No supported edit evidence' in page.locator('#variant-edit-evidence').inner_text()
            page.locator('#variant-name').fill('Fluoro idea')
            page.locator('#variant-hypothesis').fill('Does adding fluorine change the measured potency?')
            if args.screenshots:
                page.screenshot(path=str(args.screenshots/'whatif-variant.png'), full_page=True)
            page.locator('#save-variant').click()
            page.wait_for_function("() => !isPageOpen('variant-dialog')")
            page.reload()
            page.wait_for_function('() => window.whatifViewerReady === true')
            page.locator('#open-proposals').click()
            page.wait_for_selector('.proposal-row')
            assert 'Fluoro idea' in page.locator('#proposals-list').inner_text()
            with page.expect_download() as proposal_download:
                page.locator('[data-export-proposal]').first.click()
            proposal = json.loads(Path(proposal_download.value.path()).read_text())
            assert proposal['activity'] is None and proposal['bound_pose'] is None
            assert proposal['hypothesis'].startswith('Does adding fluorine')
            assert proposal['neighbours'][0]['observation']['assay_id'] == 'CHEMBL1832996'
            page.locator('#close-proposals').click()
            page.locator('[data-pair="pair-2"]').click()
            page.locator('.create-variant').first.click()
            page.wait_for_function('() => latestPreview !== null')
            page.locator('#variant-smiles').fill('Cc1noc(C)c1-c1cccc(C(C)O)c1')
            page.wait_for_function("() => latestPreview?.edit_evidence?.status === 'evidence_found'")
            assert page.locator('#variant-edit-evidence .edit-example').count() == 2
            assert page.locator('#variant-parent[data-ready=true]').count() == 1
            assert page.locator('#variant-proposal[data-ready=true]').count() == 1
            assert 'already appears' in page.locator('#variant-status').inner_text()
            page.locator('#close-variant').click()
            # Offline installations expose setup honestly and still enumerate stereo choices.
            page.locator('#open-experiments').click()
            page.locator('#run-setup-tab').click()
            page.wait_for_function("() => document.querySelectorAll('.experiment-choice').length >= 9")
            assert page.locator('#start-experiment').is_disabled()
            assert page.locator('#experiment-repeats').input_value() == '3'
            assert 'not configured' in page.locator('#experiment-runtime').inner_text()
            assert page.locator('select[aria-label="Stereochemistry for CHEMBL1828982"] option').count() == 3
            page.locator('.experiment-choice input').first.check()
            assert '1 / 3' in page.locator('#experiment-selection').inner_text()
            assert '3 predictions' in page.locator('#experiment-selection').inner_text()
            page.locator('#experiment-repeats').select_option('1')
            assert '1 predictions' in page.locator('#experiment-selection').inner_text()
            page.locator('.experiment-choice input').nth(1).check()
            page.locator('.experiment-choice input').first.uncheck()
            page.locator('.experiment-choice input').first.check()
            selected = page.evaluate('() => selectedCandidates().map(c=>c.id)')
            assert selected == ['CHEMBL1828979','CHEMBL1828978'], selected
            if args.screenshots:
                page.screenshot(path=str(args.screenshots/'whatif-experiments.png'))
            page.locator('#close-experiments').click()
            page.emulate_media(reduced_motion='reduce')
            page.reload()
            page.wait_for_function('() => window.whatifViewerReady === true')
            assert page.locator('#rotate').get_attribute('aria-pressed') == 'false'
            # Narrow viewport remains usable with no page-level horizontal overflow.
            page.set_viewport_size({'width':390,'height':844})
            page.evaluate('() => scrollTo(0,0)')
            assert not page.evaluate('() => document.documentElement.scrollWidth > innerWidth')
            page.locator('#toggle-reference').click()
            page.locator('#open-map').click()
            assert page.locator('.map-row').count() == 9
            assert page.locator('#activity-map').evaluate('(el) => el.scrollWidth <= el.clientWidth')
            page.locator('#close-map').click()
            page.locator('#toggle-reference').click()
            page.locator('#open-library').click()
            page.locator('#close-library').click()
            page.locator('#open-experiments').click()
            page.locator('#run-setup-tab').click()
            page.wait_for_function("() => document.querySelectorAll('.experiment-choice').length >= 9")
            assert page.locator('#experiments-dialog').evaluate('(el) => el.scrollWidth <= el.clientWidth')
            page.locator('#close-experiments').click()
            if args.screenshots:
                page.screenshot(path=str(args.screenshots/'whatif-mobile.png'), full_page=True)
            assert not external, external
            assert not errors, errors
            browser.close()
            print('PASS: offline assets, 3D/WebGL, comparisons, identity labels, search, library, notes, export, surface, atom measurement, rapid selection, mobile layout, 3D compound hover, and edit evidence; no unexpected browser errors.')
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
        temp.cleanup()


if __name__ == '__main__':
    main()
