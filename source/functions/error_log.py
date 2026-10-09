import os
import datetime
import traceback
from functions.app_paths import _get_app_data_dir

LOG_FILE_NAME = "translator_errors.log"
MAX_LOG_BYTES = 1024 * 1024


def get_log_path():
    """Returns the path of the error log file inside the application data folder."""
    return os.path.join(_get_app_data_dir(), LOG_FILE_NAME)


def log_exception(context):
    """Appends the exception being handled, with its traceback, to the log file and returns the file path."""
    path = get_log_path()
    try:
        if os.path.exists(path) and os.path.getsize(path) > MAX_LOG_BYTES:
            os.remove(path)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n=== {datetime.datetime.now():%Y-%m-%d %H:%M:%S} | {context} ===\n")
            f.write(traceback.format_exc())
    except Exception:
        return ""
    return path
