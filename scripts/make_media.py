#!/usr/bin/env python3
"""Regenerate docs/screenshot.png and docs/demo.gif headlessly.

    uv sync --group media && uv run python scripts/make_media.py

Drives the app against the bundled demo graph with Textual's test pilot,
exports SVG screenshots after each step and converts them with cairosvg
and Pillow.  No terminal recording involved, so the result is reproducible.
"""

from __future__ import annotations

import asyncio
import io
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw, ImageFont

from rosgraph_tui.app import RosgraphApp
from rosgraph_tui.model import EntityRef, Kind
from rosgraph_tui.source import demo_source

DOCS = Path(__file__).resolve().parent.parent / "docs"
SIZE = (110, 24)
WIDTH = 960  # px, GIF and screenshot width

KEY_LABELS = {
    "enter": "Enter",
    "escape": "Esc",
    "left": "←",
    "right": "→",
    "up": "↑",
    "down": "↓",
    "ctrl+t": "Ctrl+T",
    "ctrl+r": "Ctrl+R",
    "backspace": "Backspace",
}
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def key_overlay(frame: Image.Image, keys: tuple[str, ...]) -> Image.Image:
    """Draw a keycap badge for the pressed keys into the top-right corner."""
    if not keys:
        return frame
    label = "  ".join(KEY_LABELS.get(k, k) for k in keys)
    frame = frame.convert("RGBA")
    overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _font(max(14, frame.width // 48))
    pad_x, pad_y = 12, 6
    left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
    text_w, text_h = right - left, bottom - top
    box_w, box_h = text_w + 2 * pad_x, text_h + 2 * pad_y
    x1, y1 = frame.width - box_w - 14, 8
    draw.rounded_rectangle((x1, y1, x1 + box_w, y1 + box_h), radius=8, fill=(255, 196, 0, 235))
    draw.text((x1 + pad_x - left, y1 + pad_y - top), label, font=font, fill=(20, 20, 20, 255))
    return Image.alpha_composite(frame, overlay).convert("RGB")


async def record() -> tuple[list[tuple[Image.Image, int]], Image.Image]:
    app = RosgraphApp(demo_source(), refresh_rate=0)
    frames: list[tuple[Image.Image, int]] = []
    still: Image.Image | None = None

    def snap() -> Image.Image:
        png = cairosvg.svg2png(bytestring=app.export_screenshot().encode(), output_width=WIDTH)
        return Image.open(io.BytesIO(png)).convert("RGB")

    async with app.run_test(size=SIZE) as pilot:
        async def settle() -> None:
            await app.workers.wait_for_complete()
            await pilot.pause()
            await pilot.pause()

        async def step(*keys: str, hold: int = 700) -> None:
            if keys:
                await pilot.press(*keys)
            await settle()
            frames.append((key_overlay(snap(), keys), hold))

        await step(hold=1200)  # the full list
        for key in "cam":  # type to filter; the best match is highlighted
            await step(key, hold=450)
        await step(hold=900)
        while app.column(1).highlighted_ref != EntityRef(Kind.TOPIC, "/camera/image_raw"):
            await step("down", hold=500)  # walk down to the topic we want
        await step(hold=600)
        await step("enter", hold=1200)  # root on the topic
        still = snap()
        await step("right", hold=600)  # into the subscribers column
        await step("right", hold=1200)  # root on /camera/rectify
        await step("right", hold=600)
        await step("right", hold=1200)  # root on /camera/image_rect
        await step("escape", hold=900)  # back to the topic list
        await step("escape", hold=900)  # back to everything
        await step("ctrl+t", hold=1400)  # show hidden names
        await step("ctrl+t", hold=1400)
    assert still is not None
    return frames, still


def main() -> None:
    frames, still = asyncio.run(record())
    DOCS.mkdir(exist_ok=True)
    still.save(DOCS / "screenshot.png", optimize=True)
    images = [frame.quantize(colors=64, method=Image.Quantize.MEDIANCUT) for frame, _ in frames]
    images[0].save(
        DOCS / "demo.gif",
        save_all=True,
        append_images=images[1:],
        duration=[hold for _, hold in frames],
        loop=0,
        optimize=True,
    )
    for name in ("screenshot.png", "demo.gif"):
        print(f"{name}: {(DOCS / name).stat().st_size / 1024:.0f} KiB")


if __name__ == "__main__":
    main()
