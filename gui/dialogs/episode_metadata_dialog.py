import os
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QVBoxLayout, QFormLayout, 
                             QLineEdit, QTextEdit, QTextBrowser, QPushButton, 
                             QLabel, QWidget, QApplication, QComboBox)
from PyQt6.QtCore import Qt
from core.config import _
from core.templates import TemplateManager

class EpisodeMetadataDialog(QDialog):
    def __init__(self, parent, game_name, ep_number, game_data=None, profile_data=None, episode_data=None, hostings=None):
        super().__init__(parent)
        self.game_name = game_name
        self.ep_number = ep_number
        
        # Реальные данные
        self.game_data = game_data or {}
        self.profile_data = profile_data or {}
        self.episode_data = episode_data or ('', '', '', '') # (title, desc, timecodes, tags)

        self.hostings = hostings or [("youtube", "YouTube"), ("rutube", "RuTube")]
        
        self.setWindowTitle(_("title_episode_metadata"))
        self.resize(1100, 700) # Окно делаем широким, чтобы превью не сжималось
        
        self.setup_ui()
        self.load_initial_data() # Подгружаем сохраненный текст в поля
        self.update_preview() # Сразу генерируем текст при открытии

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        
        # ================= ЛЕВАЯ ПАНЕЛЬ (ВВОД) =================
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 15, 0)
        
        form_layout = QFormLayout()
        form_layout.setSpacing(15)
        
        # 1. Уникальное название
        self.title_input = QLineEdit()
        self.title_input.textChanged.connect(self.update_preview)
        form_layout.addRow(_("lbl_unique_title"), self.title_input)
        
        # Динамический счетчик символов
        self.counter_label = QLabel()
        self.counter_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        form_layout.addRow("", self.counter_label)
        
        # 2. Описание серии
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText(_("placeholder_ep_desc"))
        self.desc_input.textChanged.connect(self.update_preview)
        form_layout.addRow(_("lbl_episode_desc"), self.desc_input)
        
        # 3. Таймкоды
        self.timecodes_input = QTextEdit()
        self.timecodes_input.setPlaceholderText(_("placeholder_timecodes"))
        self.timecodes_input.textChanged.connect(self.update_preview)
        form_layout.addRow(_("lbl_timecodes"), self.timecodes_input)
        
        # 4. Хештеги серии
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText(_("placeholder_tags"))
        self.tags_input.textChanged.connect(self.update_preview)
        form_layout.addRow(_("lbl_episode_tags"), self.tags_input)
        
        left_layout.addLayout(form_layout)
        
        self.save_btn = QPushButton(f"💾 {_('btn_save_meta')}")
        self.save_btn.clicked.connect(self.accept)
        left_layout.addWidget(self.save_btn)
        
        # ================= ПРАВАЯ ПАНЕЛЬ (ПРЕДПРОСМОТР) =================
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(15, 0, 0, 0)
        
        # --- 1. Аннотация ---
        hint_label = QLabel(_("lbl_copy_hint", "<i>Нажатие по кнопкам ниже копирует соответствующий текст в буфер обмена</i>"))
        hint_label.setTextFormat(Qt.TextFormat.RichText)
        hint_label.setStyleSheet("color: #888888; margin-bottom: 5px;")
        right_layout.addWidget(hint_label)

        # --- 2. Кнопка копирования названия (теперь ВЫШЕ предпросмотра) ---
        header_layout = QHBoxLayout()
        self.btn_copy_title = QPushButton(f"📋 {_('lbl_title')}")
        self.btn_copy_title.clicked.connect(self.copy_title_only)
        header_layout.addWidget(self.btn_copy_title)
        header_layout.addStretch() # Прижимаем кнопку влево, чтобы она не растягивалась на всю ширину
        right_layout.addLayout(header_layout)

        # Надпись Предпросмотр
        right_layout.addWidget(QLabel(_("lbl_preview")))        
        
        # Используем QTextBrowser для режима "только чтение" с поддержкой форматирования
        self.preview_browser = QTextBrowser()
        self.preview_browser.setStyleSheet("""
            QTextBrowser {
                background-color: #1e1e1e; 
                color: #e0e0e0; 
                border: 1px solid #3a3a3a; 
                border-radius: 4px;
                padding: 10px;
                font-size: 13px; 
                font-family: Consolas, monospace;
            }
        """)
        right_layout.addWidget(self.preview_browser)
        
        # --- 3. Нижняя панель (Видеохостинг + Кнопки) ---
        bottom_layout = QHBoxLayout()
        
        # Логический блок селектора платформы (Объединяем надпись и список)
        hosting_layout = QHBoxLayout()
        hosting_layout.setSpacing(8) # Минимальное расстояние между надписью и списком
        hosting_layout.addWidget(QLabel(_("lbl_videohosting")))
        
        self.platform_selector = QComboBox()
        for key, display_name in self.hostings:
            self.platform_selector.addItem(display_name, userData=key)
        self.platform_selector.currentIndexChanged.connect(self.update_preview)
        hosting_layout.addWidget(self.platform_selector)
        
        # Добавляем блок хостинга в нижнюю строку
        bottom_layout.addLayout(hosting_layout)
        
        # Визуальный разделитель между селектором хостинга и кнопками копирования
        bottom_layout.addSpacing(20)

        # Кнопки копирования текста
        self.btn_copy_video = QPushButton(f"📋 {_('btn_copy_video')}")
        self.btn_copy_shorts = QPushButton(f"📱 {_('btn_copy_shorts')}")
        self.btn_copy_ai = QPushButton(f"🤖 {_('btn_copy_ai')}")
        
        self.btn_copy_video.clicked.connect(lambda: self.copy_to_clipboard("video"))
        self.btn_copy_shorts.clicked.connect(lambda: self.copy_to_clipboard("shorts"))
        self.btn_copy_ai.clicked.connect(lambda: self.copy_to_clipboard("ai"))
        
        bottom_layout.addWidget(self.btn_copy_video)
        bottom_layout.addWidget(self.btn_copy_shorts)
        bottom_layout.addWidget(self.btn_copy_ai)
        
        right_layout.addLayout(bottom_layout)
        
        main_layout.addWidget(left_panel, stretch=1)
        main_layout.addWidget(right_panel, stretch=1)

    def _get_raw_data(self):
        """Единая точка сбора всех переменных для шаблонизатора"""
        current_platform_key = self.platform_selector.currentData()
        ep_tags = self.tags_input.text().strip()
        game_tags = self.game_data.get("default_tags", "")
        
        combined_tags = f"{game_tags} {ep_tags}".replace(',', ' ')
        all_tags = [t.strip() for t in combined_tags.split() if t.strip()]
        unique_tags = " ".join(list(dict.fromkeys(all_tags))) 
        
        return {
            "game_name": self.game_name,
            "ep_number": self.ep_number,
            "custom_title": self.title_input.text().strip(),
            "custom_desc": self.desc_input.toPlainText().strip(),
            "timecodes": self.timecodes_input.toPlainText().strip(),
            "unique_tags": unique_tags,
            "game_desc": self.game_data.get("desc_template", ""),
            "game_playlist": self.game_data.get("playlists", {}).get(current_platform_key, ""),
            "profile_links": self.profile_data.get("channel_links", ""),
            "profile_cta": self.profile_data.get("global_desc", "")
        }

    def update_preview(self):
        raw_data = self._get_raw_data()
        
        # Расчет длины заголовка для счетчика лимитов YouTube/RuTube
        ep_title = raw_data["custom_title"]
        if ep_title:
            full_title = f"{ep_title} | {self.game_name} - {_('lbl_episode')} {self.ep_number}"
        else:
            full_title = f"{self.game_name} | {_('lbl_episode')} {self.ep_number}"
            
        char_count = len(full_title)
        color = "#d32f2f" if char_count > 100 else "#888888"
        self.counter_label.setText(f'<span style="color:{color};">{char_count}/{_("lbl_100_symbols")}</span>')
        
        # Сборка финального текста через шаблонизатор
        if hasattr(self.parent(), 'config'):
            tm = TemplateManager(self.parent().config)
            rendered_text = tm.render("publish_video.tpl", raw_data)
        else:
            rendered_text = "Ошибка: Конфигурация не найдена"
            
        # Форматирование для предпросмотра (замена переносов и подсветка тегов)
        html_text = rendered_text.replace('\n', '<br>')
        
        if raw_data["unique_tags"]:
            html_text = html_text.replace(
                raw_data["unique_tags"], 
                f"<span style='color: #2196F3;'>{raw_data['unique_tags']}</span>"
            )
            
        self.preview_browser.setHtml(html_text)
        
    def copy_to_clipboard(self, mode):
        raw_data = self._get_raw_data()
        
        if not hasattr(self.parent(), 'config'):
            return
            
        tm = TemplateManager(self.parent().config)
        
        # Формируем текст строго по выбранному .tpl файлу
        if mode == "video":
            text_to_copy = tm.render("publish_video.tpl", raw_data)
        elif mode == "shorts":
            text_to_copy = tm.render("publish_shorts.tpl", raw_data)
        elif mode == "ai":
            text_to_copy = tm.render("ai_prompt.tpl", raw_data)
        else:
            text_to_copy = ""
            
        QApplication.clipboard().setText(text_to_copy)
    
    def get_data(self):
        return {
            "custom_title": self.title_input.text().strip(),
            "custom_desc": self.desc_input.toPlainText().strip(),
            "timecodes": self.timecodes_input.toPlainText().strip(),
            "custom_tags": self.tags_input.text().strip()
        }
    
    def load_initial_data(self):
        """Заполняет поля ввода ранее сохраненными данными эпизода"""
        title, desc, timecodes, tags = self.episode_data
        
        # Блокируем сигналы, чтобы не вызывать перерисовку превью 4 раза подряд
        self.title_input.blockSignals(True)
        self.desc_input.blockSignals(True)
        self.timecodes_input.blockSignals(True)
        self.tags_input.blockSignals(True)
        
        self.title_input.setText(title)
        self.desc_input.setPlainText(desc)
        self.timecodes_input.setPlainText(timecodes)
        self.tags_input.setText(tags)
        
        self.title_input.blockSignals(False)
        self.desc_input.blockSignals(False)
        self.timecodes_input.blockSignals(False)
        self.tags_input.blockSignals(False)

    def copy_title_only(self):
        ep_title = self.title_input.text().strip()
        if ep_title:
            full_title = f"{ep_title} | {self.game_name} ({_('lbl_episode')} {self.ep_number})"
        else:
            full_title = f"{self.game_name} | Прохождение ({_('lbl_episode')} {self.ep_number})"
            
        QApplication.clipboard().setText(full_title)