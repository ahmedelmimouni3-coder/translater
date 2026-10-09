import json
from PyQt6 import QtWidgets as qt
from PyQt6 import QtCore as qt1
from general_settings import general_settings
from functions.app_paths import get_settings_file_path
from functions.i18n import load_current_language_and_color
from functions.gemini_ai import save_gemini_config
class settings_dialog(qt.QDialog):
    """The settings window with a section tree and the general settings page."""
    def __init__(self, parent=None):
        """Builds the settings window with its section list, pages and save button."""
        super().__init__(parent)
        self.setMinimumSize(1000, 500)
        self.setWindowTitle("settings")
        self.tri=qt.QTreeWidget()
        self.tri.setHeaderHidden(True)
        self.item_general=qt.QTreeWidgetItem(self.tri,["general"])
        self.stacked_widget=qt.QStackedWidget()
        self.general_page=general_settings()
        self.general_page.load_general_settings()
        self.stacked_widget.addWidget(self.general_page)
        self.tri.currentItemChanged.connect(self.on_item_changed)
        self.save_buttion=qt.QPushButton("save settings ")
        self.save_buttion.clicked.connect(self.save_all_settings)
        layout=qt.QVBoxLayout(self)
        layout.addWidget(self.tri)
        layout.addWidget(self.stacked_widget)
        layout.addWidget(self.save_buttion)
        self.apply_language()
    def apply_language(self):
        """Applies the saved interface language and color to this window and its page."""
        t, color_name = load_current_language_and_color()
        self.translations = t
        self.setWindowTitle(t.get("settings_window_title", "settings"))
        self.item_general.setText(0, t.get("general_section", "general"))
        self.save_buttion.setText(t.get("save_settings_button", "save settings "))
        self.general_page.apply_language(t)
        if color_name:
            self.setStyleSheet(f"background-color: {color_name};")
        else:
            self.setStyleSheet("")
    def on_item_changed(self, current, previous):
        """Shows the page that belongs to the selected section."""
        if current:
            index = self.tri.indexOfTopLevelItem(current)
            if index != -1:
                    self.stacked_widget.setCurrentIndex(index)
    def save_all_settings(self):
        """Saves the general and Gemini settings, refreshes the main window and closes this window."""
        try:
            finel_data=self.general_page.get_general_settings()
            settings_path = get_settings_file_path()
            with open(settings_path,'w',encoding='utf-8') as f:
                json.dump(finel_data,f,ensure_ascii=False,indent=4)
            gemini_data = self.general_page.get_gemini_settings()
            save_gemini_config(gemini_data["model"], gemini_data["api_key"])
            t = getattr(self, "translations", {})
            qt.QMessageBox.information(self, t.get("success_title", "success"), t.get("settings_saved_msg", "don"))
            if self.parent() is not None and hasattr(self.parent(),"apply_language"):
                self.parent().apply_language()
            self.apply_language()
            self.close()
        except Exception as e:
            t = getattr(self, "translations", {})
            qt.QMessageBox.critical(self, t.get("err_title", "error"), t.get("settings_save_failed_msg", "error "))
