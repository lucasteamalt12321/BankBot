"""Тесты модуля музыки: MIDI (mido) и аудио (librosa/soundfile)."""
import os
import numpy as np
import pytest

mido = pytest.importorskip("mido")
librosa = pytest.importorskip("librosa")
pytest.importorskip("soundfile")

from core.music import midi_utils, audio_utils, analyze, detect_bpm, detect_key, change_tempo, change_key, overlay


def _make_midi(path, bpm=120, key='C', note=60, beats=8):
    mf = mido.MidiFile()
    tr = mido.MidiTrack()
    tr.append(mido.MetaMessage('key_signature', key=key, time=0))
    tr.append(mido.MetaMessage('set_tempo', tempo=int(60000000 / bpm), time=0))
    tick = mf.ticks_per_beat
    for _ in range(beats):
        tr.append(mido.Message('note_on', note=note, velocity=80, time=0))
        tr.append(mido.Message('note_off', note=note, velocity=0, time=tick))
    mf.tracks.append(tr)
    mf.save(path)
    return path


def test_midi_detect_bpm_and_key(tmp_path):
    p = _make_midi(tmp_path / 'a.mid', bpm=120, key='C')
    assert abs(detect_bpm(str(p)) - 120) < 1e-6
    assert detect_key(str(p)) == 'C'


def test_midi_change_key_transposes_notes(tmp_path):
    p = _make_midi(tmp_path / 'a.mid', note=60)
    out = change_key(str(p), semitones=3)
    mf = mido.MidiFile(out)
    notes = [m.note for tr in mf.tracks for m in tr if m.type == 'note_on' and m.velocity]
    assert all(n == 63 for n in notes)


def test_midi_change_tempo_factor(tmp_path):
    p = _make_midi(tmp_path / 'a.mid', bpm=120)
    out = change_tempo(str(p), factor=2.0)
    mf = mido.MidiFile(out)
    # при factor=2 все длительности событий удвоены
    times = [m.time for tr in mf.tracks for m in tr]
    assert any(t >= mf.ticks_per_beat * 2 - 1 for t in times)


def test_midi_overlay_combines_tracks(tmp_path):
    a = _make_midi(tmp_path / 'a.mid', note=60)
    b = _make_midi(tmp_path / 'b.mid', note=64)
    out = overlay([str(a), str(b)])
    mf = mido.MidiFile(out)
    assert len(mf.tracks) == 2


def _make_click_wav(path, bpm=120, sr=22050, seconds=4.0):
    period = 60.0 / bpm
    n = int(seconds * sr)
    sig = np.zeros(n, dtype=np.float32)
    pos = 0
    while pos < n:
        end = min(pos + int(0.05 * sr), n)
        sig[pos:end] = 1.0
        pos += int(period * sr)
    import soundfile as sf
    sf.write(str(path), sig, sr)
    return path


def test_audio_detect_bpm(tmp_path):
    p = _make_click_wav(tmp_path / 'c.wav', bpm=120)
    assert abs(detect_bpm(str(p)) - 120) < 30


def test_audio_change_tempo(tmp_path):
    p = _make_click_wav(tmp_path / 'c.wav', bpm=120)
    out = change_tempo(str(p), target_bpm=240)
    assert os.path.exists(out)
    # time_stretch ускоряет сигнал в ~2 раза -> длительность заметно уменьшается
    dur_in = librosa.get_duration(path=str(p))
    dur_out = librosa.get_duration(path=str(out))
    assert dur_out < dur_in * 0.7


def test_audio_overlay(tmp_path):
    a = _make_click_wav(tmp_path / 'a.wav', bpm=120)
    b = _make_click_wav(tmp_path / 'b.wav', bpm=120)
    out = overlay([str(a), str(b)])
    assert os.path.exists(out)
