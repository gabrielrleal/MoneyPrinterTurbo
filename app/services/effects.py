"""
effects.py — Biblioteca de operacoes atomicas MoviePy.

Cada funcao recebe clip(s) + parametros, retorna clip transformado.
Sem side effects, sem I/O de arquivo, sem dependencia de config/models.
Componiveis — qualquer preset pode importar e combinar livremente.
"""

from moviepy import (
    ColorClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
    VideoClip,
    concatenate_videoclips,
    vfx,
)


def apply_fit_resize(
    clip: VideoClip, target_w: int, target_h: int
) -> VideoClip:
    cw, ch = clip.size
    if cw == target_w and ch == target_h:
        return clip

    ratio_clip = cw / ch
    ratio_target = target_w / target_h

    if ratio_clip == ratio_target:
        return clip.resized(new_size=(target_w, target_h))

    scale = min(target_w / cw, target_h / ch)
    new_w, new_h = int(cw * scale), int(ch * scale)

    bg = ColorClip(size=(target_w, target_h), color=(0, 0, 0)).with_duration(
        clip.duration
    )
    fg = clip.resized(new_size=(new_w, new_h)).with_position("center")
    return CompositeVideoClip([bg, fg], size=(target_w, target_h))


def apply_fill_resize(
    clip: VideoClip, target_w: int, target_h: int
) -> CompositeVideoClip:
    cw, ch = clip.size
    if cw == target_w and ch == target_h:
        return clip

    scale = max(target_w / cw, target_h / ch)
    new_w, new_h = int(cw * scale), int(ch * scale)
    resized = clip.resized(new_size=(new_w, new_h))

    x_off = (target_w - new_w) / 2
    y_off = (target_h - new_h) / 2

    bg = ColorClip(size=(target_w, target_h), color=(0, 0, 0)).with_duration(
        clip.duration
    )
    positioned = resized.with_position((x_off, y_off))
    return CompositeVideoClip([bg, positioned], size=(target_w, target_h))


def apply_ken_burns(
    clip: VideoClip,
    start_scale: float = 1.0,
    end_scale: float = 1.08,
) -> VideoClip:
    dur = clip.duration
    cw, ch = clip.size

    def zoom_at(t: float):
        progress = t / dur if dur > 0 else 0
        s = start_scale + (end_scale - start_scale) * progress
        return int(cw * s), int(ch * s)

    def pos_at(t: float):
        progress = t / dur if dur > 0 else 0
        s = start_scale + (end_scale - start_scale) * progress
        ox = cw * (1 - s) / 2
        oy = ch * (1 - s) / 2
        return ox, oy

    return clip.resized(new_size=zoom_at).with_position(pos_at)


def apply_blur(clip: VideoClip, radius: float = 30.0) -> VideoClip:
    import numpy as np
    from PIL import Image, ImageFilter

    def blur_frame(get_frame, t):
        frame = get_frame(t)
        frame_uint8 = frame.astype(np.uint8) if frame.dtype != np.uint8 else frame
        img = Image.fromarray(frame_uint8)
        blurred = img.filter(ImageFilter.GaussianBlur(radius=radius))
        return np.array(blurred).astype(frame.dtype)

    return clip.transform(blur_frame)


def apply_transition(
    clip: VideoClip,
    mode: str | None,
    duration: float = 1.0,
    side: str = "left",
) -> VideoClip:
    if mode is None or mode == "none":
        return clip

    m = mode.lower().replace("_", "")

    if m in ("fadein",):
        return clip.with_effects([vfx.FadeIn(duration)])
    if m in ("fadeout",):
        return clip.with_effects([vfx.FadeOut(duration)])

    if any(d in m for d in ("slide",)):
        return _apply_slide(clip, mode, duration, side)

    if m == "shuffle":
        return _apply_shuffle_transition(clip, duration, side)

    return clip


