import requests
from PyQt6 import QtWidgets as qt
from PyQt6 import QtCore as qtcore
from .updater import DownloadUpdateDialog

UPDATE_INFO_URL = "https://raw.githubusercontent.com/ahmedelmimouni3-coder/translater/main/update_info_TEMPLATE.json"
def _version_to_tuple(version_string):
    """Converts a version string such as 2.2.1 into a tuple of integers for comparison."""
    try:
        return tuple(int(part) for part in str(version_string).split("."))
    except (ValueError, AttributeError):
        return (0,)


class _UpdateCheckSignals(qtcore.QObject):
    """Carries the result of the update check from the worker thread to the UI."""
    finished = qtcore.pyqtSignal(object, str)


class _UpdateCheckTask(qtcore.QRunnable):
    """A background task that downloads the update information file."""
    def __init__(self, url):
        """Stores the update information URL and creates the result signal."""
        super().__init__()
        self.url = url
        self.signals = _UpdateCheckSignals()

    def run(self):
        """Fetches the update information and emits it, or emits the error text."""
        try:
            response = requests.get(self.url, timeout=5)
            response.raise_for_status()
            info = response.json()
            self.signals.finished.emit(info, "")
        except Exception as e:
            self.signals.finished.emit(None, str(e))


class _UpdateChecker(qtcore.QObject):
    """Starts an update check and shows the result to the user."""
    def __init__(self, parent, current_version, show_no_update_message):
        """Stores the settings and starts the background check."""
        super().__init__(parent)
        self.parent_widget = parent
        self.current_version = current_version
        self.show_no_update_message = show_no_update_message
        self.task = _UpdateCheckTask(UPDATE_INFO_URL)
        self.task.signals.finished.connect(self._on_finished)
        qtcore.QThreadPool.globalInstance().start(self.task)

    def _on_finished(self, info, error):
        """Handles the check result: reports errors, offers a new version, or says there is no update."""
        if error:
            if self.show_no_update_message:
                qt.QMessageBox.warning(
                    self.parent_widget,"Error", "Unable to connect to the server to check for updates. Make sure you are connected to the Internet and try later"
                )
            return

        latest_version = info.get("version", "0")
        if _version_to_tuple(latest_version) > _version_to_tuple(self.current_version):
            _show_update_dialog(self.parent_widget, latest_version, info.get("download", ""), info.get("what is new", ""))
        else:
            if self.show_no_update_message:
                qt.QMessageBox.information(self.parent_widget, "Information", "No new updates are available. You are using the latest version.")


def check_for_update(parent, current_version, show_no_update_message=True):
    """Starts an update check for the given current version."""
    checker = _UpdateChecker(parent, current_version, show_no_update_message)
    if not hasattr(parent, "_active_update_checkers"):
        parent._active_update_checkers = []
    parent._active_update_checkers.append(checker)


def _show_update_dialog(parent, version, download_url, whats_new):
    """Shows the new version with its release notes and starts the download if the user accepts."""
    dialog = qt.QDialog(parent)
    dialog.setWindowTitle("New update available")
    dialog.resize(420, 320)
    layout = qt.QVBoxLayout(dialog)

    title_label = qt.QLabel(f"A new version is available: {version}")
    layout.addWidget(title_label)

    whats_new_label = qt.QLabel("What's new:")
    layout.addWidget(whats_new_label)

    whats_new_text = qt.QTextEdit()
    whats_new_text.setPlainText(whats_new or "لا يوجد وصف للتغييرات.")
    whats_new_text.setReadOnly(True)
    whats_new_text.setTextInteractionFlags(qtcore.Qt.TextInteractionFlag.TextSelectableByKeyboard)
    layout.addWidget(whats_new_text)

    button_box = qt.QDialogButtonBox()
    download_button = button_box.addButton("download now ", qt.QDialogButtonBox.ButtonRole.AcceptRole)
    button_box.addButton("Later", qt.QDialogButtonBox.ButtonRole.RejectRole)
    button_box.accepted.connect(dialog.accept)
    button_box.rejected.connect(dialog.reject)
    layout.addWidget(button_box)

    dialog.exec()
    if dialog.result() == qt.QDialog.DialogCode.Accepted and download_url:
        DownloadUpdateDialog(parent, download_url).exec()
