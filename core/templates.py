import os
import logging
from database import APP_DATA_DIR

class SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"

class TemplateManager:
    def __init__(self, config):
        self.config = config
        self.lang = config.get("language", "ru_ru")
        
        # Шаблоны теперь лежат в Документы/LetsPlayManager/templates/ru_ru
        self.tpl_dir = os.path.join(APP_DATA_DIR, "templates", self.lang)
        self._ensure_folders_and_defaults()

    def _ensure_folders_and_defaults(self):
        """Создает папку и генерирует стандартные шаблоны, если их нет"""
        os.makedirs(self.tpl_dir, exist_ok=True)
        
        # 1. Файл справки
        readme_path = os.path.join(self.tpl_dir, "_README_VARIABLES.txt")
        if not os.path.exists(readme_path):
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write("=== ДОСТУПНЫЕ ПЕРЕМЕННЫЕ ДЛЯ ШАБЛОНОВ ===\n")
                f.write("{game_name}       - Название игры\n")
                f.write("{ep_number}       - Номер эпизода\n")
                f.write("{custom_title}    - Уникальное название серии\n")
                f.write("{custom_desc}     - Описание серии\n")
                f.write("{timecodes}       - Таймкоды серии\n")
                f.write("{unique_tags}     - Склеенные теги без дубликатов\n")
                f.write("{game_desc}       - Базовое описание игры (из БД)\n")
                f.write("{game_playlist}   - Ссылка на плейлист для текущего хостинга\n")
                f.write("{profile_links}   - Глобальные ссылки профиля\n")
                f.write("{profile_cta}     - Глобальный призыв к действию\n\n")
                f.write("=== ВНУТРЕННИЕ БЛОКИ ===\n")
                f.write("{block_timecodes} - Собранный блок таймкодов\n")
                f.write("{block_links}     - Собранный блок ссылок\n")

        # 2. Базовые блоки (кирпичики)
        self._create_if_not_exists("_timecodes.tpl", "⏱️ Таймкоды:\n{timecodes}")
        self._create_if_not_exists("_links.tpl", "🔗 Ссылки:\nПлейлист: {game_playlist}\n{profile_links}")
        
        # 3. Финальные шаблоны сборки
        video_tpl = (
            "{custom_title} | {game_name} (Эпизод {ep_number})\n\n"
            "{custom_desc}\n\n"
            "{game_desc}\n\n"
            "{block_timecodes}\n\n"
            "{block_links}\n\n"
            "{profile_cta}\n\n"
            "{unique_tags}"
        )
        self._create_if_not_exists("publish_video.tpl", video_tpl)
        
        shorts_tpl = (
            "{game_desc}\n\n"
            "{block_links}\n\n"
            "{profile_cta}"
        )
        self._create_if_not_exists("publish_shorts.tpl", shorts_tpl)

        ai_tpl = (
            "Я записываю летсплей по игре {game_name}. В этой серии (эпизод {ep_number}) произошло следующее:\n"
            "{custom_desc}\n\n"
            "Сгенерируй 5 вариантов названий и короткое SEO-описание. Мои теги: {unique_tags}"
        )
        self._create_if_not_exists("ai_prompt.tpl", ai_tpl)

    def _create_if_not_exists(self, filename, default_content):
        filepath = os.path.join(self.tpl_dir, filename)
        if not os.path.exists(filepath):
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(default_content)

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