def _apply_slide(
    clip: VideoClip, mode: str, duration: float, side: str
) -> CompositeVideoClip:
    w, h = clip.size
    m = mode.lower().replace("_", "")
    is_out = "out" in m

    resolved_side = side
    for s in ("left", "right", "top", "bottom"):
        if s in m:
            resolved_side = s
            break

    transition_start = max(clip.duration - duration, 0) if is_out else 0

    def pos(t: float):
        if is_out and t <= transition_start:
            return 0, 0

        elapsed = t - transition_start if is_out else t
        progress = min(elapsed / max(duration, 0.001), 1)

        if resolved_side in ("left", "right"):
            sign = -1 if resolved_side == "left" else 1
            offset = sign * (w * (1 - progress) if not is_out else w * progress)
            return offset, 0
        else:
            sign = -1 if resolved_side == "top" else 1
            offset = sign * (h * (1 - progress) if not is_out else h * progress)
            return 0, offset

    bg = ColorClip(size=(w, h), color=(0, 0, 0)).with_duration(clip.duration)
    moving = clip.with_position(pos)
    return CompositeVideoClip([bg, moving], size=(w, h)).with_duration(clip.duration)


def _apply_shuffle_transition(
    clip: VideoClip, duration: float, side: str
) -> VideoClip:
    import random

    funcs = [
        lambda c: c.with_effects([vfx.FadeIn(duration)]),
        lambda c: c.with_effects([vfx.FadeOut(duration)]),
        lambda c: _apply_slide(c, "slide_in", duration, random.choice(["left", "right", "top", "bottom"])),
        lambda c: _apply_slide(c, "slide_out", duration, random.choice(["left", "right", "top", "bottom"])),
    ]
    return random.choice(funcs)(clip)


def compose_sequential(
    clips: list[VideoClip],
    target_duration: float | None = None,
    loop: bool = True,
) -> VideoClip:
    if not clips:
        raise ValueError("compose_sequential: clips list is empty")

    total = sum(c.duration for c in clips)
    if loop and target_duration and total < target_duration:
        n_loops = int(target_duration / total) + 1
        clips = clips * n_loops

    result = concatenate_videoclips(clips)
    if target_duration:
        result = result.subclipped(0, target_duration)
    return result


def compose_overlay(
    bg: VideoClip,
    fg: VideoClip,
    position: str | tuple = "center",
    scale: float = 0.8,
) -> CompositeVideoClip:
    bw, bh = bg.size
    fg_resized = fg.resized(
        new_size=(int(bw * scale), int(bh * scale))
    )
    fg_positioned = fg_resized.with_position(position).with_duration(bg.duration)
    return CompositeVideoClip([bg, fg_positioned], size=(bw, bh))


def compose_split(
    clips: list[VideoClip],
    layout: str = "horizontal",
    gap: int = 4,
) -> CompositeVideoClip:
    if len(clips) != 2:
        raise ValueError("compose_split requires exactly 2 clips")

    a, b = clips
    if layout == "horizontal":
        w = int(a.w + b.w + gap)
        h = max(a.h, b.h)
        b = b.with_position((int(a.w + gap), 0))
    else:
        w = max(a.w, b.w)
        h = int(a.h + b.h + gap)
        b = b.with_position((0, int(a.h + gap)))

    bg = ColorClip(size=(w, h), color=(0, 0, 0)).with_duration(
        max(a.duration, b.duration)
    )
    return CompositeVideoClip([bg, a, b], size=(w, h))


def apply_crossfade(
    clip_a: VideoClip,
    clip_b: VideoClip,
    duration: float = 1.0,
) -> CompositeVideoClip:
    overlap = min(duration, clip_a.duration, clip_b.duration)
    a = clip_a.with_effects([vfx.FadeOut(overlap)])
    b = (
        clip_b.with_start(clip_a.duration - overlap)
        .with_effects([vfx.FadeIn(overlap)])
    )
    total_dur = clip_a.duration + clip_b.duration - overlap
    size = (max(int(clip_a.w), int(clip_b.w)), max(int(clip_a.h), int(clip_b.h)))
    bg = ColorClip(size=size, color=(0, 0, 0)).with_duration(total_dur)
    return CompositeVideoClip([bg, a, b], size=size)


