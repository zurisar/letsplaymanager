import os
import logging
from database import APP_DATA_DIR

TEMPLATES_VERSION = "0.8"

# Словари дефолтов под языки
DEFAULT_TEMPLATES = {
    "ru_ru": {
        "readme": (
            "=== ДОСТУПНЫЕ ПЕРЕМЕННЫЕ ДЛЯ ШАБЛОНОВ ===\n"
            "{game_name}       - Название игры\n"
            "{ep_number}       - Номер эпизода\n"
            "{custom_title}    - Уникальное название серии\n"
            "{custom_desc}     - Описание серии\n"
            "{timecodes}       - Таймкоды серии\n"
            "{unique_tags}     - Склеенные теги без дубликатов\n"
            "{max_title_len}   - Допустимая длина заголовка до лимита в 100 знаков\n"
            "{game_desc}       - Базовое описание игры (из БД)\n"
            "{game_playlist}   - Ссылка на плейлист для текущего хостинга\n"
            "{profile_links}   - Глобальные ссылки профиля\n"
            "{profile_cta}     - Глобальный призыв к действию\n\n"
            "=== ВНУТРЕННИЕ БЛОКИ ===\n"
            "{block_timecodes} - Собранный блок таймкодов\n"
            "{block_links}     - Собранный блок ссылок\n"
        ),
        "timecodes": "⏱️ Таймкоды:\n{timecodes}",
        "links": "🔗 Ссылки:\nПлейлист: {game_playlist}\n{profile_links}",
        "video": (
            "{custom_title} | {game_name} (Эпизод {ep_number})\n\n"
            "{custom_desc}\n\n"
            "{game_desc}\n\n"
            "{block_timecodes}\n\n"
            "{block_links}\n\n"
            "{profile_cta}\n\n"
            "{unique_tags}"
        ),
        "shorts": "{game_desc}\n\n{block_links}\n\n{profile_cta}",
        "ai": (
            "Я автор YouTube-канала, выпускаю летсплей по игре «{game_name}».\n"
            "Это серия №{ep_number}.\n\n"
            "КОНТЕКСТ СЕРИИ:\n"
            "Краткий черновик: {custom_desc}\n"
            "Таймкоды событий:\n"
            "{timecodes}\n\n"
            "ТВОЯ ЗАДАЧА:\n"
            "1. Заголовки (5 вариантов):\n"
            "   - Придумай 5 цепляющих, кликабельных названий для серии.\n"
            "   - Название игры и номер серии внутрь НЕ пиши.\n"
            "   - Длина каждого заголовка строго ДО {max_title_len} символов.\n\n"
            "2. Описание:\n"
            "   - Напиши бодрое SEO-описание для зрителей на основе заметок и таймкодов (2-4 абзаца).\n\n"
            "3. Хештеги:\n"
            "   - Подбери 5-8 релевантных тегов под события этой серии.\n"
            "   - Базовые теги игры: {unique_tags}"
        ),
    },
    "en_us": {
        "readme": (
            "=== AVAILABLE TEMPLATE VARIABLES ===\n"
            "{game_name}       - Game title\n"
            "{ep_number}       - Episode number\n"
            "{custom_title}    - Custom episode title\n"
            "{custom_desc}     - Episode description\n"
            "{timecodes}       - Episode timecodes\n"
            "{unique_tags}     - Combined tags without duplicates\n"
            "{max_title_len}   - Allowed title length up to 100 chars limit\n"
            "{game_desc}       - Base game description (from DB)\n"
            "{game_playlist}   - Playlist URL for selected platform\n"
            "{profile_links}   - Global profile links\n"
            "{profile_cta}     - Global call to action\n\n"
            "=== INTERNAL BLOCKS ===\n"
            "{block_timecodes} - Formatted timecodes block\n"
            "{block_links}     - Formatted links block\n"
        ),
        "timecodes": "⏱️ Timestamps:\n{timecodes}",
        "links": "🔗 Links:\nPlaylist: {game_playlist}\n{profile_links}",
        "video": (
            "{custom_title} | {game_name} (Episode {ep_number})\n\n"
            "{custom_desc}\n\n"
            "{game_desc}\n\n"
            "{block_timecodes}\n\n"
            "{block_links}\n\n"
            "{profile_cta}\n\n"
            "{unique_tags}"
        ),
        "shorts": "{game_desc}\n\n{block_links}\n\n{profile_cta}",
        "ai": (
            "I run a YouTube gaming channel, publishing a let's play of \"{game_name}\".\n"
            "This is episode #{ep_number}.\n\n"
            "EPISODE CONTEXT:\n"
            "Draft notes: {custom_desc}\n"
            "Timestamps:\n"
            "{timecodes}\n\n"
            "YOUR TASK:\n"
            "1. Titles (5 options):\n"
            "   - Generate 5 catchy, click-worthy titles for this episode.\n"
            "   - Do NOT include the game title or episode number.\n"
            "   - Maximum title length: up to {max_title_len} characters.\n\n"
            "2. Description:\n"
            "   - Write an engaging SEO-optimized description based on my notes and timestamps (2-4 paragraphs).\n\n"
            "3. Hashtags:\n"
            "   - Generate 5-8 relevant tags for this specific episode.\n"
            "   - Base game tags already in use: {unique_tags}"
        ),
    }
}

class SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"

class TemplateManager:
    def __init__(self, config):
        self.config = config
        self.lang = config.get("language", "ru_ru")
        
        self.tpl_dir = os.path.join(APP_DATA_DIR, "templates", self.lang)
        self._ensure_folders_and_defaults()

    def _ensure_folders_and_defaults(self):
        os.makedirs(self.tpl_dir, exist_ok=True)
        version_marker = os.path.join(self.tpl_dir, ".version")
        
        current_tpl_version = "0.0"
        if os.path.exists(version_marker):
            with open(version_marker, "r", encoding="utf-8") as f:
                current_tpl_version = f.read().strip()

        need_force_update = current_tpl_version < TEMPLATES_VERSION
        
        # Забираем языковой пак или дефолтимся на en_us, если язык экзотический
        tpl_pack = DEFAULT_TEMPLATES.get(self.lang, DEFAULT_TEMPLATES["en_us"])

        # 1. Справка
        readme_path = os.path.join(self.tpl_dir, "_README_VARIABLES.txt")
        if not os.path.exists(readme_path) or need_force_update:
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(tpl_pack["readme"])

        # 2. Блоки и шаблоны
        self._write_template("_timecodes.tpl", tpl_pack["timecodes"], need_force_update)
        self._write_template("_links.tpl", tpl_pack["links"], need_force_update)
        self._write_template("publish_video.tpl", tpl_pack["video"], need_force_update)
        self._write_template("publish_shorts.tpl", tpl_pack["shorts"], need_force_update)
        self._write_template("ai_prompt.tpl", tpl_pack["ai"], need_force_update)

        with open(version_marker, "w", encoding="utf-8") as f:
            f.write(TEMPLATES_VERSION)

    def _write_template(self, filename, default_content, force_update=False):
        filepath = os.path.join(self.tpl_dir, filename)
        if not os.path.exists(filepath):
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(default_content)
        elif force_update:
            # Бекапим пользовательский файл, если он правился, и накатываем новый эталон
            bak_path = filepath + ".bak"
            try:
                if not os.path.exists(bak_path):
                    os.replace(filepath, bak_path)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(default_content)
            except OSError as e:
                logging.error(f"Не удалось обновить шаблон {filename}: {e}")

    def read_template(self, filename, custom_folder=None):
        if custom_folder:
            custom_path = os.path.join(custom_folder, filename)
            if os.path.exists(custom_path):
                with open(custom_path, 'r', encoding='utf-8') as f:
                    return '\n'.join(f.read().splitlines())
                    
        filepath = os.path.join(self.tpl_dir, filename)
        if not os.path.exists(filepath):
            return ""
            
        with open(filepath, 'r', encoding='utf-8') as f:
            return '\n'.join(f.read().splitlines())

    def render(self, template_name, data_dict, custom_folder=None):
        context = SafeDict(data_dict)
        
        if context.get("timecodes", "").strip():
            tc_tpl = self.read_template("_timecodes.tpl", custom_folder)
            context["block_timecodes"] = tc_tpl.format(**context) if tc_tpl else context["timecodes"]
        else:
            context["block_timecodes"] = ""
            
        links_tpl = self.read_template("_links.tpl", custom_folder)
        context["block_links"] = links_tpl.format(**context) if links_tpl else ""
        
        main_tpl = self.read_template(template_name, custom_folder)
        if not main_tpl:
            return f"[Ошибка: Шаблон {template_name} не найден]"
            
        final_text = main_tpl.format(**context)
        
        while "\n\n\n" in final_text:
            final_text = final_text.replace("\n\n\n", "\n\n")
            
        return final_text.strip()
    
