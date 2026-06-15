"""
Render one demo video per effect for visual inspection.

Usage:
    python test/render_effects_demos.py

Output: test/preview_output/effects/*.mp4  (15 videos, one per effect)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from moviepy import (
    ColorClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
    VideoFileClip,
    concatenate_videoclips,
)

from app.services import effects as ef

RESOURCES = Path(__file__).parent / "resources"
OUTPUT = Path(__file__).parent / "preview_output" / "effects"
FONT = "Arial"

TEST_VIDEO = str(RESOURCES / "1.png.mp4")
WIKI_IMG = str(RESOURCES / "2.png")
W, H = 1080, 1920


def _gradient(w=W, h=H, duration=3.0):
    X, Y = np.meshgrid(np.linspace(0, 1, w), np.linspace(0, 1, h))
    r = (X * 255).astype(np.uint8)
    g = (Y * 255).astype(np.uint8)
    b = ((1 - X) * 255).astype(np.uint8)
    frame = np.stack([r, g, b], axis=-1)
    return ImageClip(frame).with_duration(duration)


def _label(clip, text, sub="", font_size=56):
    txt = TextClip(
        text=text, font=FONT, font_size=font_size,
        color="white", stroke_color="black", stroke_width=3,
    ).with_position(("center", 60)).with_duration(clip.duration)
    parts = [clip, txt]
    if sub:
        sub_txt = TextClip(
            text=sub, font=FONT, font_size=32,
            color="#cccccc", stroke_color="black", stroke_width=1,
        ).with_position(("center", 120)).with_duration(clip.duration)
        parts.append(sub_txt)
    return CompositeVideoClip(parts, size=clip.size)


def render(name, clip, label, sub=""):
    path = OUTPUT / f"{name}.mp4"
    print(f"  {name}...", end=" ", flush=True)
    labeled = _label(clip, label, sub)
    labeled.write_videofile(str(path), fps=30, logger=None)
    print(f"\033[92m✓\033[0m {path.name}")


# ── 1. Fit Resize ────────────────────────────────────────────
def demo_fit_resize():
    g = _gradient(640, 640, 3)
    r = ef.apply_fit_resize(g, W, H)
    render("01_fit_resize", r, "Fit Resize", "640×640 → 1080×1920 (letterbox)")


# ── 2. Fill Resize ───────────────────────────────────────────
def demo_fill_resize():
    g = _gradient(640, 640, 3)
    r = ef.apply_fill_resize(g, W, H)
    render("02_fill_resize", r, "Fill Resize", "640×640 → 1080×1920 (center-crop)")


# ── 3. Ken Burns ─────────────────────────────────────────────
def demo_ken_burns():
    img = ImageClip(WIKI_IMG).with_duration(3).resized(new_size=(W, H))
    r = ef.apply_ken_burns(img, 1.0, 1.12)
    render("03_ken_burns", r, "Ken Burns Zoom", "1.0× → 1.12× over 3s")


# ── 4. Blur ──────────────────────────────────────────────────
def demo_blur():
    g = _gradient(duration=3)
    r = ef.apply_blur(g, radius=30)
    render("04_blur", r, "Gaussian Blur", "radius=30")


# ── 5. Color Grade ───────────────────────────────────────────
def demo_color_grade():
    g = _gradient(duration=6)
    seg_dur = 1.0
    presets = ["none", "vintage", "cinema", "bw", "warm", "cool"]
    segs = []
    for p in presets:
        seg = g.subclipped(0, seg_dur)
        processed = ef.apply_color_grade(seg, p)
        named = _label(processed, f"Color Grade — {p}")
        segs.append(named)
    r = concatenate_videoclips(segs)
    render("05_color_grade", r, "Color Grade Presets", "none → vintage → cinema → bw → warm → cool")


# ── 6. Vignette ──────────────────────────────────────────────
def demo_vignette():
    g = _gradient(duration=3)
    r = ef.apply_vignette(g, radius=0.4, intensity=0.6)
    render("06_vignette", r, "Vignette", "radius=0.4, intensity=0.6")


# ── 7. Transition ────────────────────────────────────────────
def demo_transition():
    segs = []
    for name, mode, side in [
        ("Fade In", "fade_in", "left"),
        ("Fade Out", "fade_out", "left"),
        ("Slide In (left)", "slide_in", "left"),
        ("Slide Out (left)", "slide_out", "left"),
        ("Shuffle", "shuffle", "left"),
    ]:
        g = _gradient(duration=2)
        r = ef.apply_transition(g, mode, duration=1.0, side=side)
        named = _label(r, f"Transition — {name}")
        segs.append(named)
    r = concatenate_videoclips(segs)
    render("07_transition", r, "Transition Modes")


# ── 8. Crossfade ─────────────────────────────────────────────
def demo_crossfade():
    a = _gradient(duration=3)
    b = ImageClip(WIKI_IMG).with_duration(3).resized(new_size=(W, H))
    r = ef.apply_crossfade(a, b, duration=1.5)
    render("08_crossfade", r, "Crossfade", "3s A → 1.5s overlap → 3s B")


# ── 9. Speed ─────────────────────────────────────────────────
def demo_speed():
    clip = VideoFileClip(TEST_VIDEO)
    segs = []
    for speed, label in [(1.0, "1× Normal"), (2.0, "2× Fast"), (0.5, "0.5× SlowMo")]:
        seg = clip.subclipped(0, 2.0)
        r = ef.apply_speed(seg, speed)
        named = _label(r, f"Speed — {label}")
        segs.append(named)
    r = concatenate_videoclips(segs)
    path = OUTPUT / "09_speed.mp4"
    print("  09_speed...", end=" ", flush=True)
    named = _label(r, "Speed Ramp")
    named.write_videofile(str(path), fps=30, logger=None)
    clip.close()
    named.close()
    print(f"\033[92m✓\033[0m 09_speed.mp4")


# ── 10. Freeze ────────────────────────────────────────────────
def demo_freeze():
    clip = VideoFileClip(TEST_VIDEO).resized(new_size=(W, H))
    r = ef.apply_freeze(clip, at_time=1.0, duration=1.5)
    render("10_freeze", r, "Freeze Frame", "freeze at 1.0s for 1.5s")
    clip.close()


# ── 11. Overlay / PiP ────────────────────────────────────────
def demo_overlay():
    bg = _gradient(duration=3)
    fg = ImageClip(WIKI_IMG).with_duration(3)
    r = ef.compose_overlay(bg, fg, position="center", scale=0.4)
    render("11_overlay", r, "Overlay / PiP", "center, scale=0.4")


# ── 12. Split Screen ─────────────────────────────────────────
def demo_split():
    a = _gradient(W // 2, H, 3)
    b = ImageClip(WIKI_IMG).with_duration(3).resized(new_size=(W // 2, H))
    r = ef.compose_split([a, b], layout="horizontal", gap=4)
    render("12_split", r, "Split Screen", "horizontal, gap=4px")


# ── 13. Sequential ───────────────────────────────────────────
def demo_sequential():
    clips = []
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    for c in colors:
        clips.append(ColorClip(size=(W, H), color=c).with_duration(1))
    r = ef.compose_sequential(clips, target_duration=4, loop=True)
    render("13_sequential", r, "Sequential + Loop", "3 clips → looped to 4s")


# ── 14. Lower Third ──────────────────────────────────────────
def demo_lower_third():
    bg = _gradient(duration=3)
    lt = ef.create_lower_third(
        "Mona Lisa — Louvre Museum", W, height=100,
        position=("center", "bottom"), opacity=0.75,
    ).with_duration(3)
    r = CompositeVideoClip([bg, lt], size=(W, H))
    render("14_lower_third", r, "Lower Third", 'text="Mona Lisa — Louvre Museum"')


# ── 15. Background ───────────────────────────────────────────
def demo_background():
    segs = []
    for label, clip in [
        ("Solid Black", ef.create_background(W, H, 2, color=(0, 0, 0))),
        ("Solid Gray", ef.create_background(W, H, 2, color=(64, 64, 64))),
        ("Solid Red", ef.create_background(W, H, 2, color=(180, 30, 30))),
    ]:
        named = _label(clip, f"Background — {label}")
        segs.append(named)
    blur_src = _gradient(duration=2)
    blurred = ef.create_background(W, H, 2, blur_source=blur_src)
    named = _label(blurred, "Background — from Blur Source")
    segs.append(named)
    r = concatenate_videoclips(segs)
    render("15_background", r, "Background Types")


# ── Main ─────────────────────────────────────────────────────
def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    demos = [
        demo_fit_resize, demo_fill_resize, demo_ken_burns,
        demo_blur, demo_color_grade, demo_vignette,
        demo_transition, demo_crossfade, demo_speed,
        demo_freeze, demo_overlay, demo_split,
        demo_sequential, demo_lower_third, demo_background,
    ]
    for fn in demos:
        try:
            fn()
        except Exception as e:
            print(f"  \033[91m✗ {fn.__name__}: {e}\033[0m")
    print(f"\nDone! {len(demos)} videos in {OUTPUT}/")


if __name__ == "__main__":
    main()
