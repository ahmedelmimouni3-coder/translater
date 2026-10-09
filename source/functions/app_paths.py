import os
import shutil

APP_FOLDER_NAME = "Translator"
SETTINGS_FILE_NAME = "data_settings.json"
GEMINI_CONFIG_FILE_NAME = "gemini_config.json"
LEGACY_SETTINGS_PATH = "data_settings.json"


def _get_app_data_dir():
    """Returns the application data folder (inside APPDATA), creating it if needed."""
    app_data_dir = os.getenv("APPDATA")
    if not app_data_dir:
        app_data_dir = os.path.join(os.path.expanduser("~"), ".config")
    settings_dir = os.path.join(app_data_dir, APP_FOLDER_NAME)
    os.makedirs(settings_dir, exist_ok=True)
    return settings_dir


def get_settings_file_path():
    """Returns the path of the settings file, copying a legacy settings file into place when found."""
    settings_dir = _get_app_data_dir()

    settings_path = os.path.join(settings_dir, SETTINGS_FILE_NAME)

    if not os.path.exists(settings_path) and os.path.exists(LEGACY_SETTINGS_PATH):
        try:
            shutil.copyfile(LEGACY_SETTINGS_PATH, settings_path)
        except Exception:
            pass

    return settings_path


def get_gemini_config_path():
    """Returns the path of the Gemini configuration file."""
    settings_dir = _get_app_data_dir()
    return os.path.join(settings_dir, GEMINI_CONFIG_FILE_NAME)
