import sqlite3
import os

# --- ИСПОЛЬЗУЕМ ПАПКУ "ДОКУМЕНТЫ" (Documents) ---
DOCUMENTS_DIR = os.path.join(os.path.expanduser('~'), 'Documents')
APP_DATA_DIR = os.path.join(DOCUMENTS_DIR, 'LetsPlayManager')

# Создаем папку, если ее нет
os.makedirs(APP_DATA_DIR, exist_ok=True)

# Теперь база лежит в Документах
DB_NAME = os.path.join(APP_DATA_DIR, "letsplay.db")

def init_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS videohostings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL
        )
    ''')

    # В новой версии (0.3) таблица games сразу создается с новыми полями
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            folder_path TEXT NOT NULL,
            ai_url TEXT DEFAULT '',
            steam_id TEXT DEFAULT '',
            release_date TEXT DEFAULT ''
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS episodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            number INTEGER NOT NULL,
            title TEXT DEFAULT '',
            has_desc BOOLEAN DEFAULT 0,
            has_preview BOOLEAN DEFAULT 0,
            file_size TEXT DEFAULT '0',
            duration TEXT DEFAULT '0',
            sources_deleted BOOLEAN DEFAULT 0,
            FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS episode_uploads (
            episode_id INTEGER,
            videohosting_id INTEGER,
            is_uploaded BOOLEAN DEFAULT 0,
            url TEXT DEFAULT '',
            PRIMARY KEY (episode_id, videohosting_id),
            FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE, 
            FOREIGN KEY (videohosting_id) REFERENCES videohostings(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute("INSERT OR IGNORE INTO videohostings (key, display_name) VALUES ('youtube', 'YouTube')")
    cursor.execute("INSERT OR IGNORE INTO videohostings (key, display_name) VALUES ('rutube', 'RuTube')")

    conn.commit()
    conn.close()
    print(f"База данных успешно инициализирована по пути: {DB_NAME}")

def add_game(name, folder_path, ai_url="", steam_id="", release_date=""):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO games (name, folder_path, ai_url, steam_id, release_date) 
        VALUES (?, ?, ?, ?, ?)
    ''', (name, folder_path, ai_url, steam_id, release_date))
    conn.commit()
    conn.close()

def get_games():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Теперь мы извлекаем еще и ai_url
    cursor.execute('SELECT id, name, folder_path, ai_url FROM games')
    games = cursor.fetchall()
    conn.close()
    return games

def update_game_ai_url(game_id, url):
    """Быстрое обновление ссылки на ИИ-чат для конкретной игры"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE games SET ai_url = ? WHERE id = ?', (url, game_id))
    conn.commit()
    conn.close()

def add_episode_if_not_exists(game_id, number):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM episodes WHERE game_id = ? AND number = ?', (game_id, number))
    if not cursor.fetchone():
        cursor.execute('INSERT INTO episodes (game_id, number) VALUES (?, ?)', (game_id, number))
    conn.commit()
    conn.close()

def get_episodes(game_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Теперь подтягиваем из базы еще и title (кастомное название эпизода)
    cursor.execute('SELECT id, number, title, file_size, duration FROM episodes WHERE game_id = ? ORDER BY number', (game_id,))
    episodes = cursor.fetchall()
    conn.close()
    return episodes

def update_episode_title(episode_id, title):
    """Обновление кастомного названия эпизода (Пункт 5)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE episodes SET title = ? WHERE id = ?', (title, episode_id))
    conn.commit()
    conn.close()

def get_videohostings():
    """Получить список всех доступных хостингов для динамических колонок в таблице (Пункт 3)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT id, key, display_name FROM videohostings')
    hostings = cursor.fetchall()
    conn.close()
    return hostings

def get_uploads(episode_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT videohosting_id FROM episode_uploads WHERE episode_id = ? AND is_uploaded = 1', (episode_id,))
    uploads = [row[0] for row in cursor.fetchall()]
    conn.close()
    return uploads

def get_upload_url(episode_id, videohosting_id):
    """Получить сохраненную ссылку на опубликованное видео (Пункт 7)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT url FROM episode_uploads WHERE episode_id = ? AND videohosting_id = ?', (episode_id, videohosting_id))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else ''

def toggle_upload(episode_id, videohosting_id, is_uploaded, url=''):
    """Установка статуса загрузки и опционально ссылки (Пункт 3 и 7)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if is_uploaded:
        cursor.execute('''
            INSERT INTO episode_uploads (episode_id, videohosting_id, is_uploaded, url) 
            VALUES (?, ?, 1, ?)
            ON CONFLICT(episode_id, videohosting_id) 
            DO UPDATE SET is_uploaded = 1
        ''', (episode_id, videohosting_id, url))
    else:
        cursor.execute('''
            UPDATE episode_uploads 
            SET is_uploaded = 0, url = '' 
            WHERE episode_id = ? AND videohosting_id = ?
        ''', (episode_id, videohosting_id))
    conn.commit()
    conn.close()

def update_episode_metadata(episode_id, file_size, duration):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE episodes SET file_size = ?, duration = ? WHERE id = ?', (file_size, duration, episode_id))
    conn.commit()
    conn.close()

def add_videohosting(key, display_name):
    """Добавляет новый хостинг в БД. Возвращает True, если успешно, и False, если такой ключ уже есть."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO videohostings (key, display_name) VALUES (?, ?)', (key, display_name))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def delete_videohosting(hosting_id):
    """Удаляет хостинг и все связанные с ним галочки/ссылки (благодаря ON DELETE CASCADE)"""
    conn = sqlite3.connect(DB_NAME)
    # Обязательно включаем внешние ключи, чтобы каскадное удаление сработало
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()
    cursor.execute('DELETE FROM videohostings WHERE id = ?', (hosting_id,))
    conn.commit()
    conn.close()

# Блок проверки: этот код выполнится только если запустить этот файл напрямую
if __name__ == "__main__":
    init_db()