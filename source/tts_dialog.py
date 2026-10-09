import os
from PyQt6 import QtWidgets as qt
from PyQt6.QtCore import Qt, QRunnable, QThreadPool, QObject, pyqtSignal
from functions import speak, audio_player
from functions.gemini_ai import (
    TTS_MODELS, TTS_VOICES, DEFAULT_TTS_MODEL, DEFAULT_TTS_VOICE,
    synthesize_speech, load_gemini_config, update_gemini_config,
)

SAMPLE_TEXT = "Hello! This is a short sample of my voice."


class VoiceComboBox(qt.QComboBox):
    """A voice drop-down where Space plays a sample instead of opening the list."""
    sample_requested = pyqtSignal()

    def keyPressEvent(self, event):
        """Plays a voice sample when Space is pressed, otherwise behaves like a normal combo box."""
        if event.key() == Qt.Key.Key_Space and not event.modifiers():
            self.sample_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """Swallows the Space release so the list does not open."""
        if event.key() == Qt.Key.Key_Space and not event.modifiers():
            event.accept()
            return
        super().keyReleaseEvent(event)


class _Signals(QObject):
    """Carries task results from worker threads to the dialog."""
    finished = pyqtSignal(str, str, object, str)


class _TtsTask(QRunnable):
    """A background task that converts text to speech and reports the result by signal."""
    def __init__(self, kind, key, text, model, voice, style, signals):
        """Stores the task kind, text, model, voice, style and the signal object."""
        super().__init__()
        self.kind, self.key = kind, key
        self.text, self.model, self.voice, self.style = text, model, voice, style
        self.signals = signals

    def run(self):
        """Synthesizes the speech and emits the WAV bytes or the error text."""
        try:
            wav = synthesize_speech(self.text, self.model, self.voice, self.style)
            self.signals.finished.emit(self.kind, self.key, wav, "")
        except Exception as e:
            self.signals.finished.emit(self.kind, self.key, None, str(e))


