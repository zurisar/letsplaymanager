from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit
from core.config import _

class ProgressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{_('title_conversion')} (FFmpeg)")
        self.resize(600, 400)
        
        layout = QVBoxLayout(self)
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("font-family: Consolas; font-size: 10pt;")
        layout.addWidget(self.log_output)
        
    def append_log(self, text):
        self.log_output.append(text)
        scrollbar = self.log_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())