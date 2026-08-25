import sqlite3
import logging

def apply_migrations(db_path, old_version, new_version):
    """
    Применяет миграции к базе данных в зависимости от версии.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # --- МИГРАЦИЯ ДО ВЕРСИИ 0.3 ---
        if old_version < "0.3":
            logging.info(f"Запуск обновления БД: с {old_version} до 0.3...")
            
            # Получаем список существующих колонок в таблице games
            cursor.execute("PRAGMA table_info(games)")
            columns = [row[1] for row in cursor.fetchall()]
            
            # Добавляем новые колонки, если их еще нет (Пункт 2 из ваших задач)
            if "ai_url" not in columns:
                cursor.execute("ALTER TABLE games ADD COLUMN ai_url TEXT DEFAULT ''")
            if "steam_id" not in columns:
                cursor.execute("ALTER TABLE games ADD COLUMN steam_id TEXT DEFAULT ''")
            if "release_date" not in columns:
                cursor.execute("ALTER TABLE games ADD COLUMN release_date TEXT DEFAULT ''")
                
            conn.commit()
            logging.info("База данных успешно обновлена до версии 0.3")
            
        # В будущем здесь будут блоки: if old_version < "0.4": ...

    except Exception as e:
        logging.error(f"Критическая ошибка при обновлении БД: {e}")
        conn.rollback() # Откатываем изменения в случае сбоя
    finally:
        conn.close()