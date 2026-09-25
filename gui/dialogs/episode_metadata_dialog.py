import os
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QVBoxLayout, QFormLayout, 
                             QLineEdit, QTextEdit, QTextBrowser, QPushButton, 
                             QLabel, QWidget, QApplication, QComboBox)
from PyQt6.QtCore import Qt
from core.config import _

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

    def update_preview(self):
        # 1. Расчет длины заголовка
        ep_title = self.title_input.text().strip()
        
        # Формируем название с разделителем, если введено уникальное имя
        if ep_title:
            full_title = f"{ep_title} | {self.game_name} - {_('lbl_episode')} {self.ep_number}"
        else:
            full_title = f"{self.game_name} | {_('lbl_episode')} {self.ep_number}"
            
        char_count = len(full_title)
        
        # Окрашиваем счетчик в красный, если превышен лимит хостингов
        color = "#d32f2f" if char_count > 100 else "#888888"
        self.counter_label.setText(f'<span style="color:{color};">{char_count}/{_('lbl_100_symbols')}</span>')
        
        # 2. Сборка тела описания
        desc = self.desc_input.toPlainText().strip()
        timecodes = self.timecodes_input.toPlainText().strip()
        ep_tags = self.tags_input.text().strip()

        # --- Читаем реальные ключи из БД и Профиля ---     
        current_platform_key = self.platform_selector.currentData()   
        
        game_desc = self.game_data.get("desc_template", "")
        playlists = self.game_data.get("playlists", {})
        game_playlist = playlists.get(current_platform_key, "")
        game_tags = self.game_data.get("default_tags", "")
        
        profile_links = self.profile_data.get("channel_links", "")
        profile_cta = self.profile_data.get("global_desc", "")
             
        # Используем HTML для красивого предпросмотра (при копировании будет Plain Text)
        preview_html = f"<b>{_('lbl_title_upper')}:</b><br><span style='color: #4CAF50;'>{full_title}</span><br><br>"
        preview_html += f"<b>{_('lbl_description_upper')}:</b><br>"
        if desc: preview_html += f"{desc}<br><br>"
        preview_html += f"{game_desc.replace(chr(10), '<br>')}<br><br>"

        if timecodes:
            preview_html += f"⏱️ <b>{_('lbl_timecodes')}:</b><br>{timecodes.replace(chr(10), '<br>')}<br><br>"

        preview_html += f"🔗 <b>{_('lbl_links')}:</b><br>{_('lbl_playlist')}: {game_playlist}<br>"
        preview_html += f"{profile_links.replace(chr(10), '<br>')}<br><br>"
        preview_html += f"{profile_cta.replace(chr(10), '<br>')}<br><br>"
        
        # Склейка и фильтрация тегов (убираем дубли и пустые)
        # Объединяем теги игры и эпизода, заменяем запятые на пробелы и разбиваем
        combined_tags = f"{game_tags} {ep_tags}".replace(',', ' ')
        all_tags = [t.strip() for t in combined_tags.split() if t.strip()]
        unique_tags = " ".join(list(dict.fromkeys(all_tags)))
        preview_html += f"<span style='color: #2196F3;'>{unique_tags}</span>"
        
        self.preview_browser.setHtml(preview_html)
        
    def copy_to_clipboard(self, mode):
        # 1. Собираем базовые сырые данные
        desc = self.desc_input.toPlainText().strip()
        timecodes = self.timecodes_input.toPlainText().strip()
        ep_tags = self.tags_input.text().strip()

        # Получаем ключ выбранной платформы (например, 'youtube' или 'rutube')
        current_platform_key = self.platform_selector.currentData()
        
        game_desc = self.game_data.get("desc_template", "")
        playlists = self.game_data.get("playlists", {})
        game_playlist = playlists.get(current_platform_key, "")
        game_tags = self.game_data.get("default_tags", "")
        
        profile_links = self.profile_data.get("channel_links", "")
        profile_cta = self.profile_data.get("global_desc", "")
        
        # Объединяем теги игры и эпизода, заменяем запятые на пробелы и разбиваем
        combined_tags = f"{game_tags} {ep_tags}".replace(',', ' ')
        all_tags = [t.strip() for t in combined_tags.split() if t.strip()]
        unique_tags = " ".join(list(dict.fromkeys(all_tags)))
        unique_tags = " ".join(list(dict.fromkeys(all_tags))) 
        
        text_to_copy = ""
        
        # 2. Формируем текст в зависимости от режима
        if mode == "video":
            parts = []
            if desc: parts.append(desc)
            if game_desc: parts.append(game_desc)
            if timecodes: parts.append(f"⏱️ {_('lbl_timecodes')}:\n{timecodes}")

            links_part = []
            if game_playlist: links_part.append(f"{_('lbl_playlist')}: {game_playlist}")
            if profile_links: links_part.append(profile_links)
            if links_part: parts.append(f"🔗 {_('lbl_links')}:\n" + "\n".join(links_part))
            
            if profile_cta: parts.append(profile_cta)
            if unique_tags: parts.append(unique_tags)
            
            text_to_copy = "\n\n".join(parts)
            
        elif mode == "shorts":
            # Для Shorts: описание игры и ссылки. Без таймкодов и тегов (они уходят в заголовок)
            parts = []
            if game_desc: parts.append(game_desc)
            
            links_part = []
            if game_playlist: links_part.append(f"{_('lbl_playlist')}: {game_playlist}")
            if profile_links: links_part.append(profile_links)
            if links_part: parts.append(f"🔗 {_('lbl_links')}:\n" + "\n".join(links_part))
            
            if profile_cta: parts.append(profile_cta)
            
            text_to_copy = "\n\n".join(parts)
            
        elif mode == "ai":
            # Промпт для нейросети
            base_tags_phrase = f"Мои стандартные теги: {unique_tags}. Их дублировать не нужно." if unique_tags else ""
            
            text_to_copy = (
                f"Я записываю летсплей по игре {self.game_name}. "
                f"В этой серии (эпизод {self.ep_number}) произошло следующее:\n{desc}\n\n"
                f"1. Сгенерируй 5 вариантов кликбейтных названий для YouTube (строго до 100 символов каждое).\n"
                f"2. Напиши короткое привлекательное SEO-описание.\n"
                f"3. Предложи 5-7 новых уникальных хештегов, которые подходят ИМЕННО к событиям этой серии. {base_tags_phrase}"
            )
            
        # 3. Отправляем в буфер обмена
        clipboard = QApplication.clipboard()
        clipboard.setText(text_to_copy)
            
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