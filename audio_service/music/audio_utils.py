"""Аудио-утилиты (MP3/WAV): BPM, тональность, темп, высота, наложение.

Анализ и синтез поверх `librosa` + `soundfile`; конвертация в MP3 поверх `pydub`
(требует системный ffmpeg). Все зависимости импортируются лениво — при их
отсутствии функции выбрасывают понятное сообщение.
"""
from __future__ import annotations

import os
import re
from typing import List, Optional

import numpy as np

try:
    import librosa
    import soundfile as sf
    _LIBROSA = True
except Exception:  # pragma: no cover - зависит от окружения
    _LIBROSA = False


_KEY_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# Профили Крумхансля–Шмуклера для определения тональности по хромаграмме.
_MAJOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_MINOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]


def _require() -> None:
    if not _LIBROSA:
        raise RuntimeError("Для аудио нужны librosa+soundfile (pip install librosa soundfile)")


def _load(path: str, sr: int = 22050, duration: float = 30.0):
    """Загрузка аудио с ограничением длительности (анализ не нуждается в целом треке)."""
    _require()
    return librosa.load(path, sr=sr, mono=True, duration=duration)


def detect_bpm(path: str, sr: int = 22050, duration: float = 30.0) -> float:
    """Оценивает темп композиции, BPM."""
    y, sr = _load(path, sr=sr, duration=duration)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    return float(np.asarray(tempo).reshape(-1)[0])


def detect_key(path: str, sr: int = 22050, duration: float = 30.0) -> str:
    """Оценивает тональность (напр. 'C major' / 'A minor') по хромаграмме."""
    y, sr = _load(path, sr=sr, duration=duration)
    return _key_from_y(y, sr)


def _key_from_y(y, sr: int) -> str:
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    mean = chroma.mean(axis=1)
    s = mean.sum() + 1e-9
    mean = mean / s
    best = None
    for i in range(12):
        maj = sum(mean[k] * _MAJOR[(k - i) % 12] for k in range(12))
        minr = sum(mean[k] * _MINOR[(k - i) % 12] for k in range(12))
        if best is None or maj > best[0]:
            best = (maj, i, 'major')
        if minr > best[0]:
            best = (minr, i, 'minor')
    return f"{_KEY_NAMES[best[1]]} {best[2]}"


def analyze_audio(path: str, sr: int = 16000, duration: float = 20.0) -> dict:
    """Быстрый анализ аудио: загружает трек один раз (срез по длительности)."""
    y, sr = _load(path, sr=sr, duration=duration)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(np.asarray(tempo).reshape(-1)[0])
    key = _key_from_y(y, sr)
    return {"format": "audio", "bpm": bpm, "key": key}


def change_tempo(path: str, target_bpm: Optional[float] = None,
                 factor: Optional[float] = None, out: Optional[str] = None,
                 sr: int = 22050) -> str:
    """Меняет темп без изменения высоты тона.

    target_bpm — целевой BPM (считается относительно измеренного).
    factor — множитель скорости (>1 быстрее). Результат в том же формате, что и вход.
    """
    _require()
    if target_bpm is None and factor is None:
        raise ValueError("нужен target_bpm или factor")
    y, sr = librosa.load(path, sr=sr, mono=True)
    if factor is None:
        factor = target_bpm / detect_bpm(path, sr=sr)
    y2 = librosa.effects.time_stretch(y, rate=float(factor))
    return _save(y2, sr, out, path, f"_x{factor:.3f}")


def change_key(path: str, semitones: Optional[int] = None,
               target_key: Optional[str] = None, out: Optional[str] = None,
               sr: int = 22050) -> str:
    """Меняет высоту тона (тональность) без изменения темпа.

    semitones — сдвиг в полутонах. target_key — целевая тональность
    (сдвиг считается относительно текущей).
    """
    _require()
    if semitones is None and target_key is not None:
        semitones = _key_shift(target_key, detect_key(path, sr=sr))
    if semitones is None:
        raise ValueError("нужен semitones или target_key")
    y, sr = librosa.load(path, sr=sr, mono=True)
    y2 = librosa.effects.pitch_shift(y, sr=sr, n_steps=float(semitones))
    return _save(y2, sr, out, path, f"_transp{semitones}")


