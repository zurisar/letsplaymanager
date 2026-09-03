import os
import re
from PyQt6.QtWidgets import QDialog, QFormLayout, QLineEdit, QHBoxLayout, QPushButton, QFileDialog
from core.config import _

class AddGameDialog(QDialog):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.config = config
        self.manual_path = False
        self.setWindowTitle(_("title_add_new_game"))
        self.resize(500, 200)

        layout = QFormLayout(self)

        self.name_input = QLineEdit()
        self.name_input.textChanged.connect(self.update_folder_path)
        layout.addRow(_("lbl_game_name"), self.name_input)

        folder_layout = QHBoxLayout()
        self.folder_input = QLineEdit()
        self.folder_btn = QPushButton(_("btn_browse", "Обзор"))
        self.folder_btn.clicked.connect(self.browse_folder)
        
        folder_layout.addWidget(self.folder_input)
        folder_layout.addWidget(self.folder_btn)
        layout.addRow(_("lbl_game_folder"), folder_layout)

        self.ai_url_input = QLineEdit()
        self.ai_url_input.setPlaceholderText("https://chatgpt.com/...")
        layout.addRow(_("lbl_ai_chat_link"), self.ai_url_input)

        self.steam_input = QLineEdit()
        self.steam_input.setPlaceholderText("Например: 108600 (Project Zomboid)")
        layout.addRow("Steam ID (опционально):", self.steam_input)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton(_("btn_save", "Сохранить"))
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton(_("btn_cancel", "Отмена"))
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

    def browse_folder(self):
        start_dir = self.config.get("renders_folder", "")
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку для игры", start_dir)
        if folder:
            self.folder_input.setText(folder)
            self.manual_path = True 

    def update_folder_path(self):
        renders_dir = self.config.get("renders_folder", "")
        if renders_dir:
            safe_name = re.sub(r'[\\/*?:"<>|]', "", self.name_input.text().strip())
            if safe_name:
                self.folder_input.setText(os.path.join(renders_dir, safe_name))
            else:
                self.folder_input.clear()