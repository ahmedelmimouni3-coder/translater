import array
import glob
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import wave

from functions.app_paths import get_settings_file_path
from functions.error_log import log_exception
from functions.speech_to_text import transcribe_audio_file, SpeechNotRecognized

AUDIO_VIDEO_EXTENSIONS = [
    "wav", "wave", "mp3", "mp2", "mpa", "m4a", "m4b", "m4r", "aac", "adts", "ac3", "eac3", "ec3",
    "ogg", "oga", "opus", "spx", "flac", "aif", "aiff", "aifc", "au", "snd", "caf", "amr", "awb",
    "gsm", "wma", "ape", "wv", "tta", "tak", "mka", "mpc", "ra", "voc", "w64", "rf64", "dts",
    "dtshd", "mlp", "thd", "weba", "8svx",
    "mp4", "m4v", "mov", "qt", "3gp", "3g2", "3ga", "mkv", "webm", "avi", "wmv", "asf", "flv", "f4v",
    "mpg", "mpeg", "mpe", "ts", "mts", "m2ts", "m2t", "vob", "ogv", "ogm", "rm", "rmvb", "divx", "mxf", "dv",
]

TARGET_SECONDS = 20.0
HARD_MAX_SECONDS = 30.0
WAV_PIECE_SECONDS = 30.0
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_FFMPEG_MISSING = (
    "لم يتم العثور على ffmpeg. بدونه يمكن تحويل ملفات WAV وAIFF وFLAC فقط. "
    "ثبّته عبر: pip install imageio-ffmpeg (النسخة التنفيذية تتضمنه تلقائياً)"
)


class TranscriptionError(RuntimeError):
    """A transcription failure that carries the text transcribed before it and the part where it stopped."""

    def __init__(self, message, partial="", part=0, total=0):
        """Stores the message, the partial text and the failing part number out of the total."""
        super().__init__(message)
        self.partial, self.part, self.total = partial, part, total


class TranscriptionCancelled(TranscriptionError):
    """Raised when the user cancels a transcription in progress."""


def file_dialog_filter():
    """Builds the open-file dialog filter listing all known audio and video extensions."""
    patterns = " ".join(f"*.{e}" for e in AUDIO_VIDEO_EXTENSIONS)
    return f"Audio and video files ({patterns});;All files (*.*)"


def _ffmpeg_candidates():
    """Yields possible ffmpeg paths: bundled with the frozen app or inside the imageio_ffmpeg package."""
    dirs = []
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        dirs += [os.path.join(base, "imageio_ffmpeg", "binaries"),
                 os.path.join(os.path.dirname(sys.executable), "_internal", "imageio_ffmpeg", "binaries"),
                 os.path.dirname(sys.executable)]
    try:
        spec = importlib.util.find_spec("imageio_ffmpeg")
        if spec and spec.submodule_search_locations:
            dirs.append(os.path.join(list(spec.submodule_search_locations)[0], "binaries"))
    except Exception:
        pass
    for d in dirs:
        yield from sorted(glob.glob(os.path.join(d, "ffmpeg*")))


def find_ffmpeg():
    """Returns the path of an ffmpeg executable, or None when none is available."""
    for path in _ffmpeg_candidates():
        if os.path.isfile(path) and (os.name != "nt" or path.lower().endswith(".exe")):
            return path
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.isfile(exe):
            return exe
    except Exception:
        pass
    return shutil.which("ffmpeg")


def _run(cmd):
    """Runs a command without a console window and returns the finished process."""
    return subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          creationflags=_NO_WINDOW)


def _tail(text, lines=3):
    """Returns the last few non-empty lines of a text on one line (for error messages)."""
    return " | ".join([l.strip() for l in text.strip().splitlines() if l.strip()][-lines:])