def overlay(paths: List[str], out: Optional[str] = None, mix: float = 0.8,
            sr: int = 22050) -> str:
    """Накладывает несколько аудиофайлов: суммирует сигналы и нормирует.

    mix — итоговая громкость (0..1). Результат в формате первого файла.
    """
    _require()
    import numpy as np
    sigs = []
    maxlen = 0
    for p in paths:
        y, _ = librosa.load(p, sr=sr, mono=True)
        sigs.append(y)
        maxlen = max(maxlen, len(y))
    mixed = np.zeros(maxlen, dtype=np.float32)
    for y in sigs:
        padded = np.pad(y, (0, maxlen - len(y)))
        mixed += padded
    mixed = mixed / max(1, len(sigs)) * mix
    peak = float(np.max(np.abs(mixed))) + 1e-9
    mixed = (mixed / peak * 0.95).astype(np.float32)
    return _save(mixed, sr, out, paths[0], "_mixed")


def _save(y, sr: int, out: Optional[str], src: str, tag: str) -> str:
    if out is None:
        root, ext = os.path.splitext(src)
        out = root + tag + (ext or '.wav')
    fmt = 'MP3' if out.lower().endswith('.mp3') else None
    sf.write(out, y, sr, format=fmt)
    return out


def normalize(path: str, peak: float = 0.95, out: Optional[str] = None,
              sr: int = 22050) -> str:
    """Нормализует громкость к заданному пику (0..1)."""
    _require()
    y, sr = librosa.load(path, sr=sr, mono=True)
    y = y / (float(np.max(np.abs(y))) + 1e-9) * peak
    return _save(y.astype(np.float32), sr, out, path, "_norm")


def reverse(path: str, out: Optional[str] = None, sr: int = 22050) -> str:
    """Разворачивает аудио задом наперёд."""
    _require()
    y, sr = librosa.load(path, sr=sr, mono=True)
    return _save(y[::-1].astype(np.float32), sr, out, path, "_rev")


def echo(path: str, delay: float = 0.25, decay: float = 0.4,
         out: Optional[str] = None, sr: int = 22050) -> str:
    """Добавляет эхо (задержка в секундах + коэффициент затухания)."""
    _require()
    y, sr = librosa.load(path, sr=sr, mono=True)
    d = max(1, int(sr * float(delay)))
    out_sig = np.zeros(len(y) + d, dtype=np.float32)
    out_sig[:len(y)] += y
    out_sig[d:] += (y * float(decay)).astype(np.float32)
    peak = float(np.max(np.abs(out_sig))) + 1e-9
    out_sig = (out_sig / peak * 0.95).astype(np.float32)
    return _save(out_sig, sr, out, path, "_echo")


def trim(path: str, start: float = 0.0, end: Optional[float] = None,
         out: Optional[str] = None, sr: int = 22050) -> str:
    """Обрезает аудио по времени (start/end в секундах)."""
    _require()
    y, sr = librosa.load(path, sr=sr, mono=True)
    s = max(0, int(float(start) * sr))
    e = len(y) if end is None else max(s, int(float(end) * sr))
    return _save(y[s:e].astype(np.float32), sr, out, path, "_trim")


def _key_shift(target_key: str, current_key: Optional[str]) -> int:
    t_idx = _parse_key(target_key)
    c_idx = _parse_key(current_key) if current_key else 0
    return (t_idx - c_idx) % 12


def _parse_key(name: str) -> int:
    s = name.strip()
    minor = bool(re.search(r'(minor|min|m)$', s, re.I)) and not s.lower().endswith('maj')
    if minor:
        s = re.sub(r'(minor|min|m)$', '', s, flags=re.I).strip()
    base_map = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
    letter = s[0].upper()
    acc = s[1] if len(s) > 1 and s[1] in '#b' else ''
    idx = base_map[letter]
    idx += 1 if acc == '#' else (-1 if acc == 'b' else 0)
    return idx % 12
