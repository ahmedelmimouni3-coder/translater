"""Converts an audio file to text with the SpeechRecognition library."""
import speech_recognition as sr

# Google returns a confidence value for its best guess. Below this value the guess is treated as
# "not recognized" instead of being inserted into the text (this is what produced invented words
# for music, noise and speech in a different language).
MIN_CONFIDENCE = 0.45


class SpeechNotRecognized(RuntimeError):
    """Raised when no speech could be recognized in the audio file."""


class SpeechServiceError(RuntimeError):
    """Raised when the speech recognition service cannot be reached."""


def transcribe_audio_file(audio_path, language="ar-SA"):
    """Reads a WAV, AIFF or FLAC file and converts it to text with the free Google Speech Recognition service.

    Raises SpeechNotRecognized when nothing was understood or the best guess has a low confidence.
    """
    recognizer = sr.Recognizer()
    recognizer.operation_timeout = 60
    with sr.AudioFile(audio_path) as source:
        audio = recognizer.record(source)
    try:
        result = recognizer.recognize_google(audio, language=language, show_all=True)
    except sr.RequestError as e:
        raise SpeechServiceError(f"تعذر الاتصال بخدمة التعرف على الصوت: {e}")
    except sr.UnknownValueError:
        raise SpeechNotRecognized("تعذر التعرف على الكلام في الملف الصوتي")
    alternatives = result.get("alternative") if isinstance(result, dict) else None
    if not alternatives:
        raise SpeechNotRecognized("تعذر التعرف على الكلام في الملف الصوتي")
    best = alternatives[0]
    text = (best.get("transcript") or "").strip()
    confidence = best.get("confidence")  # Google gives it only for the first alternative, and not always
    if not text or (confidence is not None and confidence < MIN_CONFIDENCE):
        raise SpeechNotRecognized("الثقة في النتيجة منخفضة")
    return text