class TextToSpeechDialog(qt.QDialog):
    """The dialog with the translation text, model, voice and style controls and the Play, Stop and Save buttons."""
    def __init__(self, parent, text):
        """Builds the controls, restores the saved preferences and lays them out."""
        super().__init__(parent)
        t = getattr(parent, "translations", {}) or {}
        self.t = t
        self.setMinimumSize(1000, 500)
        self.setWindowTitle(t.get("tts_window_title", "Text to speech"))
        self.audio_wav = None
        self.sample_cache = {}
        self.busy_convert = False
        self.busy_sample = False
        self._closed = False
        self.signals = _Signals()
        self.signals.finished.connect(self.on_task_finished)

        self.text_view = qt.QTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByKeyboard)
        self.text_view.setAccessibleName(t.get("tts_text_label", "Translation text"))
        self.text_view.setPlainText(text)
        self.label_text = qt.QLabel(t.get("tts_text_label", "Translation text"))
        self.label_text.setBuddy(self.text_view)

        config = load_gemini_config()
        self.model_combo = qt.QComboBox()
        self.model_combo.addItems(TTS_MODELS)
        self.model_combo.setAccessibleName(t.get("tts_model_label", "Speech model"))
        saved_model = config.get("tts_model", DEFAULT_TTS_MODEL)
        if saved_model in TTS_MODELS:
            self.model_combo.setCurrentText(saved_model)
        self.label_model = qt.QLabel(t.get("tts_model_label", "Speech model"))
        self.label_model.setBuddy(self.model_combo)

        self.voice_combo = VoiceComboBox()
        for name, desc in TTS_VOICES:
            self.voice_combo.addItem(f"{name} - {desc}", name)
        self.voice_combo.setAccessibleName(t.get("tts_voice_label", "Voice (press Space to hear a sample)"))
        saved_voice = config.get("tts_voice", DEFAULT_TTS_VOICE)
        index = self.voice_combo.findData(saved_voice)
        if index != -1:
            self.voice_combo.setCurrentIndex(index)
        self.voice_combo.sample_requested.connect(self.play_sample)
        self.label_voice = qt.QLabel(t.get("tts_voice_label", "Voice (press Space to hear a sample)"))
        self.label_voice.setBuddy(self.voice_combo)

        self.style_edit = qt.QLineEdit(config.get("tts_style", ""))
        self.style_edit.setPlaceholderText(t.get("tts_style_placeholder", "e.g. cheerfully, slowly, in a whisper"))
        self.style_edit.setAccessibleName(t.get("tts_style_label", "Speaking style (optional)"))
        self.label_style = qt.QLabel(t.get("tts_style_label", "Speaking style (optional)"))
        self.label_style.setBuddy(self.style_edit)

        self.convert_button = qt.QPushButton(t.get("tts_convert_button", "Convert to speech"))
        self.convert_button.setDefault(True)
        self.convert_button.clicked.connect(self.start_conversion)

        self.status_label = qt.QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setAccessibleName(t.get("tts_status_label", "Status"))

        self.play_button = qt.QPushButton(t.get("tts_play", "Play"))
        self.stop_button = qt.QPushButton(t.get("tts_stop", "Stop"))
        self.save_button = qt.QPushButton(t.get("tts_save", "Save"))
        self.play_button.clicked.connect(self.play_audio)
        self.stop_button.clicked.connect(audio_player.stop)
        self.save_button.clicked.connect(self.save_audio)
        for b in (self.play_button, self.stop_button, self.save_button):
            b.setVisible(False)

        self.close_button = qt.QPushButton(t.get("close", "Close"))
        self.close_button.clicked.connect(self.close)

        left = qt.QVBoxLayout()
        left.addWidget(self.label_text)
        left.addWidget(self.text_view)
        right = qt.QVBoxLayout()
        for w in (self.label_model, self.model_combo, self.label_voice, self.voice_combo,
                  self.label_style, self.style_edit, self.convert_button, self.status_label):
            right.addWidget(w)
        buttons = qt.QHBoxLayout()
        for b in (self.play_button, self.stop_button, self.save_button):
            buttons.addWidget(b)
        right.addLayout(buttons)
        right.addStretch(1)
        right.addWidget(self.close_button)
        main = qt.QHBoxLayout(self)
        main.addLayout(left, 2)
        main.addLayout(right, 1)

        self.setTabOrder(self.model_combo, self.voice_combo)
        self.voice_combo.setFocus()

    def set_status(self, message, announce=True):
        """Shows a status message and announces it with the screen reader."""
        self.status_label.setText(message)
        if announce:
            speak.speak(message)

    def _current(self):
        """Returns the selected (model, voice)."""
        return self.model_combo.currentText(), self.voice_combo.currentData()

    def _save_prefs(self):
        """Saves the selected model, voice and style for next time."""
        model, voice = self._current()
        try:
            update_gemini_config(tts_model=model, tts_voice=voice, tts_style=self.style_edit.text().strip())
        except Exception:
            pass

    def start_conversion(self):
        """Starts converting the whole text to speech in a background task."""
        if self.busy_convert:
            return
        text = self.text_view.toPlainText().strip()
        if not text:
            qt.QMessageBox.warning(self, self.t.get("warning_title", "Warning"),
                                   self.t.get("no_text_to_convert", "There is no text to convert!"))
            return
        model, voice = self._current()
        self._save_prefs()
        audio_player.stop()
        self.busy_convert = True
        self.convert_button.setEnabled(False)
        for b in (self.play_button, self.stop_button, self.save_button):
            b.setVisible(False)
        self.audio_wav = None
        self.set_status(self.t.get("tts_converting", "Converting text to speech, please wait..."))
        QThreadPool.globalInstance().start(
            _TtsTask("full", "", text, model, voice, self.style_edit.text().strip(), self.signals))

    def play_sample(self):
        """Plays a short sample of the selected voice (cached for instant repeats)."""
        if not audio_player.is_supported():
            self.set_status(self.t.get("tts_play_unsupported", "Audio playback is supported on Windows only"))
            return
        model, voice = self._current()
        key = f"{model}|{voice}"
        cached = self.sample_cache.get(key)
        if cached is not None:
            audio_player.play_wav_bytes(cached)
            return
        if self.busy_sample:
            return
        self.busy_sample = True
        speak.speak(self.t.get("tts_loading_sample", "Loading sample..."))
        QThreadPool.globalInstance().start(
            _TtsTask("sample", key, SAMPLE_TEXT, model, voice, "", self.signals))

    def on_task_finished(self, kind, key, wav, error):
        """Handles a finished task: plays a sample or reveals the Play, Stop and Save buttons."""
        if self._closed:
            return
        if kind == "sample":
            self.busy_sample = False
            if wav is None:
                self.set_status(f"{self.t.get('err_title', 'Error')}: {error}")
                return
            self.sample_cache[key] = wav
            model, voice = self._current()
            if key == f"{model}|{voice}":
                try:
                    audio_player.play_wav_bytes(wav)
                except Exception as e:
                    self.set_status(str(e))
            return
        self.busy_convert = False
        self.convert_button.setEnabled(True)
        if wav is None:
            self.set_status(f"{self.t.get('err_title', 'Error')}: {error}")
            return
        self.audio_wav = wav
        for b in (self.play_button, self.stop_button, self.save_button):
            b.setVisible(True)
        self.set_status(self.t.get("tts_done", "Conversion finished. You can play or save the audio."))
        self.play_button.setFocus()

    def play_audio(self):
        """Plays the converted audio."""
        if self.audio_wav is None:
            return
        try:
            audio_player.play_wav_bytes(self.audio_wav)
        except Exception as e:
            qt.QMessageBox.critical(self, self.t.get("err_title", "Error"), str(e))

    def save_audio(self):
        """Asks for a path and saves the converted audio as a WAV file."""
        if self.audio_wav is None:
            return
        target_dir = os.path.join(os.path.expanduser("~/Documents"), "translater")
        os.makedirs(target_dir, exist_ok=True)
        default_path = os.path.join(target_dir, "translated_speech.wav")
        path, _ = qt.QFileDialog.getSaveFileName(
            self, self.t.get("tts_save_title", "Save audio as"), default_path, "WAV Audio (*.wav)")
        if not path:
            return
        if not path.lower().endswith(".wav"):
            path += ".wav"
        try:
            with open(path, "wb") as f:
                f.write(self.audio_wav)
            self.set_status(self.t.get("tts_saved", "Audio saved successfully"))
        except Exception as e:
            qt.QMessageBox.critical(self, self.t.get("err_title", "Error"), str(e))

    def closeEvent(self, event):
        """Stops playback and removes temp files when the window closes."""
        audio_player.cleanup()
        super().closeEvent(event)

    def done(self, result):
        """Marks the dialog closed and cleans up audio before it ends."""
        self._closed = True
        audio_player.cleanup()
        super().done(result)
