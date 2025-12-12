"""
Telegram бот для мониторинга безопасности.
Команды:
- /start - приветствие
- /activate <token> - активация пользователя
- /status - статус активации
- /update - принудительная проверка уязвимостей
"""

import os
import asyncio
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
)

from storage import is_user_activated, activate_user, get_user_info
from github_client import GitHubClient, format_alerts_report


load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ACTIVATION_TOKEN = os.getenv("ACTIVATION_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    if is_user_activated(chat_id):
        await update.message.reply_text(
            f"👋 Привет, {user.first_name}!\n\n"
            "✅ Вы уже активированы.\n\n"
            "Доступные команды:\n"
            "• /status - статус активации\n"
            "• /update - проверить уязвимости\n"
        )
    else:
        await update.message.reply_text(
            f"👋 Привет, {user.first_name}!\n\n"
            "🔒 Этот бот мониторит GitHub Security Alerts.\n\n"
            "Для активации используйте команду:\n"
            "`/activate <ваш_токен>`\n\n"
            "Токен активации можно получить у администратора.",
            parse_mode="Markdown"
        )


async def activate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /activate <token>."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    if is_user_activated(chat_id):
        await update.message.reply_text("✅ Вы уже активированы!")
        return

    if not context.args or len(context.args) != 1:
        await update.message.reply_text(
            "❌ Использование: `/activate <токен>`",
            parse_mode="Markdown"
        )
        return

    token = context.args[0]

    if token != ACTIVATION_TOKEN:
        logger.warning(f"Failed activation attempt from {user.username} (chat_id: {chat_id})")
        await update.message.reply_text("❌ Неверный токен активации.")
        return

    username = user.username or user.first_name
    is_new = activate_user(chat_id, username)

    if is_new:
        logger.info(f"User activated: {username} (chat_id: {chat_id})")
        await update.message.reply_text(
            "✅ Активация успешна!\n\n"
            "Теперь вы будете получать ежедневные отчёты о безопасности.\n\n"
            "Доступные команды:\n"
            "• /status - статус активации\n"
            "• /update - проверить уязвимости прямо сейчас"
        )
    else:
        await update.message.reply_text("✅ Вы уже были активированы ранее.")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /status."""
    chat_id = update.effective_chat.id

    if not is_user_activated(chat_id):
        await update.message.reply_text(
            "❌ Вы не активированы.\n\n"
            "Используйте `/activate <токен>` для активации.",
            parse_mode="Markdown"
        )
        return

    user_info = get_user_info(chat_id)
    activated_at = user_info.get("activated_at", "N/A") if user_info else "N/A"

    await update.message.reply_text(
        f"✅ *Статус: Активирован*\n\n"
        f"📅 Дата активации: `{activated_at}`\n"
        f"🆔 Chat ID: `{chat_id}`\n\n"
        f"Используйте /update для проверки уязвимостей.",
        parse_mode="Markdown"
    )


async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /update - принудительная проверка уязвимостей."""
    chat_id = update.effective_chat.id

    if not is_user_activated(chat_id):
        await update.message.reply_text(
            "❌ Команда доступна только для активированных пользователей.\n\n"
            "Используйте `/activate <токен>` для активации.",
            parse_mode="Markdown"
        )
        return

    await update.message.reply_text("🔍 Проверяю репозитории на уязвимости...")

    try:
        client = GitHubClient(GITHUB_TOKEN)
        alerts = client.get_all_alerts()
        report = format_alerts_report(alerts)

        await update.message.reply_text(
            report,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Error checking alerts: {e}")
        await update.message.reply_text(
            f"❌ Ошибка при проверке: {str(e)}"
        )


async def unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик неизвестных сообщений от неактивированных пользователей."""
    chat_id = update.effective_chat.id

    if not is_user_activated(chat_id):
        # Игнорируем сообщения от неактивированных, но отвечаем на первое
        await update.message.reply_text(
            "🔒 Бот требует активации.\n\n"
            "Используйте `/activate <токен>` или напишите /start",
            parse_mode="Markdown"
        )


def main() -> None:
    """Запуск бота."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in environment")
    if not ACTIVATION_TOKEN:
        raise ValueError("ACTIVATION_TOKEN not set in environment")
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN not set in environment")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("activate", activate_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("update", update_command))

    # Обработчик неизвестных сообщений
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        unknown_message
    ))

    logger.info("Bot started")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
