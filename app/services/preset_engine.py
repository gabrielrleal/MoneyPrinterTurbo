"""
preset_engine.py — Descoberta e carregamento de presets via TOML.

Cada arquivo .toml em resource/presets/ define um preset disponivel.
O campo "engine" mapeia para o modulo Python em app/services/presets/.
"""

import tomllib
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent.parent
PRESETS_DIR = ROOT / "resource" / "presets"

_registry: Dict[str, Dict[str, Any]] = {}


def _discover():
    if not PRESETS_DIR.is_dir():
        return
    for f in sorted(PRESETS_DIR.glob("*.toml")):
        try:
            data = tomllib.loads(f.read_text(encoding="utf-8"))
            engine = data.get("engine", "")
            if engine:
                _registry[engine] = data
        except Exception:
            continue


def list_presets() -> List[Dict[str, Any]]:
    if not _registry:
        _discover()
    return [
        {
            "name": data.get("name", engine),
            "engine": engine,
            "description": data.get("description", ""),
        }
        for engine, data in _registry.items()
    ]


def load_params(engine_name: str) -> Dict[str, Any]:
    if not _registry:
        _discover()
    data = _registry.get(engine_name, {})
    return data.get("params", {})
