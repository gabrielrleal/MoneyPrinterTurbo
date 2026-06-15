"""
Preset: gallery
"""

from loguru import logger
from moviepy import ImageClip

from app.models.schema import VideoAspect
from app.services.effects import (
    apply_crossfade,
    apply_fit_resize,
    apply_ken_burns,
    compose_sequential,
)
from app.services.preset_engine import load_params
from app.services.presets import RenderContext
from app.services.video import _open_video_clip_quietly, close_clip

name = "gallery"
description = (
    "Wiki artwork with Ken Burns first, "
    "then crossfade to Pexels videos"
)


def render(ctx: RenderContext) -> str:
    logger.info(f"preset: {name} — {description}")
    params = load_params(name)
    aspect = VideoAspect(ctx.video_aspect)
    w, h = aspect.to_resolution()

    wiki_duration = params.get("wiki_duration", 4.0)
    fade_duration = params.get("fade_duration", 1.0)

    wiki = ImageClip(ctx.wiki_overlay_image).with_duration(wiki_duration)
    wiki = apply_fit_resize(wiki, w, h)
    wiki = apply_ken_burns(
        wiki,
        start_scale=params.get("ken_burns_start", 1.0),
        end_scale=params.get("ken_burns_end", 1.08),
    )

    remaining = max(0.1, ctx.audio_duration - wiki_duration + fade_duration)
    pexels_clips = []
    for vp in ctx.video_paths:
        clip = _open_video_clip_quietly(vp)
        pexels_clips.append(apply_fit_resize(clip, w, h))
        close_clip(clip)
    pexels = compose_sequential(
        pexels_clips, target_duration=remaining, loop=True
    )

    final = apply_crossfade(wiki, pexels, duration=fade_duration)
    if final.duration > ctx.audio_duration:
        final = final.subclipped(0, ctx.audio_duration)
    final.write_videofile(ctx.combined_video_path, fps=30, logger=None)
    final.close()
    return ctx.combined_video_path
