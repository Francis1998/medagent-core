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


def terminal_palette() -> Image.Image:
    """Return a fixed palette: the terminal colors plus anti-aliasing blends of the text."""
    colors = [BG, BAR, *DOTS]
    blends = ((BG, FG, 6), (BG, CMD, 4), (BG, PROMPT, 4), (BAR, TITLE, 4))
    for background, foreground, steps in blends:
        for step in range(1, steps + 1):
            colors.append(
                tuple(
                    round(b + (f - b) * step / steps)
                    for b, f in zip(background, foreground, strict=True)
                )
            )
    flat = [channel for color in colors for channel in color]
    palette = Image.new("P", (1, 1))
    palette.putpalette(flat + flat[-3:] * (32 - len(colors)))
    return palette


def render_transcript(
    raw: list[str],
    output: Path,
    *,
    title: str = "",
    cols: int = 96,
    rows: int = 26,
    font_size: int = 14,
    type_steps: int = 12,
    line_ms: int = 90,
    final_hold_ms: int = 3500,
    block_output: bool = False,
    fixed_palette: bool = False,
) -> int:
    """Render transcript lines into an animated GIF at ``output``; return the frame count.

    ``block_output`` reveals each command's output in one frame (held ``line_ms``
    per line) instead of line by line. ``fixed_palette`` maps every frame onto
    ``terminal_palette()``, so unchanged pixels stay identical between frames and
    the GIF stores only what changed (about 10x smaller than per-frame adaptive
    palettes, which can also drop the window-button colors).
    """
    font = load_font(font_size)
    char_w = max(1, int(font.getlength("M"))) if hasattr(font, "getlength") else 7
    line_h = font_size + 6
    pad = 16
    bar_h = 30
    width = pad * 2 + char_w * cols
    height = bar_h + pad * 2 + line_h * rows
    wrapped = wrap_lines(raw, cols)

    def draw_screen(visible: list[tuple[str, str]]) -> Image.Image:
        image = Image.new("RGB", (width, height), BG)
        draw = ImageDraw.Draw(image)
        draw.rectangle([0, 0, width, bar_h], fill=BAR)
        for index, color in enumerate(DOTS):
            x = 14 + index * 20
            draw.ellipse([x, 10, x + 11, 21], fill=color)
        if title:
            draw.text((80, 8), title, font=font, fill=TITLE)
        window = visible[-rows:]
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
        return image

    palette = terminal_palette() if fixed_palette else None

    frames: list[Image.Image] = []
    durations: list[int] = []

    def draw_frame(visible: list[tuple[str, str]], hold_ms: int) -> None:
        image = draw_screen(visible)
        if palette is None:
            frames.append(image.convert("P", palette=Image.ADAPTIVE, colors=32))
        else:
            frames.append(image.quantize(palette=palette, dither=Image.Dither.NONE))
        durations.append(hold_ms)

    visible: list[tuple[str, str]] = []
    pending: list[tuple[str, str]] = []

    def flush_output() -> None:
        if pending:
            visible.extend(pending)
            draw_frame(visible, line_ms * len(pending))
            pending.clear()

    draw_frame(visible, 600)
    for kind, text in wrapped:
        if kind == "cmd":
            flush_output()
            body = text[2:]
            step = max(1, len(body) // type_steps)
            for end in range(step, len(body) + step, step):
                draw_frame([*visible, (kind, "$ " + body[:end])], 60)
            visible.append((kind, text))
            draw_frame(visible, 450)
        elif block_output:
            pending.append((kind, text))
        else:
            visible.append((kind, text))
            draw_frame(visible, line_ms)
    flush_output()
    draw_frame(visible, final_hold_ms)

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
    return len(frames)


def render(args: argparse.Namespace) -> None:
    raw = Path(args.input).read_text(encoding="utf-8").rstrip("\n").splitlines()
    output = Path(args.output)
    frame_count = render_transcript(
        raw,
        output,
        title=args.title,
        cols=args.cols,
        rows=args.rows,
        font_size=args.font_size,
        type_steps=args.type_steps,
        line_ms=args.line_ms,
        final_hold_ms=args.final_hold_ms,
    )
    print(f"wrote {output} ({output.stat().st_size} bytes, {frame_count} frames)")


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
