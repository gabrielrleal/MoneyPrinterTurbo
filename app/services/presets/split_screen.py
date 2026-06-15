"""
Preset: split_screen
"""

from loguru import logger
from moviepy import ImageClip

from app.models.schema import VideoAspect
from app.services.effects import (
    apply_fill_resize,
    apply_fit_resize,
    compose_sequential,
    compose_split,
)
from app.services.preset_engine import load_params
from app.services.presets import RenderContext
from app.services.video import _open_video_clip_quietly, close_clip

name = "split_screen"
description = (
    "Wiki artwork and Pexels videos side by side"
)


def render(ctx: RenderContext) -> str:
    logger.info(f"preset: {name} — {description}")
    params = load_params(name)
    aspect = VideoAspect(ctx.video_aspect)
    w, h = aspect.to_resolution()

    gap = params.get("gap", 4)
    half_w = (w - gap) // 2

    wiki = ImageClip(ctx.wiki_overlay_image).with_duration(ctx.audio_duration)
    wiki = apply_fit_resize(wiki, half_w, h)

    clips = []
    for vp in ctx.video_paths:
        clip = _open_video_clip_quietly(vp)
        clips.append(apply_fill_resize(clip, half_w, h))
        close_clip(clip)
    pexels = compose_sequential(
        clips, target_duration=ctx.audio_duration, loop=True
    )

    final = compose_split([wiki, pexels], layout="horizontal", gap=gap)
    final = final.with_duration(ctx.audio_duration)
    final.write_videofile(ctx.combined_video_path, fps=30, logger=None)
    final.close()
    return ctx.combined_video_path
