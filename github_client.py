"""
GitHub API клиент для получения Dependabot Security Alerts.
"""

import os
import requests
from typing import List, Dict, Any
from dataclasses import dataclass
from enum import Enum


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


@dataclass
class SecurityAlert:
    """Представление security alert."""
    repo_name: str
    package_name: str
    severity: str
    cve_id: str
    ghsa_id: str
    summary: str
    vulnerable_version: str
    patched_version: str
    url: str
    created_at: str


class GitHubClient:
    """Клиент для работы с GitHub API."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

    def get_user_repos(self) -> List[Dict[str, Any]]:
        """Получить все репозитории пользователя."""
        repos = []
        page = 1

        while True:
            response = requests.get(
                f"{self.BASE_URL}/user/repos",
                headers=self.headers,
                params={
                    "per_page": 100,
                    "page": page,
                    "type": "all"  # owner, collaborator, organization_member
                }
            )
            response.raise_for_status()

            data = response.json()
            if not data:
                break

            repos.extend(data)
            page += 1

        return repos

    def get_dependabot_alerts(self, owner: str, repo: str) -> List[SecurityAlert]:
        """Получить Dependabot alerts для репозитория."""
        alerts = []

        try:
            response = requests.get(
                f"{self.BASE_URL}/repos/{owner}/{repo}/dependabot/alerts",
                headers=self.headers,
                params={
                    "state": "open",
                    "per_page": 100
                }
            )

            # 403 = Dependabot alerts отключены для репозитория
            # 404 = Нет доступа
            if response.status_code in (403, 404):
                return []

            response.raise_for_status()
            data = response.json()

            for alert in data:
                security_advisory = alert.get("security_advisory") or {}
                vulnerability = alert.get("security_vulnerability") or {}

                # first_patched_version может быть None
                first_patched = vulnerability.get("first_patched_version")
                patched_version = first_patched.get("identifier") if first_patched else "N/A"

                # package тоже может быть None
                package = vulnerability.get("package") or {}

                alerts.append(SecurityAlert(
                    repo_name=f"{owner}/{repo}",
                    package_name=package.get("name", "unknown"),
                    severity=security_advisory.get("severity", "unknown"),
                    cve_id=security_advisory.get("cve_id") or "",
                    ghsa_id=security_advisory.get("ghsa_id") or "",
                    summary=security_advisory.get("summary", "No description"),
                    vulnerable_version=vulnerability.get("vulnerable_version_range", ""),
                    patched_version=patched_version,
                    url=alert.get("html_url", ""),
                    created_at=alert.get("created_at", "")
                ))

        except requests.exceptions.RequestException as e:
            print(f"Error fetching alerts for {owner}/{repo}: {e}")

        return alerts

    def get_all_alerts(self) -> Dict[str, List[SecurityAlert]]:
        """
        Получить все alerts для всех репозиториев пользователя.
        Возвращает словарь сгруппированный по severity.
        """
        all_alerts = {
            "critical": [],
            "high": [],
            "moderate": [],
            "low": []
        }

        repos = self.get_user_repos()

        for repo in repos:
            owner = repo["owner"]["login"]
            repo_name = repo["name"]

            alerts = self.get_dependabot_alerts(owner, repo_name)

            for alert in alerts:
                severity = alert.severity.lower()
                if severity in all_alerts:
                    all_alerts[severity].append(alert)
                else:
                    all_alerts["low"].append(alert)

        return all_alerts


def format_alerts_report(alerts: Dict[str, List[SecurityAlert]]) -> str:
    """Форматировать отчёт об уязвимостях для Telegram."""
    total = sum(len(a) for a in alerts.values())

    if total == 0:
        return "✅ *Security Monitor Report*\n\nНет открытых уязвимостей! Все репозитории в безопасности."

    lines = [
        "🛡️ *Security Monitor Report*",
        f"📅 Найдено уязвимостей: *{total}*",
        ""
    ]

    severity_emoji = {
        "critical": "🔴",
        "high": "🟠",
        "moderate": "🟡",
        "low": "🔵"
    }

    severity_names = {
        "critical": "CRITICAL",
        "high": "HIGH",
        "moderate": "MODERATE",
        "low": "LOW"
    }

    for severity in ["critical", "high", "moderate", "low"]:
        severity_alerts = alerts.get(severity, [])
        if not severity_alerts:
            continue

        emoji = severity_emoji.get(severity, "⚪")
        name = severity_names.get(severity, severity.upper())

        lines.append(f"\n{emoji} *{name}* ({len(severity_alerts)})")
        lines.append("─" * 25)

        for alert in severity_alerts[:10]:  # Ограничим вывод
            cve = alert.cve_id or alert.ghsa_id or "N/A"
            lines.append(f"📦 `{alert.package_name}`")
            lines.append(f"   📁 {alert.repo_name}")
            lines.append(f"   🆔 {cve}")
            lines.append(f"   ⬆️ Обновить до: {alert.patched_version}")
            if alert.url:
                lines.append(f"   🔗 [Подробнее]({alert.url})")
            lines.append("")

        if len(severity_alerts) > 10:
            lines.append(f"   ... и ещё {len(severity_alerts) - 10}")

    lines.append("\n💡 *Рекомендация:* Обновите зависимости командой `npm update` или `pip install --upgrade`")

    return "\n".join(lines)