def _analyze(ffmpeg, path):
    """Returns ([(silence_start, silence_end)], duration_seconds_or_None) for an audio or video file."""
    proc = _run([ffmpeg, "-nostdin", "-hide_banner", "-i", path, "-vn",
                 "-af", "silencedetect=noise=-35dB:d=0.5", "-f", "null", "-"])
    err = proc.stderr.decode("utf-8", "replace")
    if proc.returncode != 0:
        raise TranscriptionError(f"تعذر قراءة الملف الصوتي (قد لا يحتوي على صوت أو الصيغة غير مدعومة): {_tail(err)}")
    starts = [float(x) for x in re.findall(r"silence_start:\s*(-?[\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*(-?[\d.]+)", err)]
    silences = list(zip(starts, ends))
    duration = None
    times = re.findall(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", err)
    if times:
        h, m, sec = times[-1]
        duration = int(h) * 3600 + int(m) * 60 + float(sec)
    else:
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", err)
        if m:
            duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return silences, duration


def choose_cuts(silences, duration, target=TARGET_SECONDS, hard_max=HARD_MAX_SECONDS):
    """Picks cut points: the first silence after `target` seconds, or a forced cut if none comes before `hard_max`."""
    cuts, last = [], 0.0
    for start, end in silences:
        mid = (max(start, 0.0) + end) / 2
        while mid - last > hard_max:
            last += target
            cuts.append(last)
        if mid - last >= target:
            cuts.append(mid)
            last = mid
    if duration:
        while duration - last > hard_max:
            last += target
            cuts.append(last)
    return cuts


def split_audio(ffmpeg, path, out_dir, target=TARGET_SECONDS, hard_max=HARD_MAX_SECONDS):
    """Decodes the file and splits it into 16 kHz mono WAV parts inside out_dir, returning the sorted paths."""
    silences, duration = _analyze(ffmpeg, path)
    base = [ffmpeg, "-nostdin", "-y", "-hide_banner", "-loglevel", "error", "-i", path,
            "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le"]
    pattern = os.path.join(out_dir, "chunk_%04d.wav")
    if duration is None:
        cmd = base + ["-f", "segment", "-segment_time", str(int(target)), "-reset_timestamps", "1", pattern]
    else:
        cuts = choose_cuts(silences, duration, target, hard_max)
        if cuts:
            cmd = base + ["-f", "segment", "-segment_times", ",".join(f"{c:.3f}" for c in cuts),
                          "-reset_timestamps", "1", pattern]
        else:
            cmd = base + [os.path.join(out_dir, "chunk_0000.wav")]
    proc = _run(cmd)
    chunks = sorted(glob.glob(os.path.join(out_dir, "chunk_*.wav")))
    if proc.returncode != 0 or not chunks:
        raise TranscriptionError(f"فشل تجهيز الملف الصوتي: {_tail(proc.stderr.decode('utf-8', 'replace'))}")
    return chunks


# Languages offered for recognition: the recognition language must match the language spoken in the file,
# otherwise the service invents words that sound similar in the wrong language.
STT_LANGUAGES = {
    "العربية - Arabic": "ar-SA",
    "English": "en-US",
    "Français - French": "fr-FR",
    "Español - Spanish": "es-ES",
    "Deutsch - German": "de-DE",
    "Italiano - Italian": "it-IT",
    "Português - Portuguese": "pt-PT",
    "Русский - Russian": "ru-RU",
    "Türkçe - Turkish": "tr-TR",
    "فارسی - Persian": "fa-IR",
    "اردو - Urdu": "ur-PK",
    "हिन्दी - Hindi": "hi-IN",
    "Bahasa Indonesia": "id-ID",
    "Nederlands - Dutch": "nl-NL",
    "日本語 - Japanese": "ja-JP",
    "한국어 - Korean": "ko-KR",
}
SILENCE_RMS = 100  # average 16-bit amplitude under which a part is considered empty (about -50 dB)


def interface_stt_language():
    """Maps the saved interface language to a speech recognition language code (Arabic by default)."""
    codes = {"ar": "ar-SA", "en": "en-US", "fr": "fr-FR"}
    try:
        with open(get_settings_file_path(), "r", encoding="utf-8") as f:
            saved = json.load(f).get("laste_language", "")
        return codes.get(saved.split(".")[0], "ar-SA")
    except Exception:
        return "ar-SA"


def saved_stt_language():
    """Returns the recognition language the user chose last time, or the one matching the interface language."""
    try:
        from functions.gemini_ai import load_gemini_config
        code = load_gemini_config().get("stt_language", "")
        if code in STT_LANGUAGES.values():
            return code
    except Exception:
        pass
    return interface_stt_language()


def _is_silent(path):
    """Returns True when a 16-bit WAV part contains (almost) only silence, so it is not sent for recognition."""
    try:
        with wave.open(path, "rb") as w:
            if w.getsampwidth() != 2:
                return False
            samples = array.array("h")
            samples.frombytes(w.readframes(w.getnframes()))
    except Exception:
        return False
    if not samples:
        return True
    if sys.byteorder == "big":
        samples.byteswap()
    rms = (sum(s * s for s in samples) / len(samples)) ** 0.5
    return rms < SILENCE_RMS


def _join_texts(texts):
    """Joins part texts, using a paragraph break after a finished sentence and a space otherwise."""
    out = ""
    for t in texts:
        if not out:
            out = t
        else:
            out += ("\n\n" if out.rstrip()[-1] in ".!?؟。…" else " ") + t
    return out


def _transcribe_pieces(pieces, progress, cancel_event, language):
    """Converts each piece file with transcribe_audio_file, honoring cancel and keeping the text so far on failure."""
    total, texts = len(pieces), []
    for i, piece in enumerate(pieces, 1):
        if cancel_event is not None and cancel_event.is_set():
            raise TranscriptionCancelled("تم إلغاء العملية", _join_texts(texts), i, total)
        progress(i, total)
        if _is_silent(piece):
            continue  # silence makes the recognizer invent text
        try:
            text = transcribe_audio_file(piece, language)
        except SpeechNotRecognized:
            text = ""
        except Exception as e:
            log_exception("Speech recognition")
            raise TranscriptionError(str(e), _join_texts(texts), i, total) from e
        if text.strip():
            texts.append(text.strip())
    return _join_texts(texts)


def _split_wav_without_ffmpeg(path, out_dir):
    """Splits a PCM WAV file into short WAV pieces with the standard library and returns their paths."""
    try:
        reader = wave.open(path, "rb")
    except (wave.Error, EOFError) as e:
        raise TranscriptionError(f"تعذر قراءة ملف WAV بدون ffmpeg (قد لا يكون بصيغة PCM عادية): {e}") from e
    paths = []
    with reader:
        channels, width, rate = reader.getnchannels(), reader.getsampwidth(), reader.getframerate()
        frames_per_piece = int(WAV_PIECE_SECONDS * rate)
        while True:
            frames = reader.readframes(frames_per_piece)
            if not frames:
                break
            piece_path = os.path.join(out_dir, f"piece_{len(paths):05d}.wav")
            with wave.open(piece_path, "wb") as out:
                out.setnchannels(channels)
                out.setsampwidth(width)
                out.setframerate(rate)
                out.writeframes(frames)
            paths.append(piece_path)
    return paths


def _transcribe_without_ffmpeg(path, progress, cancel_event, language):
    """Transcribes without ffmpeg: WAV is split in pieces, AIFF and FLAC are read directly, other formats need ffmpeg."""
    ext = os.path.splitext(path)[1].lstrip(".").lower()
    if ext in ("wav", "wave"):
        tmp = tempfile.mkdtemp(prefix="translator_stt_")
        try:
            progress(0, 0)
            return _transcribe_pieces(_split_wav_without_ffmpeg(path, tmp), progress, cancel_event, language)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    if ext in ("aif", "aiff", "aifc", "flac"):
        return _transcribe_pieces([path], progress, cancel_event, language)
    raise TranscriptionError(_FFMPEG_MISSING)


def transcribe_file(path, progress=None, cancel_event=None, language=None):
    """Transcribes an audio or video file of any size: ffmpeg splits it into short parts and each part goes through transcribe_audio_file."""
    progress = progress or (lambda i, n: None)
    if not os.path.isfile(path):
        raise TranscriptionError("الملف غير موجود")
    language = language or saved_stt_language()
    ffmpeg = find_ffmpeg()
    if ffmpeg is None:
        return _transcribe_without_ffmpeg(path, progress, cancel_event, language)
    tmp = tempfile.mkdtemp(prefix="translator_stt_")
    try:
        progress(0, 0)
        try:
            chunks = split_audio(ffmpeg, path, tmp)
        except TranscriptionError:
            log_exception("ffmpeg split")
            raise
        return _transcribe_pieces(chunks, progress, cancel_event, language)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
