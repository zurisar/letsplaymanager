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

    # Таблица для шортсов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shorts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            episode_id INTEGER,
            number INTEGER,
            file_size TEXT DEFAULT '0',
            duration TEXT DEFAULT '0',
            custom_title TEXT DEFAULT '',
            tags TEXT DEFAULT '',
            publish_date TEXT DEFAULT '',
            FOREIGN KEY(episode_id) REFERENCES episodes(id)
        )
    ''')

    # Таблица для загрузок шортсов на хостинги
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shorts_uploads (
            short_id INTEGER,
            videohosting_id TEXT,
            is_uploaded INTEGER DEFAULT 0,
            url TEXT DEFAULT '',
            PRIMARY KEY (short_id, videohosting_id),
            FOREIGN KEY(short_id) REFERENCES shorts(id)
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
    cursor.execute('SELECT id, name, folder_path, ai_url, steam_id FROM games')
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
    # Добавляем подсчет шортсов через LEFT JOIN
    cursor.execute('''
        SELECT e.id, e.number, e.title, e.file_size, e.duration, e.publish_date, COUNT(s.id) as shorts_count
        FROM episodes e
        LEFT JOIN shorts s ON e.id = s.episode_id
        WHERE e.game_id = ? 
        GROUP BY e.id
        ORDER BY e.number
    ''', (game_id,))
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

def update_episode_publish_date(episode_id, date_str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE episodes SET publish_date = ? WHERE id = ?', (date_str, episode_id))
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

def update_upload_url(episode_id, videohosting_id, url):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Проверяем, есть ли уже запись для этого эпизода и хостинга
    cursor.execute('SELECT 1 FROM episode_uploads WHERE episode_id = ? AND videohosting_id = ?', (episode_id, videohosting_id))
    if cursor.fetchone():
        cursor.execute('UPDATE episode_uploads SET url = ? WHERE episode_id = ? AND videohosting_id = ?', (url, episode_id, videohosting_id))
    else:
        cursor.execute('INSERT INTO episode_uploads (episode_id, videohosting_id, is_uploaded, url) VALUES (?, ?, 0, ?)', (episode_id, videohosting_id, url))
    conn.commit()
    conn.close()

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

def mark_episode_deleted(episode_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Ставим флаг удаления и сбрасываем вес/время, так как файлов больше нет
    cursor.execute('UPDATE episodes SET sources_deleted = 1, file_size = "0", duration = "0" WHERE id = ?', (episode_id,))
    conn.commit()
    conn.close()

# --- ФУНКЦИИ ДЛЯ ШОРТСОВ ---

def get_shorts(episode_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, number, file_size, duration, custom_title, tags, publish_date 
        FROM shorts WHERE episode_id = ? ORDER BY number
    ''', (episode_id,))
    shorts = cursor.fetchall()
    conn.close()
    return shorts

def add_short_to_db(episode_id, number, file_size="0", duration="0"):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO shorts (episode_id, number, file_size, duration) 
        VALUES (?, ?, ?, ?)
    ''', (episode_id, number, file_size, duration))
    conn.commit()
    conn.close()

def update_short_field(short_id, field, value):
    """Универсальная функция для обновления текстовых полей шортса"""
    allowed_fields = ['custom_title', 'tags', 'publish_date']
    if field in allowed_fields:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(f'UPDATE shorts SET {field} = ? WHERE id = ?', (value, short_id))
        conn.commit()
        conn.close()

def get_short_uploads(short_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT videohosting_id, is_uploaded, url FROM shorts_uploads WHERE short_id = ?', (short_id,))
    uploads = cursor.fetchall()
    conn.close()
    return uploads

def update_short_upload_status(short_id, videohosting_id, is_uploaded):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM shorts_uploads WHERE short_id = ? AND videohosting_id = ?', (short_id, videohosting_id))
    if cursor.fetchone():
        cursor.execute('UPDATE shorts_uploads SET is_uploaded = ? WHERE short_id = ? AND videohosting_id = ?', 
                       (is_uploaded, short_id, videohosting_id))
    else:
        cursor.execute('INSERT INTO shorts_uploads (short_id, videohosting_id, is_uploaded) VALUES (?, ?, ?)', 
                       (short_id, videohosting_id, is_uploaded))
    conn.commit()
    conn.close()

def update_short_url(short_id, videohosting_id, url):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM shorts_uploads WHERE short_id = ? AND videohosting_id = ?', (short_id, videohosting_id))
    if cursor.fetchone():
        cursor.execute('UPDATE shorts_uploads SET url = ? WHERE short_id = ? AND videohosting_id = ?', 
                       (url, short_id, videohosting_id))
    else:
        cursor.execute('INSERT INTO shorts_uploads (short_id, videohosting_id, is_uploaded, url) VALUES (?, ?, 0, ?)', 
                       (short_id, videohosting_id, url))
    conn.commit()
    conn.close()

def delete_game_full(game_id):
    """Каскадное удаление игры и всех связанных с ней данных из всех таблиц"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Сначала находим все эпизоды этой игры
    cursor.execute('SELECT id FROM episodes WHERE game_id = ?', (game_id,))
    episodes = cursor.fetchall()
    
    for (ep_id,) in episodes:
        # Для каждого эпизода находим его шортсы
        cursor.execute('SELECT id FROM shorts WHERE episode_id = ?', (ep_id,))
        shorts = cursor.fetchall()
        
        # Удаляем связи с хостингами для этих шортсов
        for (sh_id,) in shorts:
            cursor.execute('DELETE FROM shorts_uploads WHERE short_id = ?', (sh_id,))
            
        # Удаляем сами шортсы
        cursor.execute('DELETE FROM shorts WHERE episode_id = ?', (ep_id,))
        
    # Теперь, когда зависимые данные удалены, сносим эпизоды и саму игру
    cursor.execute('DELETE FROM episodes WHERE game_id = ?', (game_id,))
    cursor.execute('DELETE FROM games WHERE id = ?', (game_id,))
    
    conn.commit()
    conn.close()

def update_game(game_id, name, ai_url, steam_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE games 
        SET name = ?, ai_url = ?, steam_id = ? 
        WHERE id = ?
    ''', (name, ai_url, steam_id, game_id))
    conn.commit()
    conn.close()

# Блок проверки: этот код выполнится только если запустить этот файл напрямую
if __name__ == "__main__":
    init_db()