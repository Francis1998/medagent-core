#!/usr/bin/env python3
"""Render a REAL captured terminal transcript into an animated terminal-style GIF.

Usage (no global Pillow needed):
    uv run --with pillow python render_transcript_gif.py \
        --input transcript.txt --output assets/demo/feature.gif --title "nexus: /v1/responses"

Transcript format: plain text captured from actually running the commands.
Lines starting with "$ " are typed as commands (typing animation); every other
line is revealed as command output. Long lines are wrapped; the view scrolls.
"""

from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BG = (13, 17, 23)
BAR = (33, 38, 45)
FG = (201, 209, 217)
CMD = (126, 231, 135)
PROMPT = (88, 166, 255)
TITLE = (139, 148, 158)
DOTS = [(255, 95, 86), (255, 189, 46), (39, 201, 63)]

FONT_CANDIDATES = [
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/Monaco.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/dejavu/DejaVuSansMono.ttf",
]


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def wrap_lines(raw: list[str], cols: int) -> list[tuple[str, str]]:
    """Return (kind, text) rows where kind is 'cmd' or 'out'."""
    rows: list[tuple[str, str]] = []
    for line in raw:
        kind = "cmd" if line.startswith("$ ") else "out"
        pieces = textwrap.wrap(line, cols, replace_whitespace=False, drop_whitespace=False) or [""]
        for index, piece in enumerate(pieces):
            rows.append((kind if index == 0 else ("cmdcont" if kind == "cmd" else "out"), piece))
    return rows


def render(args: argparse.Namespace) -> None:
    raw = Path(args.input).read_text(encoding="utf-8").rstrip("\n").splitlines()
    font = load_font(args.font_size)
    char_w = max(1, int(font.getlength("M"))) if hasattr(font, "getlength") else 7
    line_h = args.font_size + 6
    pad = 16
    bar_h = 30
    width = pad * 2 + char_w * args.cols
    height = bar_h + pad * 2 + line_h * args.rows
    rows = wrap_lines(raw, args.cols)

    frames: list[Image.Image] = []
    durations: list[int] = []

    def draw_frame(visible: list[tuple[str, str]], hold_ms: int) -> None:
        image = Image.new("RGB", (width, height), BG)
        draw = ImageDraw.Draw(image)
        draw.rectangle([0, 0, width, bar_h], fill=BAR)
        for index, color in enumerate(DOTS):
            x = 14 + index * 20
            draw.ellipse([x, 10, x + 11, 21], fill=color)
        if args.title:
            draw.text((80, 8), args.title, font=font, fill=TITLE)
        window = visible[-args.rows :]
        y = bar_h + pad
        for kind, text in window:
            if kind == "cmd":
                draw.text((pad, y), "$", font=font, fill=PROMPT)
                draw.text((pad + char_w * 2, y), text[2:], font=font, fill=CMD)
            elif kind == "cmdcont":
                draw.text((pad, y), text, font=font, fill=CMD)
            else:
                draw.text((pad, y), text, font=font, fill=FG)
            y += line_h
        frames.append(image.convert("P", palette=Image.ADAPTIVE, colors=32))
        durations.append(hold_ms)

    visible: list[tuple[str, str]] = []
    draw_frame(visible, 600)
    for kind, text in rows:
        if kind == "cmd":
            body = text[2:]
            step = max(1, len(body) // args.type_steps)
            for end in range(step, len(body) + step, step):
                draw_frame([*visible, (kind, "$ " + body[:end])], 60)
            visible.append((kind, text))
            draw_frame(visible, 450)
        else:
            visible.append((kind, text))
            draw_frame(visible, args.line_ms)
    draw_frame(visible, args.final_hold_ms)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=1,
    )
    print(f"wrote {output} ({output.stat().st_size} bytes, {len(frames)} frames)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--title", default="")
    parser.add_argument("--cols", type=int, default=96)
    parser.add_argument("--rows", type=int, default=26)
    parser.add_argument("--font-size", type=int, default=14)
    parser.add_argument("--type-steps", type=int, default=12)
    parser.add_argument("--line-ms", type=int, default=90)
    parser.add_argument("--final-hold-ms", type=int, default=3500)
    render(parser.parse_args())


if __name__ == "__main__":
    main()
