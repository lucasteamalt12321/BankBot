"""MIDI-утилиты: темп (BPM), тональность, транспозиция, смена темпа, наложение.

Реализация поверх библиотеки `mido` (чистый Python, без тяжёлых зависимостей).
Все функции работают с файлами .mid / .midi.
"""
from __future__ import annotations

import os
from typing import List, Optional, Tuple

try:
    import mido
    from mido import MidiFile, MidiTrack, MetaMessage
    _MIDO = True
except Exception:  # pragma: no cover - зависит от окружения
    _MIDO = False


_MAX_MIDI_SIZE = 10 * 1024 * 1024  # 10 МБ


def _require() -> None:
    if not _MIDO:
        raise RuntimeError("Для работы с MIDI нужна библиотека `mido` (pip install mido)")


def _check_midi_size(path: str) -> None:
    size = os.path.getsize(path)
    if size > _MAX_MIDI_SIZE:
        raise ValueError(f"MIDI-файл слишком большой ({size // 1024} КБ > 10 МБ) — возможен таймаут парсинга.")


_KEY_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def _suffixed(path: str, tag: str) -> str:
    root, ext = os.path.splitext(path)
    return root + tag + (ext or '.mid')


def midi_tempo_changes(path: str) -> List[Tuple[float, int]]:
    """Возвращает список (bpm, tick) по всем событиям set_tempo."""
    _require()
    _check_midi_size(path)
    mf = MidiFile(path)
    out: List[Tuple[float, int]] = []
    for track in mf.tracks:
        for msg in track:
            if msg.type == 'set_tempo':
                out.append((round(60000000 / msg.tempo, 3), msg.time))
    if not out:
        out.append((120.0, 0))
    return out


def detect_bpm(path: str) -> float:
    """Первый (или единственный) темп в MIDI, BPM."""
    return midi_tempo_changes(path)[0][0]


def midi_key_signatures(path: str) -> List[str]:
    """Возвращает список меток key_signature (напр. 'C', 'Am')."""
    _require()
    _check_midi_size(path)
    mf = MidiFile(path)
    return [msg.key for track in mf.tracks for msg in track if msg.type == 'key_signature']


def detect_key(path: str) -> Optional[str]:
    """Первая тональность MIDI (напр. 'Am'); None, если не задана."""
    keys = midi_key_signatures(path)
    return keys[0] if keys else None


def change_key(path: str, semitones: int, out: Optional[str] = None,
               target_key: Optional[str] = None) -> str:
    """Транспонирует все ноты (изменение тональности).

    semitones — сдвиг в полутонах. Если задан target_key, сдвиг считается
    относительно текущей тональности файла.
    """
    _require()
    _check_midi_size(path)
    if target_key is not None:
        semitones = _key_shift(target_key, detect_key(path))
    if out is None:
        out = _suffixed(path, f"_transp{semitones}")
    mf = MidiFile(path)
    for track in mf.tracks:
        for msg in track:
            if msg.type in ('note_on', 'note_off') and msg.note is not None:
                msg.note = int(_clamp(msg.note + semitones, 0, 127))
    mf.save(out)
    return out


def change_tempo(path: str, target_bpm: Optional[float] = None,
                 factor: Optional[float] = None, out: Optional[str] = None) -> str:
    """Меняет темп MIDI.

    target_bpm — заменяет все set_tempo на заданный BPM.
    factor — масштабирует длительности нот (factor>1 быстрее), темпы не трогает.
    """
    _require()
    _check_midi_size(path)
    if target_bpm is None and factor is None:
        raise ValueError("нужен target_bpm или factor")
    tag = f"_bpm{target_bpm}" if target_bpm is not None else f"_x{factor}"
    if out is None:
        out = _suffixed(path, tag)
    mf = MidiFile(path)
    if target_bpm is not None:
        new_tempo = int(round(60000000 / target_bpm))
        for track in mf.tracks:
            for msg in track:
                if msg.type == 'set_tempo':
                    msg.tempo = new_tempo
        if not any(msg.type == 'set_tempo' for track in mf.tracks for msg in track):
            mf.tracks[0].insert(0, MetaMessage('set_tempo', tempo=new_tempo, time=0))
    if factor is not None:
        f = float(factor)
        for track in mf.tracks:
            for msg in track:
                msg.time = int(round(msg.time * f))
    mf.save(out)
    return out


def overlay(paths: List[str], out: Optional[str] = None) -> str:
    """Накладывает несколько MIDI: все дорожки играются одновременно.

    Разные ticks_per_beat приводятся к базе первого файла.
    """
    _require()
    if not paths:
        raise ValueError("нужен хотя бы один файл")
    for p in paths:
        _check_midi_size(p)
    if out is None:
        out = _suffixed(paths[0], "_mixed")
    base = MidiFile(paths[0])
    result = MidiFile(ticks_per_beat=base.ticks_per_beat)
    for p in paths:
        mf = MidiFile(p)
        scale = base.ticks_per_beat / mf.ticks_per_beat if mf.ticks_per_beat != base.ticks_per_beat else 1.0
        for track in mf.tracks:
            nt = MidiTrack()
            for msg in track:
                cp = msg.copy()
                if scale != 1.0:
                    cp.time = int(round(cp.time * scale))
                nt.append(cp)
            result.tracks.append(nt)
    result.save(out)
    return out


def _key_shift(target_key: str, current_key: Optional[str]) -> int:
    """Сдвиг в полутонах от current_key к target_key (относительно C, если текущей нет)."""
    t_idx = _parse_key(target_key)
    c_idx = _parse_key(current_key) if current_key else 0
    return (t_idx - c_idx) % 12


def _parse_key(name: str) -> int:
    """Возвращает индекс тоники (0=C .. 11=B) из строки 'C', 'C#', 'Am', 'F#m' и т.п."""
    s = name.strip()
    minor = s.endswith(('m', 'min', 'minor')) and not s.endswith('maj')
    if minor:
        s = s.rstrip('m').rstrip('inor').rstrip(' ')
    base_map = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
    letter = s[0].upper()
    acc = s[1] if len(s) > 1 and s[1] in '#b' else ''
    idx = base_map[letter]
    if acc == '#':
        idx += 1
    elif acc == 'b':
        idx -= 1
    return idx % 12
