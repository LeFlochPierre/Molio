"""Make a compact, 4x highlights GIF from the extended Molio tour.

Requires imageio-ffmpeg. Segment times match record_molio_complete_tour.py.
No app requests or predictions are made.
"""
import argparse
from pathlib import Path
import subprocess

import imageio_ffmpeg


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=root/'docs/media/molio-complete-tour.mp4')
    parser.add_argument('--output', type=Path, default=root/'docs/media/molio-complete-preview.gif')
    args = parser.parse_args()
    if not args.input.is_file():
        parser.error('Input video does not exist')
    if args.output.exists():
        parser.error('Output exists; choose a new filename')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Welcome, protein, input, custom edit, designs, setup, progress, results,
    # predicted pose, PubChem lookup, measured map, and experimental reference.
    parts = [(0,5),(25,34),(42,59),(59,70),(78,96),(96,112),
             (112,124),(124,146),(146,156),(172,182),(198,217)]
    selection = '+'.join(f'gte(t,{a})*lt(t,{b})' for a,b in parts)
    filters = (f"[0:v]select='{selection}',setpts=N/(30*TB)*0.25,"
               "fps=6,scale=720:-1:flags=lanczos,split[a][b];"
               "[a]palettegen=max_colors=96:stats_mode=diff[p];"
               "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle")
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-v', 'error', '-i', str(args.input),
                    '-filter_complex', filters, '-loop', '0', str(args.output)], check=True)
    print(f'Saved {args.output} ({args.output.stat().st_size/1_000_000:.1f} MB)')


if __name__ == '__main__':
    main()
