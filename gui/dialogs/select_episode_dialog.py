from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QComboBox, 
                             QPushButton, QHBoxLayout, QMessageBox)
from database import get_episodes
from core.config import _

class SelectEpisodeDialog(QDialog):
    def __init__(self, parent, game_id):
        super().__init__(parent)
        self.setWindowTitle(_("title_select_episode"))
        self.resize(350, 120)
        
        self.game_id = game_id
        self.selected_ep_id = None
        self.selected_ep_number = None
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(_("lbl_choose_episode")))
        
        self.combo = QComboBox()
        layout.addWidget(self.combo)
        
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton(_("btn_select"))
        ok_btn.clicked.connect(self.accept_selection)
        cancel_btn = QPushButton(_("btn_cancel"))
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        self.load_episodes()
        
    def load_episodes(self):
        # Получаем эпизоды только для текущей игры
        episodes = get_episodes(self.game_id) 
        
        for ep in episodes:
            # Структура из базы: ep[0] = id, ep[1] = number, ep[2] = title
            ep_id, ep_num, title = ep[0], ep[1], ep[2]
            display_text = f"Ep. {ep_num} - {title}"
            
            self.combo.addItem(display_text, userData={'id': ep_id, 'number': ep_num})
            
    def accept_selection(self):
        if self.combo.currentIndex() == -1:
            QMessageBox.warning(self, _("msg_title_error"), _("msg_no_available_episodes"))
            return
        
        data = self.combo.currentData()
        self.selected_ep_id = data['id']
        self.selected_ep_number = data['number']
        self.accept()