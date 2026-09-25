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
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from rosgraph_tui.app import RosgraphApp
from rosgraph_tui.model import EntityRef, Kind
from rosgraph_tui.source import demo_source

DOCS = Path(__file__).resolve().parent.parent / "docs"
SIZE = (110, 24)
WIDTH = 960  # px, GIF and screenshot width

KEY_LABELS = {
    "enter": "↩ enter",
    "escape": "esc",
    "left": "←",
    "right": "→",
    "up": "↑",
    "down": "↓",
    "ctrl+t": "⌃ T",
    "ctrl+r": "⌃ R",
    "ctrl+q": "⌃ Q",
    "backspace": "⌫",
}
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]
HISTORY = 4  # keycaps shown at once, oldest fades out


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


class KeyCaster:
    """KeyCastr-style overlay: a translucent pill at the bottom centre with the
    last few keystrokes as keycaps, the newest bright, older ones fading."""

    def __init__(self) -> None:
        self.history: list[str] = []

    def push(self, keys: tuple[str, ...]) -> None:
        self.history.extend(KEY_LABELS.get(k, k.upper() if len(k) == 1 else k) for k in keys)
        self.history = self.history[-HISTORY:]

    def draw(self, frame: Image.Image) -> Image.Image:
        if not self.history:
            return frame
        scale = 2  # supersample for smooth corners and shadows
        w, h = frame.width * scale, frame.height * scale
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        font = _font(frame.width * scale // 44)
        cap_pad_x, cap_pad_y, cap_gap, pill_pad = 14 * scale, 7 * scale, 8 * scale, 10 * scale

        caps = []
        for label in self.history:
            left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
            caps.append((label, right - left, bottom - top, left, top))
        cap_h = max(c[2] for c in caps) + 2 * cap_pad_y
        widths = [c[1] + 2 * cap_pad_x for c in caps]
        pill_w = sum(widths) + cap_gap * (len(caps) - 1) + 2 * pill_pad
        pill_h = cap_h + 2 * pill_pad
        x0 = (w - pill_w) // 2
        y0 = int(h * 0.70) - pill_h // 2  # over the lower list area, clear of the info lines

        # drop shadow, then the pill
        shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        shadow_box = (x0, y0 + 4 * scale, x0 + pill_w, y0 + pill_h + 4 * scale)
        ImageDraw.Draw(shadow).rounded_rectangle(shadow_box, radius=pill_h // 2, fill=(0, 0, 0, 150))
        shadow = shadow.filter(ImageFilter.GaussianBlur(6 * scale))
        overlay = Image.alpha_composite(overlay, shadow)
        draw = ImageDraw.Draw(overlay)
        pill = (24, 24, 28)
        draw.rounded_rectangle((x0, y0, x0 + pill_w, y0 + pill_h), radius=pill_h // 2, fill=(*pill, 246))

        def fade(color: tuple[int, int, int], amount: float) -> tuple[int, int, int, int]:
            """Blend towards the pill colour; older keycaps sink into the pill."""
            return tuple(int(c + (p - c) * amount) for c, p in zip(color, pill, strict=True)) + (255,)

        x = x0 + pill_pad
        n = len(caps)
        for i, ((label, _tw, _th, left, top), cw) in enumerate(zip(caps, widths, strict=True)):
            age = n - 1 - i  # 0 = newest
            amount = min(0.85, 0.3 * age)
            face = fade((248, 248, 250) if age == 0 else (196, 196, 204), amount)
            edge = fade((150, 150, 160) if age == 0 else (104, 104, 114), amount)
            ink = fade((24, 24, 30), amount * 0.5)
            y = y0 + pill_pad
            # keycap: light face with a darker bottom edge for a little depth
            lift = 3 * scale
            draw.rounded_rectangle((x, y + lift, x + cw, y + cap_h + lift), radius=7 * scale, fill=edge)
            draw.rounded_rectangle((x, y, x + cw, y + cap_h), radius=7 * scale, fill=face)
            draw.text((x + cap_pad_x - left, y + cap_pad_y - top), label, font=font, fill=ink)
            x += cw + cap_gap

        overlay = overlay.resize(frame.size, Image.Resampling.LANCZOS)
        return Image.alpha_composite(frame.convert("RGBA"), overlay).convert("RGB")


async def record() -> tuple[list[tuple[Image.Image, int]], Image.Image]:
    app = RosgraphApp(demo_source(), refresh_rate=0)
    frames: list[tuple[Image.Image, int]] = []
    still: Image.Image | None = None
    caster = KeyCaster()

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
                caster.push(keys)
            await settle()
            frames.append((caster.draw(snap()) if keys else snap(), hold))

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
