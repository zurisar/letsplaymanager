import os
import re
from PyQt6.QtWidgets import (QDialog, QFormLayout, QLineEdit, QHBoxLayout, 
                             QPushButton, QFileDialog, QTabWidget, QWidget, 
                             QVBoxLayout, QLabel, QPlainTextEdit)
from core.config import _

class GameDialog(QDialog):
    def __init__(self, parent, config, game_name="", game_data=None):
        super().__init__(parent)
        self.config = config
        self.is_edit_mode = bool(game_data)
        self.game_data = game_data or {}
        
        title = f"{_('title_edit_action')}: {game_name}" if self.is_edit_mode else _("title_add_new_game")
        self.setWindowTitle(title)
        self.resize(600, 450)
        
        self.setup_ui(game_name)

    def setup_ui(self, game_name):
        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        
        # --- ВКЛАДКА 1: Основные настройки ---
        tab_general = QWidget()
        general_layout = QFormLayout(tab_general)
        general_layout.setContentsMargins(15, 15, 15, 15)
        general_layout.setSpacing(15)
        
        self.name_input = QLineEdit(game_name)
        if not self.is_edit_mode:
            self.name_input.textChanged.connect(self.update_folder_path)
        general_layout.addRow(_("lbl_game_name"), self.name_input)
        
        # Поле папки отображается только при добавлении новой игры
        if not self.is_edit_mode:
            folder_layout = QHBoxLayout()
            self.folder_input = QLineEdit()
            self.folder_btn = QPushButton(_("btn_browse"))
            self.folder_btn.clicked.connect(self.browse_folder)
            folder_layout.addWidget(self.folder_input)
            folder_layout.addWidget(self.folder_btn)
            general_layout.addRow(_("lbl_game_folder"), folder_layout)
        
        self.ai_url_input = QLineEdit(self.game_data.get('ai_url', ''))
        self.ai_url_input.setPlaceholderText("https://chatgpt.com/...")
        general_layout.addRow(_("lbl_ai_chat_link"), self.ai_url_input)
        
        self.steam_input = QLineEdit(self.game_data.get('steam_id', ''))
        self.steam_input.setPlaceholderText(_("placeholder_steam_id"))
        general_layout.addRow(_("lbl_steam_id"), self.steam_input)
        
        # --- ВКЛАДКА 2: Метаданные (Для шаблонов описаний) ---
        tab_meta = QWidget()
        meta_layout = QVBoxLayout(tab_meta)
        meta_layout.setContentsMargins(15, 15, 15, 15)
        
        meta_layout.addWidget(QLabel(_("lbl_desc_basic_game")))
        self.desc_template_input = QPlainTextEdit()
        self.desc_template_input.setPlainText(self.game_data.get('desc_template', ''))
        self.desc_template_input.setPlaceholderText("В этой игре мы пытаемся выжить в суровом мире...\n{episode_desc}")
        meta_layout.addWidget(self.desc_template_input)
        
        meta_layout.addWidget(QLabel(_("lbl_playlists_optional")))
        
        # Создаем словарь для хранения инпутов плейлистов
        self.playlist_inputs = {}
        
        # Импортируем список хостингов из базы
        from database import get_videohostings
        hostings = get_videohostings()
        
        # Подтягиваем уже сохраненные плейлисты, если мы в режиме редактирования
        saved_playlists = self.game_data.get("playlists", {})
        
        playlists_form = QFormLayout()
        for h_id, h_key, h_name in hostings:
            input_field = QLineEdit(saved_playlists.get(h_key, ""))
            input_field.setPlaceholderText(f"https://{h_key}.com/playlist...")
            playlists_form.addRow(f"{h_name}:", input_field)
            self.playlist_inputs[h_key] = input_field
            
        meta_layout.addLayout(playlists_form)
        
        meta_layout.addWidget(QLabel(_("lbl_desc_default_tags")))
        self.tags_input = QLineEdit(self.game_data.get('default_tags', ''))
        self.tags_input.setPlaceholderText(_("placeholder_default_tags"))
        meta_layout.addWidget(self.tags_input)
        
        self.tabs.addTab(tab_general, _("tab_general"))
        self.tabs.addTab(tab_meta, _("tab_desc_metadata"))
        main_layout.addWidget(self.tabs)
        
        # --- Кнопки сохранения ---
        btn_layout = QHBoxLayout()
        save_btn = QPushButton(f"💾 {_('btn_save')}" if self.is_edit_mode else _("btn_save"))
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton(_("btn_cancel"))
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        main_layout.addLayout(btn_layout)

    def browse_folder(self):
        start_dir = self.config.get("renders_folder", "")
        folder = QFileDialog.getExistingDirectory(self, _("dlg_game_select_game_folder"), start_dir)
        if folder:
            self.folder_input.setText(folder)

    def update_folder_path(self):
        renders_dir = self.config.get("renders_folder", "")
        if renders_dir:
            safe_name = re.sub(r'[\\/*?:"<>|]', "", self.name_input.text().strip())
            if safe_name:
                self.folder_input.setText(os.path.join(renders_dir, safe_name))
            else:
                self.folder_input.clear()
                
    def get_data(self):
        # Собираем все плейлисты, которые не пустые
        playlists = {}
        for h_key, input_field in self.playlist_inputs.items():
            url = input_field.text().strip()
            if url:
                playlists[h_key] = url

        data = {
            "name": self.name_input.text().strip(),
            "ai_url": self.ai_url_input.text().strip(),
            "steam_id": self.steam_input.text().strip(),
            "desc_template": self.desc_template_input.toPlainText().strip(),
            "default_tags": self.tags_input.text().strip(),
            "playlists": playlists # <--- Передаем собранный словарь
        }
        if not self.is_edit_mode:
            data["folder"] = self.folder_input.text().strip()
        return data