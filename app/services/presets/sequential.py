"""
Preset: sequential
"""

import itertools
import os
import random
import shutil
from typing import List

from loguru import logger
from moviepy import ColorClip, CompositeVideoClip

from app.models.schema import VideoAspect, VideoConcatMode, VideoTransitionMode
from app.services.effects import apply_fit_resize, apply_transition
from app.services.presets import RenderContext
from app.services.video import (
    SubClippedVideoClip,
    _prioritize_unique_source_clips,
    _open_video_clip_quietly,
    _write_videofile_with_codec_fallback,
    _get_configured_video_codec,
    close_clip,
    delete_files,
    concat_video_clips_with_ffmpeg,
    fps,
)

name = "sequential"
description = (
    "Concatena clipes dos videos Pexels sequencialmente "
    "ou aleatoriamente ate' preencher a duracao do audio"
)


def render(ctx: RenderContext) -> str:
    logger.info(f"preset: {name} — {description}")
    logger.info(f"audio duration: {ctx.audio_duration} seconds")
    logger.info(f"maximum clip duration: {ctx.max_clip_duration} seconds")

    transition_value = getattr(ctx.video_transition_mode, "value", ctx.video_transition_mode)
    output_dir = os.path.dirname(ctx.combined_video_path)

    aspect = VideoAspect(ctx.video_aspect)
    video_width, video_height = aspect.to_resolution()

    processed_clips: List[SubClippedVideoClip] = []
    subclipped_items: List[SubClippedVideoClip] = []
    video_duration = 0.0
    for video_path in ctx.video_paths:
        clip = _open_video_clip_quietly(video_path)
        clip_duration = clip.duration
        clip_w, clip_h = clip.size
        close_clip(clip)

        start_time = 0

        while start_time < clip_duration:
            end_time = min(start_time + ctx.max_clip_duration, clip_duration)

            if end_time > start_time:
                subclipped_items.append(
                    SubClippedVideoClip(
                        file_path=video_path,
                        start_time=start_time,
                        end_time=end_time,
                        width=clip_w,
                        height=clip_h,
                        source_file_path=video_path,
                    )
                )

            start_time = end_time
            if ctx.video_concat_mode.value == VideoConcatMode.sequential.value:
                break

    subclipped_items = _prioritize_unique_source_clips(
        subclipped_items=subclipped_items,
        concat_mode=ctx.video_concat_mode,
    )

    logger.debug(f"total subclipped items: {len(subclipped_items)}")

    for i, subclipped_item in enumerate(subclipped_items):
        if video_duration >= ctx.audio_duration:
            break

        logger.debug(
            f"processing clip {i+1}: {subclipped_item.width}x{subclipped_item.height}, "
            f"source: {os.path.basename(subclipped_item.source_file_path)}, "
            f"current duration: {video_duration:.2f}s, "
            f"remaining: {ctx.audio_duration - video_duration:.2f}s"
        )

        try:
            clip = _open_video_clip_quietly(subclipped_item.file_path).subclipped(
                subclipped_item.start_time, subclipped_item.end_time
            )
            clip = apply_fit_resize(clip, video_width, video_height)

            shuffle_side = random.choice(["left", "right", "top", "bottom"])
            clip = apply_transition(
                clip,
                transition_value,
                duration=1,
                side=shuffle_side,
            )

            if clip.duration > ctx.max_clip_duration:
                clip = clip.subclipped(0, ctx.max_clip_duration)

            clip_file = f"{output_dir}/temp-clip-{i+1}.mp4"
            _write_videofile_with_codec_fallback(
                clip,
                clip_file,
                codec=_get_configured_video_codec(),
                logger=None,
                fps=fps,
            )

            clip_duration_saved = clip.duration
            close_clip(clip)

            processed_clips.append(
                SubClippedVideoClip(
                    file_path=clip_file,
                    duration=clip_duration_saved,
                    width=subclipped_item.width,
                    height=subclipped_item.height,
                    source_file_path=subclipped_item.source_file_path,
                )
            )
            video_duration += clip_duration_saved

        except Exception as e:
            logger.error(f"failed to process clip: {str(e)}")

    if video_duration < ctx.audio_duration:
        logger.warning(f"video duration ({video_duration:.2f}s) is shorter than audio duration ({ctx.audio_duration:.2f}s), looping clips to match audio length.")
        base_clips = processed_clips.copy()
        for clip in itertools.cycle(base_clips):
            if video_duration >= ctx.audio_duration:
                break
            processed_clips.append(clip)
            video_duration += clip.duration
        logger.info(f"video duration: {video_duration:.2f}s, audio duration: {ctx.audio_duration:.2f}s, looped {len(processed_clips)-len(base_clips)} clips")

    logger.info("starting clip merging process")
    if not processed_clips:
        logger.warning("no clips available for merging")
        return ctx.combined_video_path

    if len(processed_clips) == 1:
        logger.info("using single clip directly")
        shutil.copy(processed_clips[0].file_path, ctx.combined_video_path)
        delete_files([processed_clips[0].file_path])
        logger.info("video combining completed")
        return ctx.combined_video_path

    clip_files = [clip.file_path for clip in processed_clips]
    logger.info(f"concatenating {len(clip_files)} clips with ffmpeg")
    concat_video_clips_with_ffmpeg(
        clip_files=clip_files,
        output_file=ctx.combined_video_path,
        threads=ctx.threads,
        output_dir=output_dir,
    )

    delete_files(clip_files)

    logger.info("video combining completed")
    return ctx.combined_video_path
