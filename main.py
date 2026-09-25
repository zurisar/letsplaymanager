import sys
import os
import logging
from PyQt6.QtWidgets import QApplication, QDialog
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QTimer

# Подтягиваем базовые настройки
from core.profile_manager import ProfileManager
from core.config import setup_logging, handle_exception, load_config, BASE_DIR, apply_theme
from database import init_db, set_db_filename

# Подтягиваем главное окно
from gui.main_window import LetsPlayManager
from gui.splash_screen import FadeSplashScreen
from gui.dialogs.profile_selector_dialog import ProfileSelectorDialog

def main():
    # 1. Перехват ошибок и логирование
    sys.excepthook = handle_exception
    setup_logging()

    # 1.5 Показываем Splash Screen в первую очередь
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Применяем темную тему ДО показа сплеш-скрина и выбора профиля
    apply_theme(app, "dark")

    if getattr(sys, 'frozen', False):
        # Если это собранный exe, берем папку, где лежит сам .exe
        base_path = os.path.dirname(sys.executable)
    else:
        # Если запуск из исходников, используем BASE_DIR
        base_path = BASE_DIR
        
    splash_image_path = os.path.join(base_path, "assets", "letsplaymanager_title.jpg")
    icon_path = os.path.join(base_path, "assets", "icon.ico")
    
    # Устанавливаем иконку для всех окон приложения
    app.setWindowIcon(QIcon(icon_path))

    splash = FadeSplashScreen(splash_image_path)
    splash.show()
    
    # Принудительно отрисовываем окно до того, как начнем грузить базы
    app.processEvents()

    # 2. Загружаем реестр профилей
    logging.info(f"Запуск менеджера профилей")
    pm = ProfileManager()
    
    splash_active = True # Флаг для контроля заставки

    if len(pm.get_all_profiles()) > 1 and pm.data.get("show_selector_on_startup", True):
        # ВАЖНО: Убираем сплеш-скрин ДО вызова диалога, иначе он его перекроет
        splash.close()
        splash_active = False
        
        selector = ProfileSelectorDialog(pm)
        if selector.exec() == QDialog.DialogCode.Accepted:
            # Пользователь выбрал профиль, забираем обновленные данные
            current_profile, profile_id = pm.get_last_used_profile()
            logging.info(f"Выбран профиль: {current_profile}")
        else:
            # Пользователь закрыл окно выбора крестиком -> отменяем запуск
            sys.exit(0) 
    else:
        # Если профиль один, просто берем последний
        current_profile, profile_id = pm.get_last_used_profile()
        logging.info(f"Загружен стандартный профиль: {current_profile}")

    # 3. Инициализация и обновление базы данных
    set_db_filename(current_profile['db_file'])
    init_db()

    # 4. Загружаем конфигурацию конкретно для выбранного профиля
    config = load_config(current_profile['config_file'])

    # Переопределяем тему, если в настройках пользователя стоит "light"
    apply_theme(app, config.get("theme", "dark"))

    window = LetsPlayManager()

    # 5. Логика появления главного окна
    if splash_active:
        # Если диалога профилей не было, плавно растворяем заставку
        def start_fade():
            window.center_on_screen()
            window.show()
            splash.fade_out(duration=500)
        
        QTimer.singleShot(500, start_fade)
    else:
        # Если диалог профилей был, заставки уже нет, просто показываем окно
        window.center_on_screen()
        window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()