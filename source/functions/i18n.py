import os
import json
from functions.app_paths import get_settings_file_path

DEFAULT_LANG_FILE = "en.json"


def load_current_language_and_color():
    """Returns (translations dict, saved color name) for the saved interface language, never raising."""
    lang_file_name = DEFAULT_LANG_FILE
    color_name = ""
    settings_path = get_settings_file_path()

    if os.path.exists(settings_path):
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                data_file = json.load(f)
            lang_file_name = data_file.get("laste_language", DEFAULT_LANG_FILE)
            color_name = data_file.get("color", "")
        except Exception:
            pass

    lang_path = os.path.join("data", "programm_language", lang_file_name)
    translations = {}
    if os.path.exists(lang_path):
        try:
            with open(lang_path, 'r', encoding='utf-8') as f:
                translations = json.load(f)
        except Exception:
            translations = {}

    return translations, color_name
