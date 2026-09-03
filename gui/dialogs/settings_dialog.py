from PyQt6.QtWidgets import QDialog, QFormLayout, QComboBox, QHBoxLayout, QLineEdit, QPushButton, QFileDialog
from core.config import _, save_config
from gui.dialogs.manage_hostings_dialog import ManageHostingsDialog

class SettingsDialog(QDialog):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.setWindowTitle(_("title_settings"))
        self.resize(500, 150)
        self.config = config

        layout = QFormLayout(self)

        self.lang_selector = QComboBox()
        self.lang_selector.addItem("Русский", userData="ru_ru")
        self.lang_selector.addItem("English", userData="en_us")
        
        current_lang = self.config.get("language", "ru_ru")
        index = self.lang_selector.findData(current_lang)
        if index >= 0:
            self.lang_selector.setCurrentIndex(index)
            
        layout.addRow("Язык / Language:", self.lang_selector)

        recordings_layout = QHBoxLayout()
        self.recordings_input = QLineEdit(self.config.get("recordings_folder", ""))
        rec_btn = QPushButton(_("btn_browse", "Обзор"))
        rec_btn.clicked.connect(lambda: self.browse_folder(self.recordings_input))
        recordings_layout.addWidget(self.recordings_input)
        recordings_layout.addWidget(rec_btn)
        layout.addRow(_("lbl_video_source_folder"), recordings_layout)

        renders_layout = QHBoxLayout()
        self.renders_input = QLineEdit(self.config.get("renders_folder", ""))
        ren_btn = QPushButton(_("btn_browse", "Обзор"))
        ren_btn.clicked.connect(lambda: self.browse_folder(self.renders_input))
        renders_layout.addWidget(self.renders_input)
        renders_layout.addWidget(ren_btn)
        layout.addRow(_("lbl_video_render_folder"), renders_layout)

        text_editor_layout = QHBoxLayout()
        self.text_editor_input = QLineEdit(self.config.get("notepad_path", "notepad.exe"))
        text_editor_btn = QPushButton(_("btn_browse"))
        text_editor_btn.clicked.connect(self.browse_text_editor)
        text_editor_layout.addWidget(self.text_editor_input)
        text_editor_layout.addWidget(text_editor_btn)
        layout.addRow(_("lbl_text_editor"), text_editor_layout)

        gimp_layout = QHBoxLayout()
        self.gimp_input = QLineEdit(self.config.get("gimp_path", ""))
        gimp_btn = QPushButton(_("btn_browse"))
        gimp_btn.clicked.connect(self.browse_gimp)
        gimp_layout.addWidget(self.gimp_input)
        gimp_layout.addWidget(gimp_btn)
        layout.addRow(_("lbl_gimp_path"), gimp_layout)

        video_editor_layout = QHBoxLayout()
        self.video_editor_input = QLineEdit(self.config.get("video_editor_path", ""))
        video_editor_btn = QPushButton("Обзор")
        video_editor_btn.clicked.connect(self.browse_video_editor)
        video_editor_layout.addWidget(self.video_editor_input)
        video_editor_layout.addWidget(video_editor_btn)
        layout.addRow(f"{_('lbl_videoeditor')} (.exe):", video_editor_layout)

        self.desc_input = QLineEdit(self.config.get("desc_name", "desc.txt"))
        layout.addRow(_("lbl_desc_filename"), self.desc_input)

        self.prev_input = QLineEdit(self.config.get("preview_name", "preview.jpg"))
        layout.addRow(_("lbl_preview_filename"), self.prev_input)

        hostings_btn = QPushButton(_("btn_videohosting_manager"))
        hostings_btn.clicked.connect(self.open_manage_hostings)
        layout.addRow(hostings_btn)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton(_("btn_save"))
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton(_("btn_cancel"))
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

    def browse_gimp(self):
        file, ignored = QFileDialog.getOpenFileName(self, _("title_select_gimp"), "", "Executable Files (*.exe)")
        if file:
            self.gimp_input.setText(file)

    def browse_text_editor(self):
        file, ignored = QFileDialog.getOpenFileName(self, _("title_select_editor"), "", "Executable Files (*.exe)")
        if file:
            self.text_editor_input.setText(file)

    def browse_video_editor(self):
        file, ignored = QFileDialog.getOpenFileName(self, _("lbl_select_videoeditor_exe"), "", "Executable (*.exe)")
        if file:
            self.video_editor_input.setText(file)

    def open_manage_hostings(self):
        dialog = ManageHostingsDialog(self)
        dialog.exec()

    def browse_folder(self, line_edit):
        folder = QFileDialog.getExistingDirectory(self, _("lbl_select_folder"))
        if folder:
            line_edit.setText(folder)

    def accept(self):
        self.config["language"] = self.lang_selector.currentData()
        self.config["recordings_folder"] = self.recordings_input.text().strip()
        self.config["renders_folder"] = self.renders_input.text().strip()
        self.config["notepad_path"] = self.text_editor_input.text().strip()
        self.config["gimp_path"] = self.gimp_input.text().strip()
        self.config["video_editor_path"] = self.video_editor_input.text().strip()
        self.config["desc_name"] = self.desc_input.text().strip()
        self.config["preview_name"] = self.prev_input.text().strip()

        save_config(self.config)
        super().accept()