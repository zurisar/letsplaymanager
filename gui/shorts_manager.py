import os
import shutil
import webbrowser
import subprocess
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QWidget, 
                             QLabel, QPushButton, QTableWidget, QTableWidgetItem, 
                             QCheckBox, QMessageBox, QFileDialog, QInputDialog, QLineEdit)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from core.config import _
from database import (get_shorts, add_short_to_db, update_short_field, 
                      get_short_uploads, update_short_upload_status, update_short_url)
from gui.dialogs.calendar_dialog import CalendarDialog
from gui.dialogs.shorts_cutter_dialog import ShortsCutterDialog

class ShortsManagerDialog(QDialog):
    def __init__(self, parent, ep_id, ep_number, ep_folder, game_name, db_size, db_duration, ai_url, config, hostings):
        super().__init__(parent)
        self.ep_id = ep_id
        self.ep_number = ep_number
        self.ep_folder = ep_folder
        self.shorts_folder = os.path.join(ep_folder, "shorts")
        self.game_name = game_name
        self.ai_url = ai_url
        self.config = config
        self.hostings = hostings

        self.setWindowTitle(f"{_('title_shorts_manager')}: {game_name} - Эпизод {ep_number}")
        self.resize(950, 500)
        layout = QVBoxLayout(self)

        # --- ВЕРХНЯЯ ИНФО-ПАНЕЛЬ ---
        info_group = QWidget()
        info_layout = QVBoxLayout(info_group)
        
        title_lbl = QLabel(f"<b>{game_name} - {_('lbl_episode')} {ep_number}</b>")
        title_lbl.setStyleSheet("font-size: 16px;")
        stats_lbl = QLabel(f"{_('lbl_source')}: {db_size} | {db_duration}")
        
        btn_layout = QHBoxLayout()
        play_btn = QPushButton(f"▶ {_('lbl_source_video')}")
        play_btn.clicked.connect(self.play_original)
        
        folder_btn = QPushButton(f"📁 {_('lbl_episode_folder')}")
        folder_btn.clicked.connect(lambda: os.startfile(self.ep_folder) if os.path.exists(self.ep_folder) else None)
        
        editor_btn = QPushButton(f"🎬 {_('lbl_videoeditor')}")
        editor_btn.setToolTip(_("tooltip_run_videoeditor"))
        editor_btn.clicked.connect(self.launch_editor)

        cut_btn = QPushButton("✂️ Нарезать шортсы") # <--- НОВАЯ КНОПКА
        cut_btn.clicked.connect(self.open_shorts_cutter)
        
        ai_btn = QPushButton(_("lbl_ai_chat"))
        ai_btn.clicked.connect(lambda: webbrowser.open(self.ai_url) if self.ai_url else QMessageBox.warning(self, _("status_error"), _("msg_ai_link_not_set")))

        btn_layout.addWidget(play_btn)
        btn_layout.addWidget(folder_btn)
        btn_layout.addWidget(editor_btn)
        btn_layout.addWidget(cut_btn)
        btn_layout.addWidget(ai_btn)
        
        info_layout.addWidget(title_lbl)
        info_layout.addWidget(stats_lbl)
        info_layout.addLayout(btn_layout)
        layout.addWidget(info_group)

        # --- ТАБЛИЦА ШОРТСОВ ---
        self.table = QTableWidget(0, 6 + len(self.hostings))
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)
        layout.addWidget(self.table)

        # --- ПАНЕЛЬ ДОБАВЛЕНИЯ ---
        add_btn = QPushButton(f"+ {_('lbl_add_shorts')}")
        add_btn.setStyleSheet("padding: 10px; font-weight: bold;")
        add_btn.clicked.connect(self.add_short)
        layout.addWidget(add_btn)

        self.update_table()

    def open_shorts_cutter(self):
        if not os.path.exists(self.ep_folder):
            return
            
        video_file = None
        for f in os.listdir(self.ep_folder):
            if f.endswith(('.mp4', '.mkv', '.avi')) and "shorts" not in f.lower():
                video_file = os.path.join(self.ep_folder, f)
                if f.endswith('.mp4'): break
                
        if video_file:
            dialog = ShortsCutterDialog(self, video_file)
            dialog.exec()
        else:
            QMessageBox.warning(self, _("status_error"), "Исходное видео не найдено.")

    def launch_editor(self):
        editor_path = self.config.get("video_editor_path", "")
        if os.path.exists(editor_path):
            subprocess.Popen([editor_path])
        else:
            QMessageBox.warning(self, _("status_error"), _("msg_videoeditor_path_not_set"))

    def play_original(self):
        if not os.path.exists(self.ep_folder): return
        for f in os.listdir(self.ep_folder):
            if f.endswith(('.mp4', '.mkv', '.avi')) and "shorts" not in f.lower():
                os.startfile(os.path.join(self.ep_folder, f))
                return
        QMessageBox.warning(self, _("status_error"), _("msg_episode_file_not_found"))

    def update_table(self):
        shorts = get_shorts(self.ep_id)
        self.table.clearContents()
        self.table.setRowCount(len(shorts))
        
        headers = [_("col_name"), _("col_size"), _("col_time"), _("col_media"), _("col_tags"), _("col_publish_date")] + [h[2] for h in self.hostings]
        self.table.setHorizontalHeaderLabels(headers)
        
        for row, s in enumerate(shorts):
            s_id, s_num, s_size, s_dur, s_title, s_tags, s_pub = s
            display_title = s_title if s_title else f"Shorts_{s_num}"
            
            title_item = QTableWidgetItem(display_title)
            title_item.setData(Qt.ItemDataRole.UserRole, s_id)
            self.table.setItem(row, 0, title_item)
            self.table.setItem(row, 1, QTableWidgetItem(s_size))
            self.table.setItem(row, 2, QTableWidgetItem(s_dur))
            
            # Медиа-кнопки
            media_w = QWidget()
            m_lay = QHBoxLayout(media_w)
            m_lay.setContentsMargins(2,2,2,2)
            f_btn = QPushButton("📁")
            f_btn.setFixedWidth(30)
            f_btn.clicked.connect(lambda ch, sid=s_id: os.startfile(self.shorts_folder) if os.path.exists(self.shorts_folder) else None)
            p_btn = QPushButton("▶")
            p_btn.setFixedWidth(30)
            p_btn.clicked.connect(lambda ch, sid=s_id, num=s_num: self.play_short(num))
            m_lay.addWidget(f_btn)
            m_lay.addWidget(p_btn)
            self.table.setCellWidget(row, 3, media_w)
            
            # Теги
            tags_item = QTableWidgetItem(s_tags if s_tags else _("lbl_add_tags"))
            if not s_tags: tags_item.setBackground(QColor("#ffcccb"))
            self.table.setItem(row, 4, tags_item)
            
            self.table.setItem(row, 5, QTableWidgetItem(s_pub if s_pub else _("lbl_not_set")))
            
            # Хостинги
            uploads = {int(u[0]): u[2] for u in get_short_uploads(s_id)}
            for col_off, (h_id, ignored, h_name) in enumerate(self.hostings):
                hw = QWidget()
                hl = QHBoxLayout(hw)
                hl.setContentsMargins(2,2,2,2)
                
                cb = QCheckBox()
                cb.setChecked(h_id in uploads)
                cb.toggled.connect(lambda ch, sid=s_id, hid=h_id: update_short_upload_status(sid, hid, int(ch)))
                
                url = next((u[2] for u in get_short_uploads(s_id) if u[0] == h_id), "")
                link_btn = QPushButton("🌐" if url else "✏️")
                link_btn.setFixedWidth(30)
                if url: link_btn.setStyleSheet("background-color: #add8e6;")
                
                link_btn.clicked.connect(lambda ch, sid=s_id, hid=h_id, hn=h_name, u=url: webbrowser.open(u) if u else self.edit_url(sid, hid, hn))
                link_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                link_btn.customContextMenuRequested.connect(lambda pos, sid=s_id, hid=h_id, hn=h_name: self.edit_url(sid, hid, hn))
                
                hl.addWidget(cb)
                hl.addWidget(link_btn)
                self.table.setCellWidget(row, 6 + col_off, hw)

    def play_short(self, s_num):
        if not os.path.exists(self.shorts_folder): return
        expected = f"Short {s_num}"
        for f in os.listdir(self.shorts_folder):
            if expected in f and f.endswith(('.mp4', '.mkv')):
                os.startfile(os.path.join(self.shorts_folder, f))
                return
        QMessageBox.warning(self, _("status_error"), _("msg_short_file_not_found"))

    def add_short(self):
        start_dir = self.config.get("renders_folder", "")
        file, ignored = QFileDialog.getOpenFileName(self, _("lbl_select_short"), start_dir, f"{_('lbl_video_files')} (*.mp4 *.mkv)")
        if not file: return
        
        os.makedirs(self.shorts_folder, exist_ok=True)
        shorts = get_shorts(self.ep_id)
        next_num = max([s[1] for s in shorts] + [0]) + 1
        
        filename, ext = os.path.splitext(file)
        out_name = f"{self.game_name} - Ep.{self.ep_number} - Short {next_num}{ext}"
        out_path = os.path.join(self.shorts_folder, out_name)
        
        norm_in = os.path.normpath(file)
        norm_out = os.path.normpath(out_path)
        
        if norm_in != norm_out:
            try:
                shutil.move(norm_in, norm_out)
            except Exception as e:
                QMessageBox.critical(self, _("status_error"), f"{_('lbl_video_convert_error')}:\n{e}")
                return
        
        # Запрашиваем размер и время через родительское окно
        size_str = self.parent().get_format_size(os.path.getsize(norm_out))
        dur_str = self.parent().get_video_duration(norm_out)
        
        add_short_to_db(self.ep_id, next_num, size_str, dur_str)
        self.update_table()
        self.parent().update_table()

    def on_cell_double_clicked(self, row, column):
        s_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        
        if column == 0:
            cur = self.table.item(row, 0).text()
            if cur.startswith("Shorts_"): cur = ""
            new_t, ok = QInputDialog.getText(self, _("lbl_name"), _("lbl_own_name"), QLineEdit.EchoMode.Normal, cur)
            if ok: update_short_field(s_id, 'custom_title', new_t.strip())
                
        elif column == 4:
            cur = self.table.item(row, 4).text()
            if cur == "Добавить теги": cur = ""
            new_t, ok = QInputDialog.getText(self, _("lbl_tags"), _("lbl_enter_tags"), QLineEdit.EchoMode.Normal, cur)
            if ok: update_short_field(s_id, 'tags', new_t.strip())
                
        elif column == 5:
            cur = self.table.item(row, 5).text()
            dialog = CalendarDialog(self, cur)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                update_short_field(s_id, 'publish_date', dialog.selected_date_str)
                
        self.update_table()

    def edit_url(self, s_id, h_id, h_name):
        url = next((u[2] for u in get_short_uploads(s_id) if u[0] == h_id), "")
        new_u, ok = QInputDialog.getText(self, f"{_('lbl_link')}: {h_name}", f"{_('lbl_enter_link')}:", QLineEdit.EchoMode.Normal, url)
        if ok:
            update_short_url(s_id, h_id, new_u.strip())
            self.update_table()