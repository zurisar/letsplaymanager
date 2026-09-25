from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt
from core.config import _, APP_VERSION

class AboutDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(_("menu_about"))
        self.setFixedSize(450, 250)
        
        layout = QVBoxLayout(self)
        
        info_label = QLabel()
        info_label.setTextFormat(Qt.TextFormat.RichText)
        info_label.setOpenExternalLinks(True) 
        info_label.setWordWrap(True)
        
        # Получаем текущую тему из родительского окна (main_window)
        current_theme = parent.config.get("theme", "dark") if hasattr(parent, 'config') else "dark"
        
        # Подбираем контрастные цвета
        header_color = "#ffffff" if current_theme == "dark" else "#2c3e50"
        link_color = "#5dade2" if current_theme == "dark" else "#2980b9" # Более светлый синий для ссылок
        
        text = f"""
        <h2 style='text-align: center; color: {header_color};'>LetsPlayManager v{APP_VERSION}</h2>
        <p style='text-align: center;'>{_('about_desc')}</p>
        <hr>
        <p><b>{_('about_features_title')}:</b><br>
        {_('about_features_text')}</p>
        <p><b>{_('about_links_title')}:</b><br>
        🐙 <a href='https://github.com/zurisar/letsplaymanager' style='color: {link_color};'>{_('about_github')}</a><br>
        🟦 <a href='https://vk.ru/zarubagames' style='color: {link_color};'>{_('about_vk')}</a></p>
        <br>
        <p style='text-align: center; font-size: 10px; color: gray;'>{_('about_footer')}</p>
        """
        
        info_label.setText(text)
        layout.addWidget(info_label)
        
        btn_layout = QHBoxLayout()
        close_btn = QPushButton(_("btn_close"))
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)