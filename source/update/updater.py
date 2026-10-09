import os
import subprocess
import requests
from PyQt6 import QtWidgets as qt
from PyQt6 import QtCore as qtcore
class DownloadSignals(qtcore.QObject):
    """Carries download progress and the final result from the worker thread."""
    progress = qtcore.pyqtSignal(int)
    finished = qtcore.pyqtSignal(str)
class DownloadTask(qtcore.QRunnable):
    """A background task that downloads the update installer file."""
    def __init__(self, url):
        """Stores the download URL, the cancel flag and the target folder."""
        super().__init__()
        self.url = url
        self.signals = DownloadSignals()
        self.is_cancelled = False
        self.download_dir = os.path.join(os.getenv("LOCALAPPDATA", os.path.expanduser("~")), "Translater", "update")
    def run(self):
        """Downloads the installer in chunks, reporting progress, and emits the file path, 'cancelled' or 'error'."""
        try:
            if os.path.exists(self.download_dir):
                for old_file in os.listdir(self.download_dir):
                    os.remove(os.path.join(self.download_dir, old_file))
            os.makedirs(self.download_dir, exist_ok=True)
        except Exception:
            self.signals.finished.emit("error")
            return
        file_path = os.path.join(self.download_dir, self.url.split("/")[-1])
        try:
            with requests.get(self.url, stream=True, timeout=15) as response:
                if response.status_code != 200:
                    self.signals.finished.emit("error")
                    return
                total_size = int(response.headers.get("content-length", 0))
                received = 0
                with open(file_path, "wb") as f:
                    for chunk in response.iter_content(1024):
                        if self.is_cancelled:
                            self.signals.finished.emit("cancelled")
                            return
                        f.write(chunk)
                        received += len(chunk)
                        if total_size:
                            self.signals.progress.emit(int(received / total_size * 100))
            self.signals.finished.emit(file_path)
        except Exception:
            self.signals.finished.emit("error")
class DownloadUpdateDialog(qt.QDialog):
    """A dialog that shows the update download progress with a cancel button."""
    def __init__(self, parent, url):
        """Builds the progress dialog and starts the download."""
        super().__init__(parent)
        self.setWindowTitle("جاري تحميل التحديث")
        self.resize(320, 120)
        layout = qt.QVBoxLayout(self)
        self.status_label = qt.QLabel("يجري الآن تحميل التحديث...")
        layout.addWidget(self.status_label)
        self.progress_bar = qt.QProgressBar()
        self.progress_bar.setFocusPolicy(qtcore.Qt.FocusPolicy.StrongFocus)
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)
        self.cancel_button = qt.QPushButton("إلغاء")
        self.cancel_button.clicked.connect(self.cancel_download)
        layout.addWidget(self.cancel_button)
        self.task = DownloadTask(url)
        self.task.signals.progress.connect(self.progress_bar.setValue)
        self.task.signals.finished.connect(self.on_finished)
        qtcore.QThreadPool.globalInstance().start(self.task)
    def cancel_download(self):
        """Requests cancelling the download."""
        self.task.is_cancelled = True
        self.status_label.setText("جاري الإلغاء...")
    def on_finished(self, result):
        """Handles the download result: shows errors, or runs the installer silently and quits the program."""
        if result == "error":
            qt.QMessageBox.critical(self, "خطأ", "حدث خطأ أثناء التحميل. تحقق من اتصالك وحاول لاحقًا.")
            self.close()
        elif result == "cancelled":
            self.close()
        else:
            try:
                subprocess.Popen([result, "/SILENT", "/NOCANCEL", "/SUPPRESSMSGBOXES", "/NORESTART"])
                qt.QApplication.quit()
            except OSError:
                os.startfile(os.path.dirname(result))
                qt.QMessageBox.information(
                    self, "تم التحميل", "تم تحميل التحديث. افتح الملف يدويًا لإكمال التثبيت."
                )
            self.close()
