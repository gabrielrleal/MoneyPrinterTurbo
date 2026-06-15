"""
Preset: overlay
"""

import os

from loguru import logger
from moviepy import ColorClip, ImageClip, VideoFileClip

from app.models.schema import VideoAspect
from app.services.effects import apply_blur, apply_ken_burns, compose_overlay
from app.services.presets import RenderContext, get_preset
from app.services.video import close_clip, delete_files

name = "overlay"
description = (
    "Sobrepoe a obra de arte do Wikipedia centralizada "
    "sobre o fundo de videos do Pexels"
)


def render(ctx: RenderContext) -> str:
    logger.info(f"preset: {name} — {description}")
    output_dir = os.path.dirname(ctx.combined_video_path)
    aspect = VideoAspect(ctx.video_aspect)
    target_w, target_h = aspect.to_resolution()

    if ctx.video_paths:
        bg_path = os.path.join(output_dir, "overlay-bg.mp4")
        bg_ctx = RenderContext(
            combined_video_path=bg_path,
            video_paths=ctx.video_paths,
            audio_duration=ctx.audio_duration,
            video_aspect=ctx.video_aspect,
            video_concat_mode=ctx.video_concat_mode,
            video_transition_mode=ctx.video_transition_mode,
            max_clip_duration=ctx.max_clip_duration,
            threads=ctx.threads,
        )
        sequential = get_preset("sequential")
        if sequential is None:
            raise RuntimeError("sequential preset not found")
        sequential.render(bg_ctx)
        bg_clip = VideoFileClip(bg_path)
    else:
        bg_clip = ColorClip(size=(target_w, target_h), color=(0, 0, 0)).with_duration(
            ctx.audio_duration
        )

    bg_blurred = apply_blur(bg_clip, radius=30)

    overlay = ImageClip(ctx.wiki_overlay_image).with_duration(ctx.audio_duration)
    overlay = apply_ken_burns(overlay, start_scale=1.0, end_scale=1.08)

    final = compose_overlay(bg_blurred, overlay, position="center", scale=0.8)
    final = final.with_duration(ctx.audio_duration)

    final.write_videofile(
        ctx.combined_video_path,
        fps=30,
        logger=None,
    )

    final.close()
    bg_clip.close()
    if ctx.video_paths:
        delete_files([bg_path])

    return ctx.combined_video_path
