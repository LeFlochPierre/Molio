"""Capture a read-only Molio walkthrough and encode a README-friendly MP4.

Requires Playwright, a Chromium browser, and imageio-ffmpeg. Start Molio first.
Uses the actual local app and saved projects; never submits predictions or saves
proposals. Source frames are temporary, while the MP4, poster and manifest remain.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT = 1440, 900
CAPTURE_FPS = 15


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8001')
    parser.add_argument('--out', type=Path, default=ROOT / 'docs/media')
    parser.add_argument('--browser', help='Optional Chrome/Chromium executable')
    args = parser.parse_args()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    video = output / 'molio-walkthrough.mp4'
    if video.exists():
        parser.error(f'{video} already exists; choose a new --out directory.')
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    scenes, errors, blocked = [], [], []
    with tempfile.TemporaryDirectory(prefix='molio-capture-') as temporary:
        scratch = Path(temporary)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=args.browser or shutil.which('google-chrome'),
                args=['--enable-unsafe-swiftshader'],
            )
            context = browser.new_context(viewport={'width': WIDTH, 'height': HEIGHT}, device_scale_factor=1)
            # Permit read-only chemistry analysis, but protect the user's projects.
            def guard(route):
                request = route.request
                path = request.url.split('?', 1)[0]
                if request.method not in ('GET', 'HEAD') and not path.endswith(('/api/designs', '/api/preview')):
                    blocked.append(request.url)
                    route.abort()
                else:
                    route.continue_()
            context.route('**/api/**', guard)
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))

            def capture(name, seconds):
                folder = scratch / name
                folder.mkdir()
                start = time.monotonic()
                count = 0
                print(f'Recording: {name} ({seconds}s)', flush=True)
                while time.monotonic() - start < seconds:
                    before = time.monotonic()
                    page.screenshot(path=str(folder / f'{count:05d}.jpg'), type='jpeg', quality=93, animations='allow')
                    count += 1
                    page.wait_for_timeout(max(0, 1 / CAPTURE_FPS - (time.monotonic() - before)) * 1000)
                scenes.append({'name': name, 'seconds': seconds, 'frames': count})

            page.goto(args.url)
            page.wait_for_selector('#molio-logo-view[data-ready=true]')
            capture('01-welcome', 5)
            page.locator('#welcome-start').click()
            page.wait_for_selector('.project-card')
            page.wait_for_function('() => projectPreviewSession.cards.filter(c => c.visible).every(c => c.view || c.element.classList.contains("sequence-only"))')
            page.mouse.move(1400, 150)
            page.screenshot(path=str(output / 'molio-library.png'))
            capture('02-project-library', 4)
            page.locator('[data-workspace="brd4"]').hover()
            capture('03-protein-preview', 3)
            page.locator('[data-workspace="brd4"]').click()
            page.wait_for_selector('#home-page:not([hidden])')
            page.wait_for_selector('#home-molecules .tile-art img')
            if page.locator('#gallery-motion').get_attribute('aria-pressed') == 'true':
                page.locator('#gallery-motion').click()
            page.mouse.move(1400, 150)
            capture('04-workspace', 5)
            page.locator('[data-open-molecule="CHEMBL1828983"]').click()
            page.wait_for_selector('#detail-molecule-shape canvas')
            page.mouse.move(1400, 150)
            page.screenshot(path=str(output / 'molio-molecule.png'))
            capture('05-molecule', 6)
            page.locator('#molecule-design').click()
            page.wait_for_selector('#design-list .design-card')
            page.wait_for_selector('#design-parent-shape canvas')
            page.mouse.move(1400, 150)
            capture('06-design-overview', 2)
            page.locator('.design-layout').evaluate('(e)=>window.scrollTo({top:window.scrollY+e.getBoundingClientRect().top-140,behavior:"instant"})')
            capture('06-design-comparison', 4)
            page.locator('#open-pocket-page').click()
            page.wait_for_selector('#pocket-page:not([hidden]) #viewer canvas')
            if page.locator('#rotate').get_attribute('aria-pressed') == 'true':
                page.locator('#rotate').click()
            page.mouse.move(1400, 150)
            capture('07-protein-pocket', 6)
            page.goto(args.url)
            page.wait_for_selector('#molio-logo-view[data-ready=true]')
            capture('08-closing', 3)
            browser.close()
        if errors or blocked:
            raise RuntimeError(f'Recording failed checks: errors={errors}, blocked writes={blocked}')
        print('Encoding MP4…', flush=True)
        clips = []
        for scene in scenes:
            clip = scratch / (scene['name'] + '.mp4')
            subprocess.run([ffmpeg, '-v', 'error', '-framerate', str(scene['frames'] / scene['seconds']),
                            '-i', str(scratch / scene['name'] / '%05d.jpg'), '-vf', 'fps=30',
                            '-c:v', 'libx264', '-preset', 'fast', '-crf', '19', '-pix_fmt', 'yuv420p',
                            '-an', str(clip)], check=True)
            clips.append(clip)
        listing = scratch / 'clips.txt'
        listing.write_text(''.join(f"file '{clip.name}'\n" for clip in clips))
        subprocess.run([ffmpeg, '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(listing),
                        '-c', 'copy', '-movflags', '+faststart', str(video)], check=True)
        subprocess.run([ffmpeg, '-v', 'error', '-i', str(video), '-f', 'null', '-'], check=True)
    manifest = {'created_utc': datetime.now(timezone.utc).isoformat(), 'width': WIDTH, 'height': HEIGHT,
                'encoded_fps': 30, 'duration_seconds': sum(s['seconds'] for s in scenes), 'audio': 'none',
                'source': 'Actual local Molio UI and saved data; no mocked scientific results',
                'new_predictions': False, 'project_writes': False, 'scenes': scenes,
                'presentation': 'Overview and pocket rotation paused using UI controls; design comparison scrolled into view.',
                'timing': 'Scene captures resampled to presentation durations; not a performance benchmark.',
                'verification': 'Full MP4 decoded successfully; no browser errors or blocked writes.'}
    (output / 'molio-recording.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Saved {video} ({video.stat().st_size / 1e6:.1f} MB)', flush=True)


if __name__ == '__main__':
    main()
