import os
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, 
                             QListWidget, QListWidgetItem, QWidget, QHBoxLayout)
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath, QCursor
from PyQt6.QtCore import Qt, QSize
from database import APP_DATA_DIR

class ProfileSelectorDialog(QDialog):
    def __init__(self, profile_manager, parent=None):
        super().__init__(parent)
        self.pm = profile_manager
        self.selected_profile_id = None
        
        self.setWindowTitle("Выберите профиль")
        # Делаем окно более узким и высоким, так как у нас теперь вертикальный список
        self.setFixedSize(450, 600) 
        self.setStyleSheet("background-color: #1e1e1e; color: #ffffff;")
        
        self.setup_ui()
        
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        
        title = QLabel("Кто сейчас работает?")
        title.setStyleSheet("font-size: 24px; font-weight: bold; margin-bottom: 20px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)
        
        # --- ВЕРТИКАЛЬНЫЙ СПИСОК ---
        self.list_widget = QListWidget()
        self.list_widget.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list_widget.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: transparent;
                outline: none;
            }
            QListWidget::item {
                background-color: #2a2a2a;
                border-radius: 12px;
                margin-bottom: 10px;
            }
            QListWidget::item:hover {
                background-color: #3a3a3a;
                border: 1px solid #4CAF50;
            }
            /* Скрываем стандартный синий фон выделения PyQt */
            QListWidget::item:selected {
                background-color: #3a3a3a;
                border: 1px solid #4CAF50;
                color: #ffffff;
            }
        """)
        
        self.populate_profiles()
        
        # Привязываем клик по элементу списка к нашей функции
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        main_layout.addWidget(self.list_widget)

    def populate_profiles(self):
        profiles = self.pm.get_all_profiles()
        
        for p_id, p_data in profiles.items():
            # 1. Увеличиваем высоту плашки до 120 пикселей
            item = QListWidgetItem(self.list_widget)
            item.setSizeHint(QSize(0, 120)) 
            item.setData(Qt.ItemDataRole.UserRole, p_id)
            
            row_widget = QWidget()
            row_widget.setStyleSheet("background-color: transparent;")
            row_layout = QHBoxLayout(row_widget)
            # 2. Выравниваем отступы: 20 слева/справа, 15 сверху/снизу (15+80+15 = 110)
            row_layout.setContentsMargins(20, 15, 20, 15)
            row_layout.setSpacing(20)
            
            # Аватарка (80x80)
            avatar_label = QLabel()
            avatar_label.setFixedSize(80, 80)
            pixmap = self.get_rounded_pixmap(p_data.get("avatar_path", ""))
            avatar_label.setPixmap(pixmap)
            
            # 3. Обработка длинных названий из старых сохранений
            display_name = p_data["name"]
            if len(display_name) > 25:
                display_name = display_name[:23] + "..."
                
            name_label = QLabel(display_name)
            name_label.setStyleSheet("font-size: 18px; font-weight: bold; background: transparent;")
            
            row_layout.addWidget(avatar_label)
            row_layout.addWidget(name_label)
            row_layout.addStretch() 
            
            self.list_widget.setItemWidget(item, row_widget)

    def get_rounded_pixmap(self, image_path):
        size = 80
        radius = 20
        
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
            pixmap = pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap(0, 0, pixmap)
        else:
            painter.fillRect(0, 0, size, size, Qt.GlobalColor.darkGray)
            
        painter.end()
        return target # Заметь, мы теперь возвращаем QPixmap, а не QIcon

    def on_item_clicked(self, item):
        p_id = item.data(Qt.ItemDataRole.UserRole)
        self.selected_profile_id = p_id
        self.pm.set_last_used(p_id) 
        self.accept()