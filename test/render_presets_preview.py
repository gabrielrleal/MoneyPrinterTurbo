"""
Render preset preview videos for visual inspection.

Uses existing test resources (test/resources/1.png.mp4, 2.png, etc.)
to generate sample output from each preset + an effects showcase.

Usage:
    python test/render_presets_preview.py

Output: test/preview_output/*.mp4  — open these in any video player.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from moviepy import (
    CompositeVideoClip,
    TextClip,
    VideoFileClip,
    concatenate_videoclips,
)

from app.models.schema import VideoAspect, VideoConcatMode, VideoTransitionMode
from app.services.presets import RenderContext, get_preset
from app.services import effects as ef

RESOURCES = Path(__file__).parent / "resources"
OUTPUT = Path(__file__).parent / "preview_output"
FONT = "Arial"


def _label_clip(clip, text: str, font_size=48, y=50):
    txt = TextClip(
        text=text,
        font=FONT,
        font_size=font_size,
        color="white",
        stroke_color="black",
        stroke_width=2,
    ).with_position(("center", y)).with_duration(clip.duration)
    return CompositeVideoClip([clip, txt], size=clip.size)


def render_preset(engine: str, label: str, ctx: RenderContext):
    path = OUTPUT / f"{label}.mp4"
    ctx.combined_video_path = str(path)
    print(f"  Rendering {label} ({engine})...", end=" ", flush=True)
    try:
        preset = get_preset(engine)
        if preset:
            preset.render(ctx)
            print(f"\033[92m✓\033[0m {path.name}")
        else:
            print(f"\033[91m✗ preset '{engine}' not found\033[0m")
    except Exception as e:
        print(f"\033[91m✗ {e}\033[0m")


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)

    test_video = str(RESOURCES / "1.png.mp4")
    wiki_image = str(RESOURCES / "2.png")
    video_paths = [test_video] * 5

    # ── Preset renders ────────────────────────────────────────
    def _ctx(**kw):
        return RenderContext(combined_video_path="", **kw)

    presets = [
        ("sequential", "00_sequential", _ctx(
            video_paths=video_paths,
            audio_duration=5.0,
            video_aspect=VideoAspect.portrait,
            video_concat_mode=VideoConcatMode.random,
            video_transition_mode=VideoTransitionMode.shuffle,
            max_clip_duration=3,
            threads=2,
        )),
        ("overlay", "01_overlay", _ctx(
            video_paths=video_paths,
            audio_duration=5.0,
            wiki_overlay_image=wiki_image,
            video_aspect=VideoAspect.portrait,
            video_concat_mode=VideoConcatMode.random,
            max_clip_duration=3,
            threads=2,
        )),
        ("gallery", "02_gallery", _ctx(
            video_paths=video_paths,
            audio_duration=6.0,
            wiki_overlay_image=wiki_image,
            video_aspect=VideoAspect.portrait,
            video_concat_mode=VideoConcatMode.random,
            max_clip_duration=3,
            threads=2,
        )),
        ("split_screen", "03_split_screen", _ctx(
            video_paths=video_paths,
            audio_duration=5.0,
            wiki_overlay_image=wiki_image,
            video_aspect=VideoAspect.portrait,
            video_concat_mode=VideoConcatMode.random,
            max_clip_duration=3,
            threads=2,
        )),
    ]

    for engine, label, ctx in presets:
        render_preset(engine, label, ctx)

    # ── Effects showcase ──────────────────────────────────────
    print("  Rendering 04_effects_showcase...", end=" ", flush=True)
    try:
        base = VideoFileClip(test_video)
        w, h = base.size

        effects = [
            ("Original", lambda c: c),
            ("Speed 2x", lambda c: ef.apply_speed(c, 2.0)),
            ("Vintage", lambda c: ef.apply_color_grade(c, "vintage")),
            ("Cinema", lambda c: ef.apply_color_grade(c, "cinema")),
            ("Vignette", lambda c: ef.apply_vignette(c, radius=0.4, intensity=0.5)),
            ("Freeze Frame", lambda c: ef.apply_freeze(c, at_time=1.0, duration=1.5)),
        ]

        segments = []
        for name, fn in effects:
            seg_dur = 2.0
            clip = base.subclipped(0, seg_dur)
            processed = fn(clip)
            labeled = _label_clip(processed, name)
            segments.append(labeled)

        final = concatenate_videoclips(segments)
        final.write_videofile(str(OUTPUT / "04_effects_showcase.mp4"), fps=30, logger=None)
        final.close()
        base.close()
        print(f"\033[92m✓\033[0m 04_effects_showcase.mp4")
    except Exception as e:
        print(f"\033[91m✗ {e}\033[0m")

    print(f"\nDone! Open {OUTPUT}/ to view results.")


if __name__ == "__main__":
    main()
