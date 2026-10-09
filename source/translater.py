import os,json,pyperclip,threading
import sys
# Relative paths such as data/... are always resolved from the program folder (needed when launched from a shortcut).
os.chdir(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__)))
import accessible_output3.outputs.auto
import user_guide,update,settings
from functions import speak
from functions.translate import translate_text
from tts_dialog import TextToSpeechDialog
from functions.error_log import log_exception
from functions.audio_transcribe import transcribe_file, file_dialog_filter, TranscriptionError, TranscriptionCancelled, STT_LANGUAGES, saved_stt_language
from functions.gemini_ai import update_gemini_config
from functions.text_to_image import text_to_image, is_unsupported_language
from functions.i18n import load_current_language_and_color  # Central module that loads the translations and the interface color
from PyQt6 import QtWidgets as qt
from PyQt6.QtCore import QThreadPool, pyqtSignal, Qt,QTimer
from PyQt6 import QtGui as qt1
CURRENT_VERSION ="2.2.1"
class TranslatorWindow(qt.QMainWindow):
    operation = pyqtSignal()
    speech_operation = pyqtSignal(str)
    speech_progress = pyqtSignal(int, int)  # (current part, total parts) while transcribing audio
    correction_operation = pyqtSignal()  # New signal for the spelling correction function, same pattern as the two signals above
    def __init__(self):
        # Builds the main window: the text input/output boxes, language dropdown, translate button, shortcuts and menus, then loads the language list from JSON
        super().__init__()
        self.setWindowTitle("Translator")
        self.text_input = qt.QTextEdit()
        self.text_input.setAccessibleName("inter text to translate")
        self.text_input.setTabChangesFocus(True)
        self.result_text = qt.QTextEdit()
        self.result_text.setAccessibleName("result translate")
        self.result_text.setReadOnly(True)
        self.result_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByKeyboard)
        self.language_list = qt.QComboBox()
        self.language_list.setAccessibleName("Choose the language")
        self.translate_button = qt.QPushButton("translate")
        self.translate_button.setDefault(True)
        self.translate_button.setIcon(qt1.QIcon("data/icons/translate_button_48.png"))
        self.translate_button.clicked.connect(self.start_translation)
        self.operation.connect(self.on_translation_finished)
        self.speech_operation.connect(self.fini_1)
        self.speech_progress.connect(self.on_speech_progress)
        self.stt_running = False
        self.stt_cancel_event = None
        self.correction_operation.connect(self.on_correction_finished)  # Connects the spelling correction signal the same way as the other two signals
        layout = qt.QVBoxLayout()
        self.label_input = qt.QLabel("input text")
        layout.addWidget(self.label_input)
        layout.addWidget(self.text_input)
        self.label_translate = qt.QLabel("translate text")  # Stores the label reference for the same reason
        layout.addWidget(self.label_translate)
        layout.addWidget(self.translate_button)
        self.label_result = qt.QLabel("result text")  # Stores the label for the same reason
        layout.addWidget(self.label_result)
        layout.addWidget(self.result_text)
        layout.addWidget(self.language_list)
        qt1.QShortcut("ctrl+t", self).activated.connect(self.start_translation)
        qt1.QShortcut("ctrl+r",self).activated.connect(lambda: self.result_text.setFocus())
        qt1.QShortcut("ctrl+i",self).activated.connect(lambda: self.text_input.setFocus())
        qt1.QShortcut("ctrl+l",self).activated.connect(lambda: self.language_list.setFocus())
        menu_bar = self.menuBar()
        self.file_menu = menu_bar.addMenu("file")  # Stores the menu reference so its title can be changed later when the language switches
        self.file_menu.setAccessibleName("file")
        self.open_file_action = qt1.QAction("open file", self)  # Stores the action reference so its text can be changed later
        self.open_file_action.triggered.connect(self.import_file)
        self.open_file_action.setShortcut("ctrl+o")
        self.open_file_action.setIcon(qt1.QIcon("data/icons/open_file_48.png"))
        self.save_file_action = qt1.QAction("save file", self)  # Stores the reference
        self.save_file_action.triggered.connect(self.save_file_in_computer)
        self.save_file_action.setShortcut("ctrl+s")
        self.save_file_action.setIcon(qt1.QIcon("data/icons/save_file_48.png"))
        self.welcom_app()
        self.clear_txt_action=qt1.QAction("clear input",self)  # Stores the reference
        self.clear_txt_action.triggered.connect(self.clear_input)
        self.clear_txt_action.setShortcut("ctrl+d")
        self.clear_txt_action.setIcon(qt1.QIcon("data/icons/clear_input_48.png"))
        self.clear_result_action=qt1.QAction("clear result",self)  # Stores the reference
        self.clear_result_action.triggered.connect(self.clear_result)
        self.clear_result_action.setShortcut("ctrl+shift+d")
        self.clear_result_action.setIcon(qt1.QIcon("data/icons/clear_result_48.png"))
        self.copy_translate_action=qt1.QAction("copy translate ",self)  # Stores the reference
        self.copy_translate_action.triggered.connect(self.copyd_txt)
        self.copy_translate_action.setShortcut("ctrl+shift+c")
        self.copy_translate_action.setIcon(qt1.QIcon("data/icons/copy_translate_48.png"))
        self.close_action=qt1.QAction("exit",self)  # Stores the reference
        self.close_action.triggered.connect(lambda: self.close())
        self.close_action.setShortcut("ctrl+q")
        self.close_action.setIcon(qt1.QIcon("data/icons/exit_48.png"))
        self.file_menu.addActions([self.open_file_action, self.save_file_action,self.clear_txt_action,self.clear_result_action,self.copy_translate_action,self.close_action])
        self.option_menu = menu_bar.addMenu("option")  # Stores the menu reference
        self.option_menu.setAccessibleName("options")
        self.convert_action = qt1.QAction("convert txt to image", self)  # Stores the reference
        self.convert_action.triggered.connect(self.convert_text_to_image)
        self.convert_action.setShortcut("ctrl+1")
        self.convert_action.setIcon(qt1.QIcon("data/icons/text_to_image_48.png"))
        self.convert_audio_action=qt1.QAction("speech to text",self)  # Stores the reference
        self.convert_audio_action.triggered.connect(self.start_op)
        self.convert_audio_action.setShortcut("ctrl+2")
        self.convert_audio_action.setIcon(qt1.QIcon("data/icons/speech_to_text_48.png"))
        self.correct_text_action=qt1.QAction("correct spelling",self)  # Button that corrects the text spelling with Gemini, inside the options menu as requested
        self.correct_text_action.triggered.connect(self.start_text_correction)
        self.correct_text_action.setShortcut("ctrl+3")
        self.tts_action=qt1.QAction("text to speech",self)  # converts the translation to speech with Gemini TTS
        self.tts_action.triggered.connect(self.open_tts_dialog)
        self.tts_action.setShortcut("ctrl+4")
        self.option_menu.addActions([self.convert_action,self.convert_audio_action,self.correct_text_action,self.tts_action])
        self.about_menu = menu_bar.addMenu("help")  # Stores the menu reference
        self.about_menu.setAccessibleName("help")
        self.about_app_action = qt1.QAction("about", self)  # Stores the reference
        self.about_app_action.setIcon(qt1.QIcon("data/icons/about_48.png"))
        self.how_to_use_action = qt1.QAction("user_guide", self)  # Stores the reference
        self.how_to_use_action.setIcon(qt1.QIcon("data/icons/how_to_use_48.png"))
        self.check_update_action = qt1.QAction("check for updates", self)  # Stores the reference
        self.about_app_action.triggered.connect(self.show_app_info)
        self.how_to_use_action.triggered.connect(self.show_user_guide)
        self.check_update_action.triggered.connect(lambda: update.check_for_update(self, CURRENT_VERSION, show_no_update_message=True))
        self.check_update_action.setShortcut("ctrl+u")
        self.check_update_action.setIcon(qt1.QIcon("data/icons/check_update_48.png"))
        self.settings_action=qt1.QAction("settings",self)  # Stores the reference (renamed from settings to avoid clashing with the imported settings.py module)
        self.settings_action.triggered.connect(self.window_settings)
        self.about_menu.addActions([self.about_app_action, self.how_to_use_action, self.check_update_action,self.settings_action])
        central_widget = qt.QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
        self.paste_to_txt()
        self.apply_language()  # Applies the previously saved interface language and color (if any) as soon as the program opens
        self.load_languages_from_json(os.path.join("data", "languages.json"))  # After applying the language so the translated error texts are used when needed
    def load_languages_from_json(self, json_path):
        # Reads the language name/code pairs from the given JSON file and fills the language dropdown, showing a fallback message if the file is missing or invalid
        t = getattr(self, "translations", {})  # Uses the current translations if they are loaded (for error messages only)
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for lang_name, lang_code in data.items():
                    self.language_list.addItem(lang_name, lang_code)
            except Exception as e:
                self.language_list.addItem(t.get("json_error_loading", "Error loading JSON"))
        else:
            self.language_list.addItem(t.get("json_not_found", "JSON file not found"))
    def start_translation(self):
        """Reads the input and language on the UI thread, then translates in a background thread."""
        if not self.translate_button.isEnabled():
            return  # another translation, correction or transcription is still running
        speak.speak("start translation")
        t = self.translations
        txt = self.text_input.toPlainText().strip()
        if not txt:
            qt.QMessageBox.warning(self, t.get("err_title", "Error"), t.get("text_must_be_entered", "Text must be entered"))
            return
        lang_code = self.language_list.currentData() or 'ar'
        lang_name = self.language_list.currentText() or 'arabic'
        self.result_text.setText(t.get("start_translate_placeholder", "start translate"))
        self.translate_button.setEnabled(False)  # prevent two overlapping translations
        QThreadPool.globalInstance().start(lambda: self.text_translate(txt, lang_name, lang_code))
    def text_translate(self, txt, lang_name, lang_code):
        """Translates with the chosen Gemini model in a worker thread and signals the UI when done."""
        try:
            self.translation_result = translate_text(txt, lang_name, lang_code)
        except Exception as e:
            self.translation_result = f"error: {str(e)}"
        self.operation.emit()
    def on_translation_finished(self):
        # Runs on the main UI thread once translation is done: shows the translated text in the result box, focuses it and plays a short notification sound
        self.translate_button.setEnabled(not self.stt_running)
        self.result_text.setFocus()
        self.result_text.setText(self.translation_result)
    def import_file(self):
        file_path, _ = qt.QFileDialog.getOpenFileName(self, self.translations.get("select_file_text_title", "Select Text File"), "", "Text Files (*.txt *.text *.html *.md *.json);;All files (*.*)")
        if file_path:
            try:
                with open(file_path, 'rb') as f:
                    raw = f.read()
            except OSError as e:
                qt.QMessageBox.critical(self, self.translations.get("err_title", "Error"), str(e))
                return
            content = None
            for encoding in ("utf-8-sig", "cp1256", "latin-1"):  # latin-1 never fails, so content is always set
                try:
                    content = raw.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            self.opened_file_path = file_path
            self.text_input.setText(content)
    def save_file_in_computer(self):
        # Saves the translated text to disk with a suggested filename and default location (Documents/translater) based on the imported file name and the target language, then lets the user confirm or change it
        if not self.result_text.toPlainText().strip():
            qt.QMessageBox.warning(self, self.translations.get("err_title", "Error"), self.translations.get("no_translated_text_msg", "There is no translated text to save. Translate first"))
            return
        lang_name = self.language_list.currentText() or "Arabic"
        documents_dir = os.path.expanduser("~/Documents")
        target_dir = os.path.join(documents_dir, "translater")
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
        if hasattr(self, 'opened_file_path') and self.opened_file_path:
            file_name = os.path.basename(self.opened_file_path)
            base_name, ext = os.path.splitext(file_name)
            filename_with_lang = f"{base_name}_{lang_name}{ext}"
        else:
            filename_with_lang = f"translated_{lang_name}.txt"
        default_save_path = os.path.join(target_dir, filename_with_lang)
        save_path, _ = qt.QFileDialog.getSaveFileName(
            self, self.translations.get("save_as_title", "save as"), default_save_path, "Text Files (*.txt *.text)"
        )
        if save_path:
            try:
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write(self.result_text.toPlainText())
            except OSError as e:
                qt.QMessageBox.critical(self, self.translations.get("err_title", "Error"), str(e))
    def show_app_info(self):
        try:
            with open("data/info_app.json", 'r', encoding='utf-8') as f:
                info_text = json.load(f).get("app info", "")
        except (OSError, ValueError) as e:
            qt.QMessageBox.critical(self, self.translations.get("err_title", "Error"), str(e))
            return
        qt.QMessageBox.about(self, self.translations.get("about", "about"), info_text)
    def paste_to_txt(self):
        paste_txt=pyperclip.paste()
        self.text_input.setText(paste_txt)
    def copyd_txt(self):
        text=self.result_text.toPlainText()
        if text:
            pyperclip.copy(text)
            speak.speak("The text has been copied to the clipboard")
        else:
            speak.speak("There is no text to copy")
    def clear_input(self):
        txt=self.text_input.toPlainText()
        if txt:
            self.text_input.clear()
            speak.speak("text has been deleted")
        else:
            speak.speak("There is no text")
    def clear_result(self):
        txt=self.result_text.toPlainText()
        if txt:
            self.result_text.clear()
            speak.speak("text has been deleted")
        else:
            speak.speak("There is no text")
    def convert_text_to_image(self):
        text = self.result_text.toPlainText().strip()
        t = self.translations  # Current translations so every message of this function uses the interface language
        if not text:
            qt.QMessageBox.warning(self, t.get("warning_title", "Warning"), t.get("no_text_to_convert", "There is no text to convert!"))
            return
        # Checks the chosen language or character range that the default font does not support (such as Asian and Indian scripts)
        current_lang_code = self.language_list.currentData() or ""
        if is_unsupported_language(current_lang_code):
            qt.QMessageBox.warning(self, t.get("unsupported_language_title", "Unsupported Language"), t.get("unsupported_language_msg", "This feature does not currently support this language"))
            return
        documents_dir = os.path.expanduser("~/Documents")
        target_dir = os.path.join(documents_dir, "translater")
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
        default_image_path = os.path.join(target_dir, "translated_image.png")
        save_path, _ = qt.QFileDialog.getSaveFileName(self, t.get("save_image_as_title", "Save Image As"), default_image_path, "PNG Image (*.png)")

        if save_path:
            try:
                text_to_image(text, save_path)
                qt.QMessageBox.information(self, t.get("success_title", "Success"), t.get("image_saved_msg", "Image saved successfully at:\n{path}").format(path=save_path))
            except Exception as error:
                qt.QMessageBox.critical(self, t.get("err_title", "Error"), t.get("image_save_failed_msg", "Failed to save image:\n{error}").format(error=str(error)))
    def open_tts_dialog(self):
        """Opens the text-to-speech window with the current translation."""
        text = self.result_text.toPlainText().strip()
        t = self.translations
        if not text:
            qt.QMessageBox.warning(self, t.get("warning_title", "Warning"), t.get("no_text_to_convert", "There is no text to convert!"))
            return
        TextToSpeechDialog(self, text).exec()
    def start_op(self):
        """Asks for an audio or video file and starts a chunked transcription, or offers to cancel a running one."""
        t = self.translations
        if self.stt_running:
            answer = qt.QMessageBox.question(
                self, t.get("stt_cancel_title", "Cancel"),
                t.get("stt_cancel_question", "A transcription is in progress. Do you want to cancel it?"))
            if answer == qt.QMessageBox.StandardButton.Yes and self.stt_cancel_event is not None:
                self.stt_cancel_event.set()
                speak.speak(t.get("stt_cancelling", "Cancelling after the current part..."))
            return
        file_path, _ = qt.QFileDialog.getOpenFileName(
            self,
            t.get("select_audio_file_title", "Select Audio File"),
            "",
            file_dialog_filter()
        )
        if file_path:
            if not self.translate_button.isEnabled():
                return  # a translation or correction is still running
            # The recognition language must be the language spoken in the file, so the user confirms it each time
            names = list(STT_LANGUAGES)
            current = saved_stt_language()
            current_index = next((i for i, n in enumerate(names) if STT_LANGUAGES[n] == current), 0)
            chosen, ok = qt.QInputDialog.getItem(
                self, t.get("stt_language_title", "Audio language"),
                t.get("stt_language_label", "Choose the language spoken in the file:"),
                names, current_index, False)
            if not ok:
                return
            language = STT_LANGUAGES[chosen]
            try:
                update_gemini_config(stt_language=language)
            except Exception:
                pass
            self.stt_running = True
            self.stt_cancel_event = threading.Event()
            self.result_text.setText(t.get("stt_preparing", "Preparing the audio file..."))
            self.translate_button.setEnabled(False)
            event = self.stt_cancel_event
            QThreadPool.globalInstance().start(lambda: self.listen_and_convert(file_path, event, language))
    def on_speech_progress(self, index, total):
        """Shows and announces the transcription progress."""
        t = self.translations
        if total == 0:
            message = t.get("stt_preparing", "Preparing the audio file...")
        else:
            message = t.get("stt_progress", "Transcribing part {i} of {n}...").format(i=index, n=total)
        self.result_text.setText(message)
        speak.speak(message)
    def listen_and_convert(self, audio_path, cancel_event, language=None):
        """Runs the transcription in a worker thread and keeps any text already transcribed on failure or cancel."""
        t = self.translations
        try:
            text = transcribe_file(audio_path, progress=lambda i, n: self.speech_progress.emit(i, n), cancel_event=cancel_event, language=language)
            if not text.strip():
                text = t.get("stt_no_speech", "No speech was found in the audio file.")
            self.speech_operation.emit(text)
        except TranscriptionCancelled as e:
            note = t.get("stt_cancelled", "[Cancelled before part {i} of {n}]").format(i=e.part, n=e.total)
            self.speech_operation.emit(f"{e.partial}\n\n{note}".strip())
        except TranscriptionError as e:
            log_path = log_exception("audio transcription")
            if e.part:
                note = t.get("stt_failed_at", "[Stopped at part {i} of {n}: {error}]").format(i=e.part, n=e.total, error=e)
            else:
                note = f"{t.get('speech_error_prefix', 'Error: ')}{e}"
            if log_path:
                note += "\n" + t.get("stt_log_note", "Details were saved to: {path}").format(path=log_path)
            self.speech_operation.emit(f"{e.partial}\n\n{note}".strip())
        except Exception as e:
            log_path = log_exception("audio transcription (unexpected)")
            note = f"{t.get('speech_error_prefix', 'Error: ')}{type(e).__name__}: {e}"
            if log_path:
                note += "\n" + t.get("stt_log_note", "Details were saved to: {path}").format(path=log_path)
            self.speech_operation.emit(note)

    def fini_1(self, result_text):
        """Shows the transcription result, clears the running state and re-enables the translate button."""
        self.stt_running = False
        self.stt_cancel_event = None
        self.result_text.setText(result_text)
        self.result_text.setFocus()
        self.translate_button.setEnabled(True)
        speak.speak(self.translations.get("stt_done", "Transcription finished"))
    def start_text_correction(self):
        if not self.translate_button.isEnabled():
            return  # another job is still running (the shortcut bypasses the disabled button)
        # Starts the spelling correction with Gemini, same pattern as start_translation: checks that there is text, then runs the real work in a background thread so the UI does not freeze
        t = self.translations
        txt = self.text_input.toPlainText().strip()
        if not txt:
            qt.QMessageBox.warning(self, t.get("err_title", "Error"), t.get("text_must_be_entered", "Text must be entered"))
            return
        speak.speak("start correction")
        self.translate_button.setEnabled(False)  # Temporarily disables translation during correction so the two operations do not clash on the same text
        QThreadPool.globalInstance().start(lambda: self.correct_text_job(txt))
    def correct_text_job(self, txt):
        # Runs in a background thread (QThreadPool): sends the current text to Gemini for spelling correction, stores the result and emits correction_operation so the main UI thread shows it safely through on_correction_finished
        try:
            from functions.gemini_ai import correct_text
            self.correction_result = correct_text(txt)
        except Exception as e:
            self.correction_result = f"{self.translations.get('speech_error_prefix', 'error: ')}{e}"
        self.correction_operation.emit()
    def on_correction_finished(self):
        # Runs on the main UI thread after correction: replaces the input text with the corrected text and re-enables the translate button
        self.text_input.setText(self.correction_result)
        self.translate_button.setEnabled(not self.stt_running)
        speak.speak("correction finished")
    def apply_language(self):
        t, color_name = load_current_language_and_color()
        self.translations = t  # Saves the dictionary as an attribute so the other functions (errors and alerts) use the same language
        # Applies each text to its widget, using get() with a default text to avoid any key missing from the language file
        self.setWindowTitle(t.get("window_title", "Translator"))
        self.label_input.setText(t.get("label_input", "input text"))
        self.text_input.setAccessibleName(t.get("input text","input text"))
        self.label_translate.setText(t.get("label_translate", "translate text"))
        self.label_result.setText(t.get("label_result", "result text"))
        self.result_text.setAccessibleName(t.get("result_text","result text"))
        self.translate_button.setText(t.get("translate", "translate"))
        self.language_list.setAccessibleName(t.get("list_language","Choose tha language"))
        self.file_menu.setTitle(t.get("file", "file"))
        self.file_menu.setAccessibleName(t.get("file","file"))
        self.open_file_action.setText(t.get("open", "open file"))
        self.save_file_action.setText(t.get("save", "save file"))
        self.clear_txt_action.setText(t.get("clear_input", "clear input"))
        self.clear_result_action.setText(t.get("clear_result", "clear result"))
        self.copy_translate_action.setText(t.get("copy", "copy translate"))
        self.close_action.setText(t.get("exit", "exit"))
        self.option_menu.setTitle(t.get("options", "option"))
        self.option_menu.setAccessibleName(t.get("options", ""))
        self.convert_action.setText(t.get("convert", "convert txt to image"))
        self.convert_audio_action.setText(t.get("speech", "speech to text"))
        self.correct_text_action.setText(t.get("correct", "correct spelling"))
        self.tts_action.setText(t.get("tts", "text to speech"))
        self.about_menu.setTitle(t.get("help", "help"))
        self.about_menu.setAccessibleName(t.get("help", ""))
        self.about_app_action.setText(t.get("about", "about"))
        self.how_to_use_action.setText(t.get("user", "user_guide"))
        self.check_update_action.setText(t.get("update", "check for updates"))
        self.settings_action.setText(t.get("settings", "settings"))
        if color_name:
            self.setStyleSheet(f"background-color: {color_name};")
        else:
            self.setStyleSheet("")  # No saved color, restores the default look of the interface
    def window_settings(self):
        settings.settings_dialog(self).exec()
    def show_user_guide(self):
        user_guide.UserGuideDialog(self).exec()
    def welcom_app(self):
        speak.speak("wilcome")
app = qt.QApplication([])
window = TranslatorWindow()
window.show()
update.check_for_update(window, CURRENT_VERSION, show_no_update_message=False)
app.exec()