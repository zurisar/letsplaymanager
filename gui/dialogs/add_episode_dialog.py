import os
from PyQt6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QLineEdit, QPushButton, QFileDialog, QComboBox, QSpinBox, QCheckBox
from core.config import _
from database import get_episodes

class AddEpisodeDialog(QDialog):
    def __init__(self, parent, games, current_game_id, config): 
        super().__init__(parent)
        self.config = config 
        self.setWindowTitle(f"{_('title_add_episode')} (MKV -> MP4)")
        self.resize(500, 200)

        layout = QFormLayout(self)

        file_layout = QHBoxLayout()
        self.file_input = QLineEdit()
        self.file_input.setReadOnly(True)
        file_btn = QPushButton(_("btn_select_file"))
        file_btn.clicked.connect(self.select_file)
        file_layout.addWidget(self.file_input)
        file_layout.addWidget(file_btn)
        layout.addRow(_("lbl_source_file"), file_layout)

        self.game_selector = QComboBox()
        for game_id, name, folder_path, ai_url, steam_id, desc_template, default_tags in games:
            self.game_selector.addItem(name, userData={'id': game_id, 'path': folder_path})
            if game_id == current_game_id:
                self.game_selector.setCurrentIndex(self.game_selector.count() - 1)
        
        layout.addRow(_("lbl_game"), self.game_selector)

        self.ep_spinbox = QSpinBox()
        self.ep_spinbox.setMinimum(1)
        self.ep_spinbox.setMaximum(9999)
        layout.addRow(_("lbl_episode_number"), self.ep_spinbox)
        
        self.game_selector.currentIndexChanged.connect(self.update_episode_number)
        self.update_episode_number()

        # self.convert_checkbox = QCheckBox(_("lbl_push_video_over_ffmpeg"))
        # self.convert_checkbox.setChecked(True) 
        self.process_mode_combo = QComboBox()
        self.process_mode_combo.addItems([
            _("mode_move_only"), 
            _("mode_fast_remux"), 
            _("mode_optimize_edit")
        ])
        layout.addRow(f"{_('lbl_action')}:", self.process_mode_combo)

        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton(_("btn_add_and_convert"))
        self.add_btn.clicked.connect(self.accept) 
        cancel_btn = QPushButton(_("btn_cancel"))
        cancel_btn.clicked.connect(self.reject) 
        
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

    def select_file(self):
        start_dir = self.config.get("recordings_folder", "") 
        # Добавляем ключи перевода для диалога выбора файла
        file, ignored = QFileDialog.getOpenFileName(
            self, 
            _("title_select_source_video"), 
            start_dir, 
            f"{_('lbl_video_files')} (*.mkv *.mp4 *.avi)"
        )
        if file:
            self.file_input.setText(file)
            
            # --- ИСПРАВЛЕННАЯ ЛОГИКА ---
            # Если это уже mp4, ставим индекс 0 ("Только перемещение")
            if file.lower().endswith('.mp4'):
                self.process_mode_combo.setCurrentIndex(0)
            # Если это mkv или avi, ставим индекс 1 ("Быстрый Remux")
            else:
                self.process_mode_combo.setCurrentIndex(1)

    def update_episode_number(self):
        current_index = self.game_selector.currentIndex()
        if current_index == -1:
            return
            
        game_data = self.game_selector.itemData(current_index)
        game_id = game_data['id']
        
        episodes = get_episodes(game_id)
        if episodes:
            max_ep = max(ep[1] for ep in episodes)
            self.ep_spinbox.setValue(max_ep + 1)
        else:
            self.ep_spinbox.setValue(1)