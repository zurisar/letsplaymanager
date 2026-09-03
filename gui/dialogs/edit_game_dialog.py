from PyQt6.QtWidgets import QDialog, QFormLayout, QLineEdit, QHBoxLayout, QPushButton

class EditGameDialog(QDialog):
    def __init__(self, parent, game_name, game_data):
        super().__init__(parent)
        self.setWindowTitle(f"Редактирование: {game_name}")
        self.resize(500, 150)
        
        layout = QFormLayout(self)

        self.name_input = QLineEdit(game_name)
        layout.addRow("Название игры:", self.name_input)

        self.ai_url_input = QLineEdit(game_data.get('ai_url', ''))
        self.ai_url_input.setPlaceholderText("https://chatgpt.com/...")
        layout.addRow("Ссылка на ИИ-чат:", self.ai_url_input)

        self.steam_input = QLineEdit(game_data.get('steam_id', ''))
        self.steam_input.setPlaceholderText("Например: 108600")
        layout.addRow("Steam ID:", self.steam_input)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("💾 Сохранить изменения")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)