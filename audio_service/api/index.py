"""Отдельный Vercel-сервис обработки аудио/MIDI (модуль «Музыка»).

Переиспользует логику core/music (mido + librosa/soundfile). LTHub обращается сюда
по CORS. Эндпоинты зеркальны LTHub: /api/music/{analyze,change_tempo,change_key,overlay}.
"""
from __future__ import annotations

import os
import tempfile

from flask import Flask, after_this_request, jsonify, request, send_file

from music import analyze, change_tempo, change_key, overlay, audio_utils, normalize, reverse, echo, trim

app = Flask(__name__)

_MUSIC_ALLOWED = {".mid", ".midi", ".mp3", ".wav"}
_MUSIC_MAX_BYTES = 8 * 1024 * 1024
_MUSIC_MIME = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".mid": "audio/midi", ".midi": "audio/midi"}


@app.after_request
def _cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


@app.before_request
def _preflight():
    if request.method == "OPTIONS":
        return ("", 204)


@app.route("/health")
def health():
    return jsonify({"ok": True, "audio_available": audio_utils._LIBROSA})


def _cleanup_after(path_or_dir):
    """Schedule removal of a temp file/dir after the response body is sent.

    Uses Response.call_on_close so the temp files survive streaming via
    send_file and are then deleted, preventing per-request dir leaks.
    """
    import shutil
    target = path_or_dir if os.path.isdir(path_or_dir) else os.path.dirname(path_or_dir)

    @after_this_request
    def _rm(resp):
        resp.call_on_close(lambda *a: shutil.rmtree(target, ignore_errors=True))
        return resp
    return path_or_dir


def _music_save_upload(field):
    f = request.files.get(field)
    if not f:
        return None, "Файл не передан (поле '%s')" % field
    fn = (f.filename or "file").strip()
    ext = ("." + fn.rsplit(".", 1)[-1].lower()) if "." in fn else ""
    if ext not in _MUSIC_ALLOWED:
        return None, "Недопустимый формат (разрешены mid/midi/mp3/wav)"
    data = f.read()
    if not data:
        return None, "Пустой файл"
    if len(data) > _MUSIC_MAX_BYTES:
        return None, "Файл слишком большой (макс. 8 МБ)"
    d = tempfile.mkdtemp(prefix="music_")
    path = os.path.join(d, "input" + ext)
    with open(path, "wb") as fp:
        fp.write(data)
    return path, None


def _music_send(out_path):
    ext = os.path.splitext(out_path)[1].lower()
    mime = _MUSIC_MIME.get(ext, "application/octet-stream")
    return send_file(out_path, mimetype=mime, as_attachment=True, download_name="music" + ext)


@app.route("/api/music/analyze", methods=["POST"])
def api_music_analyze():
    path, err = _music_save_upload("file")
    if err:
        return jsonify({"error": err}), 400
    _cleanup_after(path)
    try:
        res = analyze(path)
        res["audio_available"] = audio_utils._LIBROSA
        return jsonify(res)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/music/change_tempo", methods=["POST"])
def api_music_change_tempo():
    path, err = _music_save_upload("file")
    if err:
        return jsonify({"error": err}), 400
    _cleanup_after(path)
    target = request.form.get("target_bpm")
    factor = request.form.get("factor")
    try:
        if target:
            out = change_tempo(path, target_bpm=float(target))
        elif factor:
            out = change_tempo(path, factor=float(factor))
        else:
            return jsonify({"error": "нужен target_bpm или factor"}), 400
        return _music_send(out)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/music/change_key", methods=["POST"])
def api_music_change_key():
    path, err = _music_save_upload("file")
    if err:
        return jsonify({"error": err}), 400
    _cleanup_after(path)
    semitones = request.form.get("semitones")
    target_key = request.form.get("target_key") or None
    try:
        if semitones:
            out = change_key(path, semitones=int(semitones))
        elif target_key:
            out = change_key(path, target_key=target_key)
        else:
            return jsonify({"error": "нужен semitones или target_key"}), 400
        return _music_send(out)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/music/overlay", methods=["POST"])
def api_music_overlay():
    files = request.files.getlist("files")
    if len(files) < 2:
        return jsonify({"error": "нужно минимум 2 файла для наложения"}), 400
    if len(files) > 8:
        return jsonify({"error": "максимум 8 файлов для наложения"}), 400
    d = tempfile.mkdtemp(prefix="music_ov_")
    paths = []
    for i, f in enumerate(files):
        fn = (f.filename or "f").strip()
        ext = ("." + fn.rsplit(".", 1)[-1].lower()) if "." in fn else ".wav"
        if ext not in _MUSIC_ALLOWED:
            return jsonify({"error": "Недопустимый формат: " + fn}), 400
        data = f.read()
        if not data:
            return jsonify({"error": "Пустой файл: " + fn}), 400
        if len(data) > _MUSIC_MAX_BYTES:
            return jsonify({"error": "Файл слишком большой (макс. 8 МБ): " + fn}), 400
        p = os.path.join(d, "in%d%s" % (i, ext))
        with open(p, "wb") as fp:
            fp.write(data)
        paths.append(p)
    _cleanup_after(d)
    try:
        out = overlay(paths)
        return _music_send(out)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


def _audio_only(path):
    """Эффекты применимы только к аудио (не к MIDI)."""
    if not audio_utils._LIBROSA:
        return None, "Аудио-библиотеки недоступны на сервере"
    if (path or "").lower().endswith((".mid", ".midi")):
        return None, "Эффект доступен только для аудио (MP3/WAV)"
    return path, None


@app.route("/api/music/normalize", methods=["POST"])
def api_music_normalize():
    path, err = _music_save_upload("file")
    if err:
        return jsonify({"error": err}), 400
    _cleanup_after(path)
    path, err = _audio_only(path)
    if err:
        return jsonify({"error": err}), 400
    try:
        return _music_send(normalize(path))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/music/reverse", methods=["POST"])
def api_music_reverse():
    path, err = _music_save_upload("file")
    if err:
        return jsonify({"error": err}), 400
    _cleanup_after(path)
    path, err = _audio_only(path)
    if err:
        return jsonify({"error": err}), 400
    try:
        return _music_send(reverse(path))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/music/echo", methods=["POST"])
def api_music_echo():
    path, err = _music_save_upload("file")
    if err:
        return jsonify({"error": err}), 400
    _cleanup_after(path)
    path, err = _audio_only(path)
    if err:
        return jsonify({"error": err}), 400
    try:
        delay = float(request.form.get("delay", 0.25))
        decay = float(request.form.get("decay", 0.4))
        return _music_send(echo(path, delay=delay, decay=decay))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/music/trim", methods=["POST"])
def api_music_trim():
    path, err = _music_save_upload("file")
    if err:
        return jsonify({"error": err}), 400
    _cleanup_after(path)
    path, err = _audio_only(path)
    if err:
        return jsonify({"error": err}), 400
    try:
        start = float(request.form.get("start", 0.0))
        end = request.form.get("end")
        end = float(end) if end not in (None, "") else None
        return _music_send(trim(path, start=start, end=end))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
