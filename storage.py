"""
Хранилище активированных пользователей.
Сохраняет chat_id в JSON файл.
"""

import json
import os
from pathlib import Path
from typing import Set
from datetime import datetime


STORAGE_FILE = Path(__file__).parent / "activated_users.json"


def load_users() -> dict:
    """Загрузить данные о пользователях из файла."""
    if not STORAGE_FILE.exists():
        return {"users": {}}

    try:
        with open(STORAGE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"users": {}}


def save_users(data: dict) -> None:
    """Сохранить данные о пользователях в файл."""
    with open(STORAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def is_user_activated(chat_id: int) -> bool:
    """Проверить, активирован ли пользователь."""
    data = load_users()
    return str(chat_id) in data.get("users", {})


def activate_user(chat_id: int, username: str = None) -> bool:
    """
    Активировать пользователя.
    Возвращает True если это новая активация, False если уже был активирован.
    """
    data = load_users()

    if "users" not in data:
        data["users"] = {}

    chat_id_str = str(chat_id)

    if chat_id_str in data["users"]:
        return False

    data["users"][chat_id_str] = {
        "username": username,
        "activated_at": datetime.now().isoformat()
    }

    save_users(data)
    return True


def get_all_activated_chat_ids() -> Set[int]:
    """Получить все активированные chat_id."""
    data = load_users()
    return {int(chat_id) for chat_id in data.get("users", {}).keys()}


def get_user_info(chat_id: int) -> dict | None:
    """Получить информацию о пользователе."""
    data = load_users()
    return data.get("users", {}).get(str(chat_id))
