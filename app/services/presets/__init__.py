"""
Sistema de presets de edicao de video.

Cada preset e um modulo dentro de `presets/` que expoe:
  - name: str        -> identificador unico (ex: "sequential", "overlay")
  - description: str -> descricao legivel do que o preset faz
  - render(ctx) -> str  -> funcao principal que gera o video

COMO CRIAR UM NOVO PRESET:
  1. Crie `presets/meu_preset.py`
  2. Defina `name`, `description`, e a funcao `render(ctx)`
  3. `get_preset()` o descobre automaticamente na primeira chamada
"""

import importlib
from dataclasses import dataclass, field
from typing import List, Optional

from loguru import logger

from app.models.schema import VideoAspect, VideoConcatMode, VideoTransitionMode


@dataclass
class RenderContext:
    """Contrato unico entre combine_videos() e qualquer preset.

    Todo preset recebe este objeto e deve escrever o video final
    em `combined_video_path`.
    """
    combined_video_path: str
    video_paths: List[str]
    audio_duration: float
    audio_file: Optional[str] = None
    wiki_overlay_image: Optional[str] = None
    video_aspect: VideoAspect = VideoAspect.portrait
    video_concat_mode: VideoConcatMode = VideoConcatMode.random
    video_transition_mode: Optional[VideoTransitionMode] = None
    max_clip_duration: int = 5
    threads: int = 2


class _PresetModule:
    """Wrapper para um modulo preset descoberto automaticamente."""

    def __init__(self, module):
        self.name: str = module.name
        self.description: str = getattr(module, "description", "")
        self.render = module.render


_registry: dict[str, _PresetModule] = {}


def get_preset(name: str) -> _PresetModule | None:
    """Retorna o preset pelo nome.

    Importa o modulo sob demanda (lazy) na primeira chamada.
    Isso evita circular imports: video.py importa este modulo,
    e os presets importam de video.py.
    """
    if name in _registry:
        return _registry[name]
    try:
        module = importlib.import_module(
            f"app.services.presets.{name}"
        )
        if not hasattr(module, "name") or not hasattr(module, "render"):
            logger.warning(
                f"preset module '{name}' ignored: missing 'name' or 'render()'"
            )
            return None
        _registry[name] = _PresetModule(module)
        logger.info(f"preset loaded: {module.name}")
        return _registry[name]
    except ImportError:
        logger.warning(f"preset '{name}' not found")
        return None


def list_presets() -> list[_PresetModule]:
    """Retorna todos os presets carregados."""
    return list(_registry.values())
