"""Читалка истории репозиториев (бета).

История читается через GitHub REST API (эквивалент git log --since --until):
git-бинарник и клонирование не нужны, укладываемся в лимиты Vercel.
Файлы memory_bank/progress.md и projectbrief.md добираются с raw.githubusercontent.com.
"""

from __future__ import annotations

import datetime as dt
import os
import re

import requests

_REPO_URL_RE = re.compile(
    r"^https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)
MAX_COMMITS = 300
_MAX_MSG_CHARS = 300
_PROMPT_COMMITS_BUDGET = 30000
_MB_FILES = ("memory_bank/progress.md", "memory_bank/projectbrief.md")
_MB_FETCH_CAP = 100_000
_MB_PROMPT_CAP = 15000
_HTTP_TIMEOUT = 10


class RepoHistoryError(Exception):
    """Ошибка с готовым HTTP-статусом и сообщением для пользователя."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def parse_repo_url(url: str | None) -> tuple[str, str]:
    m = _REPO_URL_RE.match((url or "").strip())
    if not m:
        raise RepoHistoryError(
            "Нужна ссылка на публичный GitHub-репозиторий, "
            "например https://github.com/user/repo"
        )
    return m.group(1), m.group(2)


def resolve_period(data: dict) -> tuple[str, str, str]:
    """Вернуть (since_iso, until_iso, label) из days или since/until."""
    today = dt.datetime.now(dt.timezone.utc).date()
    since_raw = str(data.get("since") or "").strip()
    until_raw = str(data.get("until") or "").strip()
    if since_raw or until_raw:
        try:
            since_d = (
                dt.date.fromisoformat(since_raw)
                if since_raw
                else today - dt.timedelta(days=30)
            )
            until_d = dt.date.fromisoformat(until_raw) if until_raw else today
        except ValueError:
            raise RepoHistoryError("Даты должны быть в формате ГГГГ-ММ-ДД")
        if since_d > until_d:
            raise RepoHistoryError("Дата «с» позже даты «по»")
        if until_d > today:
            raise RepoHistoryError("Дата «по» не может быть в будущем")
        if (until_d - since_d).days > 366:
            raise RepoHistoryError("Период не может быть длиннее года")
        label = f"{since_d.isoformat()} — {until_d.isoformat()}"
    else:
        try:
            raw_days = data.get("days")
            days = 7 if raw_days is None or raw_days == "" else int(raw_days)
        except (TypeError, ValueError):
            raise RepoHistoryError("Период должен быть числом дней")
        if not 1 <= days <= 365:
            raise RepoHistoryError("Период — от 1 до 365 дней")
        since_d = today - dt.timedelta(days=days)
        until_d = today
        label = f"последние {days} дн."
    return (
        since_d.isoformat() + "T00:00:00Z",
        until_d.isoformat() + "T23:59:59Z",
        label,
    )


def _gh_headers() -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "LTHub-repo-history",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_commits(
    owner: str, repo: str, since: str, until: str
) -> tuple[list[dict], bool]:
    """Коммиты за период (новые сверху) + флаг обрезки до MAX_COMMITS."""
    commits: list[dict] = []
    truncated = False
    pages = MAX_COMMITS // 100
    for page in range(1, pages + 1):
        try:
            r = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/commits",
                params={
                    "since": since,
                    "until": until,
                    "per_page": 100,
                    "page": page,
                },
                headers=_gh_headers(),
                timeout=_HTTP_TIMEOUT,
            )
        except requests.RequestException:
            raise RepoHistoryError(
                "Не удалось связаться с GitHub, попробуйте позже", 502
            )
        if r.status_code == 404:
            raise RepoHistoryError(
                "Репозиторий не найден (приватные репозитории не поддерживаются)",
                404,
            )
        if r.status_code in (403, 429):
            raise RepoHistoryError("Лимит GitHub API исчерпан, попробуйте позже", 429)
        if r.status_code != 200:
            raise RepoHistoryError(f"GitHub вернул ошибку ({r.status_code})", 502)
        batch = r.json()
        if not isinstance(batch, list):
            raise RepoHistoryError("Неожиданный ответ GitHub", 502)
        for c in batch:
            commit = c.get("commit") or {}
            author = commit.get("author") or {}
            commits.append(
                {
                    "sha": (c.get("sha") or "")[:7],
                    "author": author.get("name") or "unknown",
                    "date": author.get("date") or "",
                    "message": (commit.get("message") or "").strip()[:_MAX_MSG_CHARS],
                }
            )
        if len(batch) < 100:
            break
        if page == pages:
            truncated = True
    return commits, truncated


def fetch_memory_bank(owner: str, repo: str) -> dict[str, str]:
    """progress.md / projectbrief.md из memory_bank при наличии (404 → пропуск)."""
    out: dict[str, str] = {}
    for path in _MB_FILES:
        try:
            r = requests.get(
                f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{path}",
                headers={"User-Agent": "LTHub-repo-history"},
                timeout=_HTTP_TIMEOUT,
            )
        except requests.RequestException:
            continue
        if r.status_code == 200:
            out[path] = r.text[:_MB_FETCH_CAP]
    return out


def build_prompt(
    owner: str,
    repo: str,
    commits: list[dict],
    mb_files: dict[str, str],
    label: str,
    truncated: bool,
) -> str:
    lines: list[str] = []
    budget = _PROMPT_COMMITS_BUDGET
    dropped = 0
    for c in commits:
        line = f"- {c['date'][:10]} {c['sha']} ({c['author']}): {c['message']}"
        if len(line) > budget:
            dropped = len(commits) - len(lines)
            break
        budget -= len(line)
        lines.append(line)
    parts = [
        f"Ты — аналитик истории разработки. Репозиторий: {owner}/{repo}. "
        f"Период: {label}.",
        "Ниже список коммитов (git log) за период, новые сверху:",
        "\n".join(lines),
    ]
    if truncated or dropped:
        parts.append(
            f"ВНИМАНИЕ: список обрезан, показаны новейшие {len(lines)} коммитов "
            f"(ещё {dropped if dropped else 'много'} не поместилось). "
            "Упомяни это в сводке."
        )
    for path, text in mb_files.items():
        parts.append(f"Контекст проекта — файл {path}:\n{text[:_MB_PROMPT_CAP]}")
    parts.append(
        "Составь на русском языке сводку того, что добавилось и изменилось "
        "в проекте за выбранный период. Сгруппируй по темам: новые функции, "
        "исправления, рефакторинг, тесты/документация/прочее. Выдели главное. "
        "Опирайся только на сообщения коммитов и приведённые файлы, не выдумывай. "
        "Файлы memory_bank используй как контекст статуса проекта. "
        "Ответ в Markdown, без вступлений и без обрамляющих ```."
    )
    return "\n\n".join(parts)


def page_html() -> str:
    return """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Читалка истории репозиториев — LTHub</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.2/marked.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/dompurify/3.1.6/purify.min.js"></script>
<style>
    body { background: var(--bb-bg); color: var(--bb-text); font-family: system-ui, sans-serif; margin: 0; }
    .wrap { max-width: 860px; margin: 0 auto; padding: 24px 16px 60px; }
    a.back { color: var(--bb-accent); text-decoration: none; font-size: 14px; }
    h1 { font-size: 24px; margin: 12px 0 4px; }
    .beta-tag { font-size: 11px; background: var(--bb-accent); color: #fff; border-radius: 8px; padding: 2px 8px; vertical-align: middle; }
    .hint { color: var(--bb-muted); font-size: 14px; margin: 0 0 20px; }
    .panel { background: var(--bb-panel); border: 1px solid var(--bb-border); border-radius: 12px; padding: 16px; }
    label { display: block; font-size: 13px; color: var(--bb-muted); margin: 10px 0 4px; }
    input[type=text], input[type=date], select {
        width: 100%; box-sizing: border-box; padding: 10px; border-radius: 8px;
        border: 1px solid var(--bb-border); background: var(--bb-elev); color: var(--bb-text); font-size: 15px;
    }
    .row { display: flex; gap: 12px; }
    .row > div { flex: 1; }
    button.go {
        margin-top: 16px; width: 100%; padding: 12px; font-size: 16px; border: none; border-radius: 8px;
        background: var(--bb-accent); color: #fff; cursor: pointer;
    }
    button.go:disabled { opacity: .6; cursor: wait; }
    #rhMeta { color: var(--bb-muted); font-size: 13px; margin: 18px 0 6px; }
    #rhWarn { color: #d97706; font-size: 13px; margin: 4px 0; }
    #rhResult { background: var(--bb-panel); border: 1px solid var(--bb-border); border-radius: 12px; padding: 16px; margin-top: 8px; line-height: 1.55; overflow-wrap: anywhere; }
    #rhResult h1, #rhResult h2, #rhResult h3 { font-size: 18px; }
    #rhResult code { background: var(--bb-elev); padding: 1px 5px; border-radius: 5px; }
    #rhError { color: #dc2626; margin-top: 14px; font-size: 14px; white-space: pre-wrap; }
    .hidden { display: none; }
</style>
</head>
<body>
<div class="wrap">
    <a class="back" href="/">← Назад в хаб</a>
    <h1>📜 Читалка истории репозиториев <span class="beta-tag">Бета</span></h1>
    <p class="hint">Вставьте ссылку на публичный GitHub-репозиторий и выберите период — ИИ расскажет, что добавилось за это время (по git log и файлам memory_bank, если они есть).</p>
    <div class="panel">
        <label for="rhUrl">Ссылка на репозиторий</label>
        <input type="text" id="rhUrl" placeholder="https://github.com/user/repo">
        <div class="row">
            <div>
                <label for="rhPeriod">Период</label>
                <select id="rhPeriod">
                    <option value="7">Последние 7 дней</option>
                    <option value="30" selected>Последние 30 дней</option>
                    <option value="90">Последние 90 дней</option>
                    <option value="custom">Свой период…</option>
                </select>
            </div>
        </div>
        <div class="row hidden" id="rhDates">
            <div>
                <label for="rhSince">С даты</label>
                <input type="date" id="rhSince">
            </div>
            <div>
                <label for="rhUntil">По дату</label>
                <input type="date" id="rhUntil">
            </div>
        </div>
        <button class="go" id="rhGo">📜 Прочитать историю</button>
    </div>
    <div id="rhError"></div>
    <div id="rhMeta"></div>
    <div id="rhWarn"></div>
    <div id="rhResult" class="hidden"></div>
</div>
<script>
(function () {
    var urlEl = document.getElementById('rhUrl');
    var periodEl = document.getElementById('rhPeriod');
    var datesEl = document.getElementById('rhDates');
    var sinceEl = document.getElementById('rhSince');
    var untilEl = document.getElementById('rhUntil');
    var goEl = document.getElementById('rhGo');
    var errEl = document.getElementById('rhError');
    var metaEl = document.getElementById('rhMeta');
    var warnEl = document.getElementById('rhWarn');
    var resEl = document.getElementById('rhResult');

    function isoDaysAgo(n) {
        var d = new Date(Date.now() - n * 86400000);
        return d.toISOString().slice(0, 10);
    }
    sinceEl.value = isoDaysAgo(30);
    untilEl.value = isoDaysAgo(0);

    periodEl.addEventListener('change', function () {
        datesEl.classList.toggle('hidden', periodEl.value !== 'custom');
    });

    function renderSummary(md) {
        resEl.classList.remove('hidden');
        if (window.marked && window.DOMPurify && typeof window.DOMPurify.sanitize === 'function') {
            resEl.innerHTML = window.DOMPurify.sanitize(window.marked.parse(md), {USE_PROFILES: {html: true}});
        } else {
            resEl.textContent = md;
        }
    }

    function fail(msg) {
        errEl.textContent = msg;
    }

    function analyze() {
        errEl.textContent = '';
        metaEl.textContent = '';
        warnEl.textContent = '';
        resEl.classList.add('hidden');
        var url = urlEl.value.trim();
        if (!url) { fail('Вставьте ссылку на репозиторий'); return; }
        var body = {url: url};
        if (periodEl.value === 'custom') {
            body.since = sinceEl.value;
            body.until = untilEl.value;
            if (!body.since || !body.until) { fail('Укажите обе даты'); return; }
        } else {
            body.days = parseInt(periodEl.value, 10);
        }
        goEl.disabled = true;
        goEl.textContent = '⏳ Читаю историю и спрашиваю ИИ…';
        var hdrs = {'Content-Type': 'application/json'};
        var tok = localStorage.getItem('web_token');
        if (tok) hdrs['X-Auth-Token'] = tok;
        fetch('/api/repo_history/analyze', {method: 'POST', headers: hdrs, body: JSON.stringify(body)})
            .then(function (r) {
                return r.text().then(function (t) {
                    var j = null;
                    try { j = JSON.parse(t); } catch (e) {}
                    return {status: r.status, body: j};
                });
            })
            .then(function (res) {
                if (res.status === 200 && res.body && res.body.summary) {
                    var b = res.body;
                    metaEl.textContent = b.repo + ' · ' + b.period + ' · коммитов: ' + b.commit_count +
                        (b.memory_bank_files && b.memory_bank_files.length ? ' · memory_bank: ' + b.memory_bank_files.join(', ') : '');
                    if (b.truncated) warnEl.textContent = '⚠️ История длинная — показаны новейшие ' + b.commit_count + ' коммитов.';
                    renderSummary(b.summary);
                } else if (res.body && res.body.error) {
                    fail(res.body.error);
                } else if (res.status === 429) {
                    fail('Слишком много запросов, подождите немного.');
                } else if (res.status === 502 || res.status === 504) {
                    fail('ИИ временно недоступен, попробуйте позже.');
                } else {
                    fail('Не удалось получить сводку (код ' + res.status + ').');
                }
            })
            .catch(function () { fail('Сервис недоступен, проверьте сеть.'); })
            .finally(function () {
                goEl.disabled = false;
                goEl.textContent = '📜 Прочитать историю';
            });
    }

    goEl.addEventListener('click', analyze);
    urlEl.addEventListener('keydown', function (e) { if (e.key === 'Enter') analyze(); });
})();
</script>
</body>
</html>"""