def apply_speed(clip: VideoClip, speed: float = 2.0) -> VideoClip:
    if speed == 1.0:
        return clip
    return clip.with_effects([vfx.MultiplySpeed(speed)])


def apply_color_grade(clip: VideoClip, preset: str = "none") -> VideoClip:
    if preset == "none":
        return clip

    import numpy as np

    def grade_frame(get_frame, t):
        frame = get_frame(t).astype(np.float32)
        if preset == "bw":
            gray = np.dot(frame[..., :3], [0.2989, 0.5870, 0.1140])
            result = np.stack([gray, gray, gray], axis=-1)
        elif preset == "vintage":
            result = frame.copy()
            result[..., 0] *= 1.08
            result[..., 1] *= 0.92
            result[..., 2] *= 0.85
        elif preset == "cinema":
            result = frame.copy()
            result[..., 0] *= 0.85
            result[..., 2] *= 1.15
            result = result * 0.85 + 15
        elif preset == "warm":
            result = frame.copy()
            result[..., 0] *= 1.06
            result[..., 2] *= 0.82
        elif preset == "cool":
            result = frame.copy()
            result[..., 0] *= 0.82
            result[..., 2] *= 1.18
        else:
            result = frame
        return np.clip(result, 0, 255).astype(np.uint8)

    return clip.transform(grade_frame)


def apply_vignette(
    clip: VideoClip, radius: float = 0.5, intensity: float = 0.3
) -> VideoClip:
    if intensity <= 0:
        return clip

    import numpy as np

    w, h = clip.size
    X, Y = np.meshgrid(np.linspace(-1, 1, w), np.linspace(-1, 1, h))
    dist = np.sqrt(X**2 + Y**2)
    mask = np.clip(1 - (dist - radius) / max(1 - radius, 0.001) * intensity, 0, 1)

    def apply(get_frame, t):
        frame = get_frame(t).astype(np.float32)
        for i in range(3):
            frame[:, :, i] *= mask
        return np.clip(frame, 0, 255).astype(np.uint8)

    return clip.transform(apply)


def apply_freeze(
    clip: VideoClip, at_time: float | None = None, duration: float = 2.0
) -> VideoClip:
    freeze_at = at_time if at_time is not None else clip.duration
    freeze_at = min(freeze_at, clip.duration)

    frozen_frame = clip.get_frame(freeze_at)
    frozen = ImageClip(frozen_frame, transparent=False).with_duration(duration)

    parts = []
    if freeze_at > 0:
        parts.append(clip.subclipped(0, freeze_at))
    parts.append(frozen)
    if freeze_at < clip.duration:
        parts.append(clip.subclipped(freeze_at, clip.duration))

    if len(parts) == 1:
        return parts[0]
    return concatenate_videoclips(parts)


def _hex_to_rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def create_lower_third(
    text: str,
    width: int,
    height: int = 80,
    position: str | tuple = ("center", "bottom"),
    color: str = "#ffffff",
    bg_color: str = "#000000",
    opacity: float = 0.7,
) -> VideoClip:
    bar = ColorClip(
        size=(width, height), color=_hex_to_rgb(bg_color)
    ).with_opacity(opacity)
    txt = TextClip(
        text=text,
        font_size=int(height * 0.45),
        color=color,
        font="Arial",
        text_align="center",
        size=(width - 40, height),
    ).with_position("center")
    return CompositeVideoClip([bar, txt], size=(width, height)).with_position(
        position
    )


def create_background(
    w: int,
    h: int,
    duration: float,
    color: tuple = (0, 0, 0),
    blur_source: VideoClip | None = None,
) -> VideoClip:
    if blur_source:
        return apply_fit_resize(apply_blur(blur_source, 30), w, h).with_duration(
            duration
        )
    return ColorClip(size=(w, h), color=color).with_duration(duration)
