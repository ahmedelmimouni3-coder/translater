import os
import shutil
import tempfile

try:
    import winsound
except ImportError:
    winsound = None

_temp_dir = None
_counter = 0


def is_supported():
    """Returns True when audio playback is available on this system."""
    return winsound is not None


def _get_temp_dir():
    """Returns the temporary folder used for playback files, creating it when needed."""
    global _temp_dir
    if _temp_dir is None or not os.path.isdir(_temp_dir):
        _temp_dir = tempfile.mkdtemp(prefix="translator_tts_")
    return _temp_dir


def play_wav_bytes(wav_bytes):
    """Plays WAV bytes asynchronously, stopping any sound that is already playing."""
    global _counter
    if winsound is None:
        raise RuntimeError("تشغيل الصوت مدعوم على ويندوز فقط")
    _counter += 1
    path = os.path.join(_get_temp_dir(), f"audio_{_counter}.wav")
    with open(path, "wb") as f:
        f.write(wav_bytes)
    winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)


def stop():
    """Stops any sound that is currently playing."""
    if winsound is not None:
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass


def cleanup():
    """Stops playback and deletes the temporary playback files."""
    global _temp_dir
    stop()
    if _temp_dir:
        shutil.rmtree(_temp_dir, ignore_errors=True)
        _temp_dir = None
