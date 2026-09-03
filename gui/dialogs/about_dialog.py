from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt
from core.config import APP_VERSION

class AboutDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("О программе")
        self.setFixedSize(450, 250)
        
        layout = QVBoxLayout(self)
        
        info_label = QLabel()
        info_label.setTextFormat(Qt.TextFormat.RichText)
        info_label.setOpenExternalLinks(True) 
        info_label.setWordWrap(True)
        
        text = f"""
        <h2 style='text-align: center; color: #2c3e50;'>LetsPlayManager v{APP_VERSION}</h2>
        <p style='text-align: center;'>Умный инструмент для наведения порядка в исходниках и управления публикациями.</p>
        <hr>
        <p><b>Основные возможности:</b><br>
        Автоматизация перепаковки, управление метаданными и шортсами, планирование публикаций и интеграция с видеоредакторами.</p>
        <p><b>Следить за обновлениями:</b><br>
        🐙 <a href='https://github.com/zurisar/letsplaymanager' style='color: #2980b9;'>Исходный код на GitHub</a><br>
        🟦 <a href='https://vk.ru/zarubagames' style='color: #2980b9;'>Официальное сообщество VK</a></p>
        <br>
        <p style='text-align: center; font-size: 10px; color: gray;'>Разработано с душой для создателей контента.</p>
        """
        
        info_label.setText(text)
        layout.addWidget(info_label)
        
        btn_layout = QHBoxLayout()
        close_btn = QPushButton("Закрыть")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)