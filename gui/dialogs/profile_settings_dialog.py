import os
import uuid
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget, 
                             QPushButton, QLabel, QLineEdit, QFileDialog, QMessageBox, QWidget,
                             QTabWidget, QTextEdit, QFormLayout, QPlainTextEdit)
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPainterPath
from PyQt6.QtCore import Qt
from database import APP_DATA_DIR
from core.config import _

class ProfileSettingsDialog(QDialog):
    def __init__(self, parent, profile_manager):
        super().__init__(parent)
        self.pm = profile_manager
        self.setWindowTitle(_("title_profile_settings"))
        self.resize(640, 480)
        
        self.current_id = None
        self.pending_avatar = None # Хранит путь к новой выбранной картинке до сохранения
        self.is_creating_new = False
        
        self.setup_ui()
        self.load_profiles_list()
        
    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        
        # --- ЛЕВАЯ ПАНЕЛЬ (Список профилей) ---
        left_layout = QVBoxLayout()
        
        self.profile_list = QListWidget()
        self.profile_list.itemSelectionChanged.connect(self.on_profile_selected)
        left_layout.addWidget(self.profile_list)
        
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton(f"➕ {_('btn_add')}")
        self.btn_add.clicked.connect(self.start_new_profile)
        self.btn_del = QPushButton(f"🗑 {_('btn_delete')}")
        self.btn_del.clicked.connect(self.delete_current_profile)
        
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_del)
        left_layout.addLayout(btn_layout)
        
        # --- ПРАВАЯ ПАНЕЛЬ (Редактор) ---
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #3a3a3a; border-radius: 4px; }
            QTabBar::tab { 
                background: #2a2a2a; 
                color: #ffffff; 
                padding: 8px 16px; 
                margin-right: 2px; 
                border-top-left-radius: 4px; 
                border-top-right-radius: 4px; 
            }
            QTabBar::tab:selected { 
                background: #4CAF50; 
                font-weight: bold; 
            }
            QTabBar::tab:hover:!selected { background: #3a3a3a; }
        """)
        
        # --- ВКЛАДКА 1: Основные настройки ---
        tab_general = QWidget()
        general_layout = QVBoxLayout(tab_general)
        general_layout.setContentsMargins(15, 15, 15, 15)

        # Создаем форму для выравнивания в строку
        form_layout = QFormLayout()
        form_layout.setSpacing(15) # Отступы между строками
        
        # Аватарка
        avatar_layout = QHBoxLayout()
        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(64, 64)
        self.set_avatar_pixmap("") 
        
        self.btn_browse_avatar = QPushButton(_("btn_browse"))
        self.btn_browse_avatar.clicked.connect(self.choose_avatar)
        
        avatar_layout.addWidget(self.avatar_label)
        avatar_layout.addWidget(self.btn_browse_avatar)
        avatar_layout.addStretch()
        form_layout.addRow(avatar_layout)
        
        # Поля данных
        self.input_name = QLineEdit()
        self.input_name.setMaxLength(25)
        form_layout.addRow(_("lbl_profile_name"), self.input_name)
        
        self.input_id = QLineEdit()
        self.input_id.setReadOnly(True)
        self.input_id.setStyleSheet("background-color: #f0f0f0; color: #555;")
        form_layout.addRow(_("lbl_profile_id"), self.input_id)

        general_layout.addLayout(form_layout)
        
        general_layout.addStretch()

        # --- ВКЛАДКА 2: Шаблоны и Метаданные ---
        tab_meta = QWidget()
        meta_layout = QVBoxLayout(tab_meta)
        meta_layout.setContentsMargins(15, 15, 15, 15)
        
        meta_layout.addWidget(QLabel(_("lbl_channel_global_links")))
        self.input_channel_links = QPlainTextEdit()
        self.input_channel_links.setPlaceholderText(f"{_('txt_example')}\n{_('placeholder_channel_links')}")
        self.input_channel_links.setMinimumHeight(100)
        meta_layout.addWidget(self.input_channel_links)
        
        meta_layout.addWidget(QLabel(_("lbl_channel_default_desc")))
        self.input_global_desc = QPlainTextEdit()
        self.input_global_desc.setPlaceholderText(f"{_('txt_example')}\n{_('placeholder_global_desc')}")
        self.input_global_desc.setMinimumHeight(100)
        meta_layout.addWidget(self.input_global_desc)

        # Добавляем вкладки в виджет
        self.tabs.addTab(tab_general, _("tab_general"))
        self.tabs.addTab(tab_meta, _("tab_channel_data"))

        right_layout.addWidget(self.tabs)
        
        # Кнопка сохранения
        self.btn_save = QPushButton(f"💾 {_('btn_save_changes')}")
        self.btn_save.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px;")
        self.btn_save.clicked.connect(self.save_profile)
        right_layout.addWidget(self.btn_save)
        
        main_layout.addLayout(left_layout, 1)
        main_layout.addWidget(self.right_panel, 2)
        
        self.right_panel.setEnabled(False) # Выключена, пока ничего не выбрано

    def set_avatar_pixmap(self, image_path):
        # """Отрисовывает аватар 64x64 со скругленными краями (squircle)"""
        size = 64
        radius = 16 
        
        target = QPixmap(size, size)
        target.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(target)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        path = QPainterPath()
        path.addRoundedRect(0, 0, size, size, radius, radius)
        painter.setClipPath(path)
        
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            # Масштабируем, если исходник не ровно 64x64
            pixmap = pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap(0, 0, pixmap)
        else:
            # Заглушка
            painter.fillRect(0, 0, size, size, Qt.GlobalColor.lightGray)
            
        painter.end()
        self.avatar_label.setPixmap(target)

    def load_profiles_list(self):
        self.profile_list.blockSignals(True)
        self.profile_list.clear()
        
        # Получаем ID профиля, под которым мы сейчас сидим
        active_profile_id = self.pm.data.get("last_used_profile", "default")
        item_to_select = None
        
        profiles = self.pm.get_all_profiles()
        for p_id, p_data in profiles.items():
            display_name = f"{p_data['name']} ({_('txt_default')})" if p_id == "default" else p_data['name']
            
            from PyQt6.QtWidgets import QListWidgetItem
            item = QListWidgetItem(display_name)
            item.setData(Qt.ItemDataRole.UserRole, p_id)
            self.profile_list.addItem(item)
            
            # Находим нужный элемент, но пока не выделяем
            if p_id == active_profile_id:
                item_to_select = item
                
        self.profile_list.blockSignals(False)
        
        # Выполняем выделение ПОСЛЕ включения сигналов. 
        # Это автоматически вызовет сигнал itemSelectionChanged и загрузит правую панель.
        if item_to_select:
            self.profile_list.setCurrentItem(item_to_select)

    def on_profile_selected(self):
        items = self.profile_list.selectedItems()
        if not items:
            self.right_panel.setEnabled(False)
            return
            
        self.is_creating_new = False
        self.pending_avatar = None
        self.right_panel.setEnabled(True)
        
        p_id = items[0].data(Qt.ItemDataRole.UserRole)
        p_data = self.pm.get_profile(p_id)
        
        self.current_id = p_id
        self.input_id.setText(p_id)
        self.input_name.setText(p_data["name"])
        self.set_avatar_pixmap(p_data.get("avatar_path", ""))

        # Загружаем метаданные (если их нет, вернется пустая строка)
        self.input_channel_links.setPlainText(p_data.get("channel_links", ""))
        self.input_global_desc.setPlainText(p_data.get("global_desc", ""))
        
        # Профиль по умолчанию нельзя переименовать или удалить
        is_default = (p_id == "default")
        self.input_name.setReadOnly(is_default)
        self.btn_del.setEnabled(not is_default)

    def start_new_profile(self):
        # """Инициирует добавление нового профиля (показывает ID, ждет сохранения)"""
        self.profile_list.clearSelection()
        self.right_panel.setEnabled(True)
        
        self.is_creating_new = True
        self.pending_avatar = None
        self.current_id = self.pm.generate_profile_id()
        
        self.input_id.setText(self.current_id)
        self.input_name.setText("")
        self.input_name.setReadOnly(False)
        self.set_avatar_pixmap("")

    def choose_avatar(self):
        file_path, _ = QFileDialog.getOpenFileName(self, _("msg_choose_avatar"), "", f"{_('filter_images')} (*.png *.jpg *.jpeg)")
        if not file_path: return
        
        # 1. Проверка веса (до 2.5 Мб)
        max_size = 2.5 * 1024 * 1024
        if os.path.getsize(file_path) > max_size:
            QMessageBox.warning(self, _("msg_title_error"), _("msg_profile_error_filesize"))
            return
            
        img = QImage(file_path)
        if img.isNull():
            QMessageBox.warning(self, _("msg_title_error"), _("msg_profile_error_read_image"))
            return
            
        # 2. Проверка разрешения (до 1024x1024)
        if img.width() > 1024 or img.height() > 1024:
            QMessageBox.warning(self, _("msg_title_error"), f"{_('msg_profile_error_image_too_big')} ({img.width()}x{img.height()}). {_('msg_profile_image_size')}")
            return
            
        # 3. Проверка соотношения сторон 1:1
        if img.width() != img.height():
            QMessageBox.warning(self, _("msg_title_error"), _("msg_profile_error_image_must_be_square"))
            return
            
        self.pending_avatar = file_path
        self.set_avatar_pixmap(file_path) # Временный предпросмотр

    def save_profile(self):
        name = self.input_name.text().strip()
        channel_links = self.input_channel_links.toPlainText().strip()
        global_desc = self.input_global_desc.toPlainText().strip()

        if not name:
            QMessageBox.warning(self, _("msg_title_error"), _("msg_profile_error_empty_name"))
            return
            
        # Физическое сохранение аватара (сжатие до 128x128)
        final_avatar_path = ""
        if self.pending_avatar:
            img = QImage(self.pending_avatar)
            scaled_img = img.scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            final_avatar_path = os.path.join(APP_DATA_DIR, f"avatar_{self.current_id}.jpg")
            scaled_img.save(final_avatar_path, "JPG", 90)
        elif not self.is_creating_new:
            # Если мы редактируем и не меняли аватар, оставляем старый путь
            old_data = self.pm.get_profile(self.current_id)
            final_avatar_path = old_data.get("avatar_path", "")

        if self.is_creating_new:
            self.pm.add_profile_with_id(self.current_id, name, final_avatar_path)
        else:
            self.pm.edit_profile(self.current_id, name=name, avatar_path=final_avatar_path)
            
        # Записываем текстовые поля напрямую в словарь профиля и сохраняем на диск
        if self.current_id in self.pm.data.get("profiles", {}):
            self.pm.data["profiles"][self.current_id]["channel_links"] = channel_links
            self.pm.data["profiles"][self.current_id]["global_desc"] = global_desc
            self.pm.save()

        self.pending_avatar = None
        self.load_profiles_list()
        
        # Выделяем только что сохраненный профиль
        for i in range(self.profile_list.count()):
            item = self.profile_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == self.current_id:
                item.setSelected(True)
                break
                
        QMessageBox.information(self, _("msg_title_success"), _("msg_profile_success_profile_saved"))

    def delete_current_profile(self):
        if not self.current_id or self.current_id == "default": return
        
        # --- ЗАЩИТА ОТ УДАЛЕНИЯ АКТИВНОГО ПРОФИЛЯ ---
        active_profile_id = self.pm.data.get("last_used_profile")
        if self.current_id == active_profile_id:
            QMessageBox.warning(self, _("msg_profile_action_blocked"), 
                _("msg_profile_cant_delete_active_profile"))
            return
        # --------------------------------------------
        
        reply = QMessageBox.question(self, _("msg_title_warning"), 
            f"{_('msg_profile_sure_to_delete_profile')} '{self.input_name.text()}'?\n\n{_('msg_profile_all_data_will_deleted')}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
        if reply == QMessageBox.StandardButton.Yes:
            self.pm.delete_profile(self.current_id)
            self.load_profiles_list()
            self.right_panel.setEnabled(False)