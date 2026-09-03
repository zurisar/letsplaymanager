import sys
from PyQt6.QtWidgets import QApplication

# Подтягиваем базовые настройки
from core.config import setup_logging, handle_exception
from database import init_db

# Подтягиваем главное окно
from gui.main_window import LetsPlayManager

def main():
    # 1. Перехват ошибок и логирование
    sys.excepthook = handle_exception
    setup_logging()

    # 2. Инициализация и обновление базы данных
    init_db()

    # 3. Запуск графического интерфейса
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = LetsPlayManager()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()