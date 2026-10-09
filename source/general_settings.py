import os,webbrowser,json
from PyQt6 import QtWidgets as qt
from PyQt6 import QtGui as qt1
from functions.app_paths import get_settings_file_path
from functions.gemini_ai import load_gemini_config, DEFAULT_GEMINI_MODEL
LANGUAGE_DISPLAY_TO_FILE = {
    "العربية": "ar.json",
    "french": "fr.json",
    "english": "en.json",
}
FILE_TO_LANGUAGE_DISPLAY = {value: key for key, value in LANGUAGE_DISPLAY_TO_FILE.items()}

GEMINI_MODEL_OPTIONS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-pro-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
]
class general_settings(qt.QWidget):
    """The general settings page: interface color, interface language, Gemini model and API key."""
    def __init__(self):
        """Builds the color, language, model and API key controls and lays them out."""
        super().__init__()
        self.color_inter_face=qt.QComboBox()
        colors=qt1.QColor.colorNames()
        self.color_inter_face.setAccessibleName("color interface")
        self.language_inter_face=qt.QComboBox()
        self.color_inter_face.addItem("default", "")  # keeps the system look; avoids forcing a color the user never chose
        self.color_inter_face.addItems(colors)
        self.color_inter_face.currentIndexChanged.connect(self.preview_color)
        self.language_inter_face.addItems(["العربية","french","english"])
        self.language_inter_face.setAccessibleName("choose language inter face")
        self.gemini_model=qt.QComboBox()
        self.gemini_model.setEditable(True)
        self.gemini_model.addItems(GEMINI_MODEL_OPTIONS)
        self.gemini_model.setAccessibleName("choose gemini model")
        self.gemini_api_key=qt.QLineEdit()
        self.gemini_api_key.setEchoMode(qt.QLineEdit.EchoMode.Password)
        self.gemini_api_key.setPlaceholderText("Gemini API Key")
        self.gemini_api_key.setAccessibleName("gemini api key")
        self.get_API=qt.QPushButton("GET API")
        self.get_API.clicked.connect(lambda: webbrowser.open("https://aistudio.google.com/apikey"))
        layout = qt.QVBoxLayout(self)
        self.label_color = qt.QLabel("color")
        layout.addWidget(self.label_color)
        layout.addWidget(self.color_inter_face)
        self.label_language = qt.QLabel("interface language")
        layout.addWidget(self.label_language)
        layout.addWidget(self.language_inter_face)
        self.label_model = qt.QLabel("Gemini model")
        layout.addWidget(self.label_model)
        layout.addWidget(self.gemini_model)
        self.label_api_key = qt.QLabel("Gemini API key")
        layout.addWidget(self.label_api_key)
        layout.addWidget(self.gemini_api_key)
        layout.addWidget(qt.QLabel("GET API"))
        layout.addWidget(self.get_API)
    def apply_language(self, t):
        """Applies the translated labels and accessible names to the page."""
        self.label_color.setText(t.get("color_interface", "color"))
        self.color_inter_face.setAccessibleName(t.get("color_interface", "color"))
        self.label_language.setText(t.get("language_interface", "interface language"))
        self.language_inter_face.setAccessibleName(t.get("language_interface", "interface language"))
        self.label_model.setText(t.get("choose_model", "Gemini model"))
        self.gemini_model.setAccessibleName(t.get("choose_model", "Gemini model"))
    def preview_color(self, *_):
        """Previews the chosen color on the settings window immediately (empty = default look)."""
        window = self.window()
        if not isinstance(window, qt.QDialog):
            return  # not placed in the settings window yet
        color_name = self.color_inter_face.currentData() or ""
        window.setStyleSheet(f"background-color: {color_name};" if color_name else "")
    def load_general_settings(self):
        """Loads the saved color and interface language into the controls, then the Gemini settings."""
        settings_path = get_settings_file_path()
        if os.path.exists(settings_path):
            try:
                with open(settings_path,'r',encoding='utf-8') as file:
                    data=json.load(file)
                    comobox=data.get("color","")
                    if comobox:
                        index=self.color_inter_face.findText(comobox)
                        if index!=-1:
                            self.color_inter_face.setCurrentIndex(index)
                    else:
                        self.color_inter_face.setCurrentIndex(0)
                    saved_lang_file=data.get("laste_language","")
                    display_name=FILE_TO_LANGUAGE_DISPLAY.get(saved_lang_file,"")
                    if display_name:
                        lang_index=self.language_inter_face.findText(display_name)
                        if lang_index!=-1:
                            self.language_inter_face.setCurrentIndex(lang_index)
            except Exception:
                pass
        self.load_gemini_settings()
    def load_gemini_settings(self):
        """Loads the saved Gemini model and API key into the controls."""
        config = load_gemini_config()
        saved_model = config.get("model", "")
        if saved_model:
            self.gemini_model.setCurrentText(saved_model)
        saved_api_key = config.get("api_key", "")
        if saved_api_key:
            self.gemini_api_key.setText(saved_api_key)
    def get_general_settings(self):
        """Returns the chosen color and interface language file as a dict to be saved."""
        selected_language_display=self.language_inter_face.currentText()
        data={
            "color": self.color_inter_face.currentData() or "",
            "laste_language": LANGUAGE_DISPLAY_TO_FILE.get(selected_language_display,"en.json")
        }
        return data
    def get_gemini_settings(self):
        """Returns the chosen Gemini model and API key as a dict."""
        model_name = self.gemini_model.currentText().strip() or DEFAULT_GEMINI_MODEL
        api_key = self.gemini_api_key.text().strip()
        return {"model": model_name, "api_key": api_key}
