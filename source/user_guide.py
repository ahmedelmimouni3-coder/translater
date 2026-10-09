import json,webbrowser
from PyQt6 import QtWidgets as qt
from PyQt6 import QtCore as qt1
class UserGuideDialog(qt.QDialog):
    """The user guide window with usage instructions, developer links and the shortcuts list."""
    def __init__(self, parent=None):
        """Builds the guide text box, developer accounts list, shortcuts list and close button."""
        super().__init__(parent)
        self.setMinimumSize(1000, 500)
        self.setWindowTitle("user guide")
        self.info_display = qt.QTextEdit()
        self.info_display.setReadOnly(True)
        self.info_display.setTextInteractionFlags(qt1.Qt.TextInteractionFlag.TextSelectableByKeyboard)
        self.list=qt.QListWidget()
        self.list.setAccessibleName("Developer Accounts")
        self.list.addItems(["youtube","get hup","telegram"])
        self.list.itemActivated.connect(self.open_lenks)
        self.list_shortcut=qt.QListWidget()
        self.list_shortcut.setAccessibleName("shortcut")
        self.list_shortcut.addItems(["save file ctrl+s","open file ctrl+o","clear result ctrl+shift+d","clear input ctrl+d","copy result ctrl+shift+c","goto language ctrl+l","enter txt ctrl+i","result ctrl+r","start translate ctrl+t","exit programme ctrl+q","txt to image ctrl+1","speech to txt ctrl+2","correct txt ctrl+3","text to speech ctrl+4","check for update ctrl+u"])
        self.close_button = qt.QPushButton("close")
        self.close_button.clicked.connect(lambda: self.close())
        layout = qt.QVBoxLayout(self)
        layout.addWidget(self.info_display)
        layout.addWidget(qt.QLabel("developer accounts"))
        layout.addWidget(self.list)
        layout.addWidget(self.list_shortcut)
        layout.addWidget(self.close_button)
        self.load_info()
    def load_info(self):
        """Loads the how-to-use text from data/info_app.json into the text box."""
        with open("data/info_app.json", 'r', encoding='utf-8') as f:
            data = json.load(f)
            how_to_use_text = data.get("how to use", "no text")
            self.info_display.setText(str(how_to_use_text))
    def open_lenks(self):
        """Opens the developer link that matches the selected account."""
        item=self.list.currentRow()
        if item==0:
            webbrowser.open("https://www.youtube.com/@x-blind-b1n")
        if item==1:
            webbrowser.open("https://github.com/Ahmedelmimouni3-coder")
        if item==2:
            webbrowser.open("https://t.me/Ae142")
