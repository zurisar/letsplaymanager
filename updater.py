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

        # --- МИГРАЦИЯ ДО ВЕРСИИ 0.4 ---
        if old_version < "0.4":
            logging.info(f"Запуск обновления БД: с {old_version} до 0.4...")
            cursor.execute("PRAGMA table_info(episodes)")
            columns = [row[1] for row in cursor.fetchall()]
            if "publish_date" not in columns:
                cursor.execute("ALTER TABLE episodes ADD COLUMN publish_date TEXT DEFAULT ''")
            conn.commit()

        # --- МИГРАЦИЯ ДО ВЕРСИИ 0.5 (Шортсы) ---
        if old_version < "0.5":
            logging.info(f"Запуск обновления БД: с {old_version} до 0.5 (Создание таблиц Shorts)...")
            # Просто вызываем init_db, так как мы добавили туда IF NOT EXISTS
            from database import init_db
            init_db()

        # --- МИГРАЦИЯ ДО ВЕРСИИ 0.7 (Шаблоны и метаданные) ---
        if old_version < "0.7":
            logging.info(f"Запуск обновления БД: с {old_version} до 0.7...")

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS game_playlists (
                    game_id INTEGER,
                    videohosting_id INTEGER,
                    playlist_url TEXT,
                    PRIMARY KEY (game_id, videohosting_id),
                    FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE,
                    FOREIGN KEY(videohosting_id) REFERENCES videohostings(id) ON DELETE CASCADE
                )
            ''')
            
            # Проверяем колонки в games
            cursor.execute("PRAGMA table_info(games)")
            game_cols = [row[1] for row in cursor.fetchall()]
            if "desc_template" not in game_cols:
                cursor.execute("ALTER TABLE games ADD COLUMN desc_template TEXT DEFAULT ''")
            if "default_tags" not in game_cols:
                cursor.execute("ALTER TABLE games ADD COLUMN default_tags TEXT DEFAULT ''")
                
            # Проверяем колонки в episodes
            cursor.execute("PRAGMA table_info(episodes)")
            ep_cols = [row[1] for row in cursor.fetchall()]
            if "custom_title" not in ep_cols:
                cursor.execute("ALTER TABLE episodes ADD COLUMN custom_title TEXT DEFAULT ''")
            if "custom_desc" not in ep_cols:
                cursor.execute("ALTER TABLE episodes ADD COLUMN custom_desc TEXT DEFAULT ''")
            if "timecodes" not in ep_cols:
                cursor.execute("ALTER TABLE episodes ADD COLUMN timecodes TEXT DEFAULT ''")
            if "custom_tags" not in ep_cols:
                cursor.execute("ALTER TABLE episodes ADD COLUMN custom_tags TEXT DEFAULT ''")

            # Удаление временного столбца playlist_link (для локальной базы)
            try:
                cursor.execute("PRAGMA table_info(games)")
                game_cols = [row[1] for row in cursor.fetchall()]
                if "playlist_link" in game_cols:
                    cursor.execute("ALTER TABLE games DROP COLUMN playlist_link")
                    logging.info("Столбец playlist_link успешно удален.")
            except Exception as e:
                logging.warning(f"Пропуск удаления playlist_link: {e}")
                
            conn.commit()
            logging.info("База данных успешно обновлена до версии 0.7")

    except Exception as e:
        logging.error(f"Критическая ошибка при обновлении БД: {e}")
        conn.rollback() # Откатываем изменения в случае сбоя
    finally:
        conn.close()