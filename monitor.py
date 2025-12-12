#!/usr/bin/env python3
"""
Скрипт мониторинга для cron.
Запускается ежедневно и отправляет отчёт всем активированным пользователям.
"""

import os
import asyncio
import logging
from dotenv import load_dotenv
from telegram import Bot

from storage import get_all_activated_chat_ids
from github_client import GitHubClient, format_alerts_report


load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")


async def send_daily_report() -> None:
    """Отправить ежедневный отчёт всем активированным пользователям."""
    if not TELEGRAM_BOT_TOKEN or not GITHUB_TOKEN:
        logger.error("Missing TELEGRAM_BOT_TOKEN or GITHUB_TOKEN")
        return

    chat_ids = get_all_activated_chat_ids()

    if not chat_ids:
        logger.info("No activated users, skipping report")
        return

    logger.info(f"Sending daily report to {len(chat_ids)} users")

    try:
        client = GitHubClient(GITHUB_TOKEN)
        alerts = client.get_all_alerts()
        report = format_alerts_report(alerts)

        total_alerts = sum(len(a) for a in alerts.values())
        logger.info(f"Found {total_alerts} total alerts")

        bot = Bot(token=TELEGRAM_BOT_TOKEN)

        for chat_id in chat_ids:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=report,
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                )
                logger.info(f"Report sent to {chat_id}")
            except Exception as e:
                logger.error(f"Failed to send to {chat_id}: {e}")

    except Exception as e:
        logger.error(f"Error generating report: {e}")


def main():
    """Точка входа."""
    asyncio.run(send_daily_report())


if __name__ == "__main__":
    main()
