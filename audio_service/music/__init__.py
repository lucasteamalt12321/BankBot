"""Модуль «Музыка»: измерение и изменение тональности и темпа (BPM), наложение аудио.

Поддерживаются форматы:
- MIDI (.mid / .midi) — поверх core.music.midi_utils (библиотека `mido`);
- аудио (MP3 / WAV) — поверх core.music.audio_utils (librosa + soundfile + pydub).

Диспетчеризация по расширению файла. Публичный API:

- analyze(path) -> {format, bpm, key}
- detect_bpm(path) -> float
- detect_key(path) -> str | None
- change_tempo(path, target_bpm=None, factor=None, out=None) -> str   (путь к результату)
- change_key(path, semitones=None, target_key=None, out=None) -> str
- overlay(paths, out=None) -> str
"""
from __future__ import annotations

import os
from typing import List, Optional

from . import audio_utils, midi_utils

_MIDI_EXT = {'.mid', '.midi'}


def _is_midi(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in _MIDI_EXT


def analyze(path: str) -> dict:
    """Сводная информация о файле: формат, темп, тональность."""
    if _is_midi(path):
        return {
            "format": "midi",
            "bpm": midi_utils.detect_bpm(path),
            "key": midi_utils.detect_key(path),
        }
    return audio_utils.analyze_audio(path)


def detect_bpm(path: str):
    return midi_utils.detect_bpm(path) if _is_midi(path) else audio_utils.detect_bpm(path)


def detect_key(path: str):
    return midi_utils.detect_key(path) if _is_midi(path) else audio_utils.detect_key(path)


def change_tempo(path: str, target_bpm: Optional[float] = None,
                 factor: Optional[float] = None, out: Optional[str] = None) -> str:
    if _is_midi(path):
        return midi_utils.change_tempo(path, target_bpm=target_bpm, factor=factor, out=out)
    return audio_utils.change_tempo(path, target_bpm=target_bpm, factor=factor, out=out)


def change_key(path: str, semitones: Optional[int] = None,
               target_key: Optional[str] = None, out: Optional[str] = None) -> str:
    if _is_midi(path):
        return midi_utils.change_key(path, semitones=semitones, target_key=target_key, out=out)
    return audio_utils.change_key(path, semitones=semitones, target_key=target_key, out=out)


def overlay(paths: List[str], out: Optional[str] = None) -> str:
    if paths and all(_is_midi(p) for p in paths):
        return midi_utils.overlay(paths, out=out)
    return audio_utils.overlay(paths, out=out)


__all__ = [
    "analyze", "detect_bpm", "detect_key", "change_tempo", "change_key", "overlay",
    "midi_utils", "audio_utils",
]
