"""Читалка истории репозиториев (бета).

История читается через GitHub REST API (эквивалент git log --since --until):
git-бинарник и клонирование не нужны, укладываемся в лимиты Vercel.
Файлы memory_bank/progress.md и projectbrief.md добираются с raw.githubusercontent.com.
"""

from __future__ import annotations

import datetime as dt
import os
import re
import time

import requests

_REPO_URL_RE = re.compile(
    r"^https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)
MAX_COMMITS = 300
_MAX_MSG_CHARS = 300
_PROMPT_COMMITS_BUDGET = 12000
_MB_FILES = ("memory_bank/progress.md", "memory_bank/projectbrief.md")
_MB_FETCH_CAP = 100_000
_MB_PROMPT_CAP = 6000
_HTTP_TIMEOUT = 10
MAX_QUESTION_CHARS = 500

# Best-effort кэш контекста (коммиты + memory_bank) на время Q&A-сессии,
# чтобы уточняющие вопросы и «Короче» не дёргали GitHub API повторно.
# In-memory: на холодном старте Vercel очищается — тогда контекст перечитывается.
_CONTEXT_TTL = 600
_CONTEXT_MAX = 200
_CONTEXT_CACHE: dict[tuple, tuple[float, list, bool, dict]] = {}


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


def get_context(
    owner: str, repo: str, since: str, until: str
) -> tuple[list[dict], bool, dict[str, str]]:
    """Коммиты + memory_bank с best-effort TTL-кэшем (для Q&A и «Короче»)."""
    key = (owner, repo, since, until)
    now = time.time()
    hit = _CONTEXT_CACHE.get(key)
    if hit and now - hit[0] < _CONTEXT_TTL:
        return hit[1], hit[2], hit[3]
    commits, truncated = fetch_commits(owner, repo, since, until)
    mb_files = fetch_memory_bank(owner, repo) if commits else {}
    if len(_CONTEXT_CACHE) >= _CONTEXT_MAX:
        oldest = min(_CONTEXT_CACHE, key=lambda k: _CONTEXT_CACHE[k][0])
        _CONTEXT_CACHE.pop(oldest, None)
    _CONTEXT_CACHE[key] = (now, commits, truncated, mb_files)
    return commits, truncated, mb_files


# Кэш готовой AI-сводки: повторный запрос того же репо/периода/режима не
# дёргает провайдеров (главная причина 429). Кэшируем только успешный ответ ИИ,
# чтобы после восстановления провайдера пользователь получил полноценный анализ.
_SUMMARY_TTL = 600
_SUMMARY_MAX = 200
_SUMMARY_CACHE: dict[tuple, tuple[float, dict]] = {}


def get_cached_summary(
    owner: str, repo: str, since: str, until: str, brief: bool
) -> dict | None:
    hit = _SUMMARY_CACHE.get((owner, repo, since, until, brief))
    if hit and time.time() - hit[0] < _SUMMARY_TTL:
        return hit[1]
    return None


def put_cached_summary(
    owner: str, repo: str, since: str, until: str, brief: bool, payload: dict
) -> None:
    key = (owner, repo, since, until, brief)
    if len(_SUMMARY_CACHE) >= _SUMMARY_MAX:
        oldest = min(_SUMMARY_CACHE, key=lambda k: _SUMMARY_CACHE[k][0])
        _SUMMARY_CACHE.pop(oldest, None)
    _SUMMARY_CACHE[key] = (time.time(), payload)


def _commit_lines(commits: list[dict]) -> tuple[list[str], int]:
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
    return lines, dropped


def _context_block(
    commits: list[dict],
    mb_files: dict[str, str],
    truncated: bool,
) -> str:
    lines, dropped = _commit_lines(commits)
    parts = [
        "Ниже список коммитов (git log) за период, новые сверху:",
        "\n".join(lines),
    ]
    if truncated or dropped:
        parts.append(
            f"ВНИМАНИЕ: список обрезан, показаны новейшие {len(lines)} коммитов "
            f"(ещё {dropped if dropped else 'много'} не поместилось). "
            "Упомяни это в ответе."
        )
    for path, text in mb_files.items():
        parts.append(f"Контекст проекта — файл {path}:\n{text[:_MB_PROMPT_CAP]}")
    return "\n\n".join(parts)


def build_prompt(
    owner: str,
    repo: str,
    commits: list[dict],
    mb_files: dict[str, str],
    label: str,
    truncated: bool,
    brief: bool = False,
) -> str:
    intro = (
        f"Ты — аналитик истории разработки. Репозиторий: {owner}/{repo}. "
        f"Период: {label}."
    )
    context = _context_block(commits, mb_files, truncated)
    if brief:
        task = (
            "Дай ОЧЕНЬ краткую выжимку (1–3 предложения, не больше 60 слов) "
            "того, что добавилось и изменилось в проекте за период. Только суть, "
            "без заголовков и списков. Опирайся только на коммиты и файлы, не выдумывай. "
            "Ответ на русском, plain text, без вступлений и без обрамляющих ```."
        )
    else:
        task = (
            "Составь на русском языке сводку того, что добавилось и изменилось "
            "в проекте за выбранный период. Сгруппируй по темам: новые функции, "
            "исправления, рефакторинг, тесты/документация/прочее. Выдели главное. "
            "Опирайся только на сообщения коммитов и приведённые файлы, не выдумывай. "
            "Файлы memory_bank используй как контекст статуса проекта. "
            "Ответ в Markdown, без вступлений и без обрамляющих ```."
        )
    return "\n\n".join([intro, context, task])


def build_ask_prompt(
    owner: str,
    repo: str,
    commits: list[dict],
    mb_files: dict[str, str],
    label: str,
    truncated: bool,
    question: str,
) -> str:
    intro = (
        f"Ты — аналитик истории разработки. Репозиторий: {owner}/{repo}. "
        f"Период: {label}."
    )
    context = _context_block(commits, mb_files, truncated)
    task = (
        f"Вопрос пользователя о конкретном моменте: {question}\n\n"
        "Ответь на русском языке кратко и по делу, опираясь ТОЛЬКО на приведённые "
        "коммиты и файлы memory_bank. Если в данных нет ответа — прямо скажи, что "
        "в истории за этот период этого не видно, и не выдумывай. Упоминай конкретные "
        "коммиты (sha/дата), когда это уместно. Ответ в Markdown, без вступлений "
        "и без обрамляющих ```."
    )
    return "\n\n".join([intro, context, task])


_FALLBACK_GROUPS = (
    ("feat", "Новые функции"),
    ("fix", "Исправления"),
    ("refactor", "Рефакторинг"),
    ("test", "Тесты"),
    ("docs", "Документация"),
    ("chore", "Прочее / обслуживание"),
)


def build_fallback_summary(
    commits: list[dict], label: str, truncated: bool, brief: bool = False
) -> str:
    """Детерминированная сводка по сообщениям коммитов, когда ИИ недоступен.

    Группирует коммиты по префиксу conventional-commits; не выдумывает ничего
    сверх сообщений. Гарантирует, что страница отдаёт результат даже при
    отказе/рейт-лимите всех ИИ-провайдеров.
    """
    buckets: dict[str, list[str]] = {key: [] for key, _ in _FALLBACK_GROUPS}
    other: list[str] = []
    for c in commits:
        msg = (c.get("message") or "").splitlines()[0].strip()
        line = f"- {c.get('date', '')[:10]} `{c.get('sha', '')}` {msg}"
        low = msg.lower()
        for key, _ in _FALLBACK_GROUPS:
            if low.startswith(key + ":") or low.startswith(key + "("):
                buckets[key].append(line)
                break
        else:
            other.append(line)
    buckets["chore"].extend(other)

    note = (
        "_ИИ сейчас недоступен — ниже автоматическая сводка по сообщениям "
        "коммитов (без анализа содержимого)._"
    )
    if brief:
        counts = ", ".join(
            f"{title.lower()}: {len(buckets[key])}"
            for key, title in _FALLBACK_GROUPS
            if buckets[key]
        )
        body = f"За период «{label}»: {len(commits)} коммитов ({counts or 'без разбивки'})."
        return note + "\n\n" + body

    parts = [note, f"## История за период «{label}» — {len(commits)} коммитов"]
    for key, title in _FALLBACK_GROUPS:
        if buckets[key]:
            parts.append(
                f"### {title} ({len(buckets[key])})\n" + "\n".join(buckets[key])
            )
    if truncated:
        parts.append("_Список коммитов обрезан лимитом — показаны новейшие._")
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
    .btnrow { display: flex; gap: 12px; margin-top: 16px; }
    button.go {
        flex: 1; padding: 12px; font-size: 16px; border: none; border-radius: 8px;
        background: var(--bb-accent); color: #fff; cursor: pointer;
    }
    button.go.secondary { background: var(--bb-elev); color: var(--bb-text); border: 1px solid var(--bb-border); }
    button.go:disabled { opacity: .6; cursor: wait; }
    #rhMeta { color: var(--bb-muted); font-size: 13px; margin: 18px 0 6px; }
    #rhWarn { color: #d97706; font-size: 13px; margin: 4px 0; }
    #rhResult, #rhAnswer { background: var(--bb-panel); border: 1px solid var(--bb-border); border-radius: 12px; padding: 16px; margin-top: 8px; line-height: 1.55; overflow-wrap: anywhere; }
    #rhResult h1, #rhResult h2, #rhResult h3, #rhAnswer h1, #rhAnswer h2, #rhAnswer h3 { font-size: 18px; }
    #rhResult code, #rhAnswer code { background: var(--bb-elev); padding: 1px 5px; border-radius: 5px; }
    #rhAsk { margin-top: 18px; }
    .askrow { display: flex; gap: 10px; }
    .askrow input { flex: 1; }
    .askrow button {
        padding: 10px 18px; font-size: 15px; border: none; border-radius: 8px;
        background: var(--bb-accent); color: #fff; cursor: pointer; white-space: nowrap;
    }
    .askrow button:disabled { opacity: .6; cursor: wait; }
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
        <div class="btnrow">
            <button class="go" id="rhGo">📜 Прочитать историю</button>
            <button class="go secondary" id="rhBrief">⚡ Короче</button>
        </div>
    </div>
    <div id="rhError"></div>
    <div id="rhMeta"></div>
    <div id="rhWarn"></div>
    <div id="rhResult" class="hidden"></div>
    <div id="rhAsk" class="hidden">
        <label for="rhQuestion">Спросить у ИИ о конкретном моменте</label>
        <div class="askrow">
            <input type="text" id="rhQuestion" placeholder="Например: что изменилось в авторизации?">
            <button id="rhAskBtn">Спросить</button>
        </div>
        <div id="rhAnswer" class="hidden"></div>
    </div>
</div>
<script>
(function () {
    var urlEl = document.getElementById('rhUrl');
    var periodEl = document.getElementById('rhPeriod');
    var datesEl = document.getElementById('rhDates');
    var sinceEl = document.getElementById('rhSince');
    var untilEl = document.getElementById('rhUntil');
    var goEl = document.getElementById('rhGo');
    var briefEl = document.getElementById('rhBrief');
    var errEl = document.getElementById('rhError');
    var metaEl = document.getElementById('rhMeta');
    var warnEl = document.getElementById('rhWarn');
    var resEl = document.getElementById('rhResult');
    var askEl = document.getElementById('rhAsk');
    var questionEl = document.getElementById('rhQuestion');
    var askBtnEl = document.getElementById('rhAskBtn');
    var answerEl = document.getElementById('rhAnswer');
    var lastCtx = null;

    function isoDaysAgo(n) {
        var d = new Date(Date.now() - n * 86400000);
        return d.toISOString().slice(0, 10);
    }
    sinceEl.value = isoDaysAgo(30);
    untilEl.value = isoDaysAgo(0);

    periodEl.addEventListener('change', function () {
        datesEl.classList.toggle('hidden', periodEl.value !== 'custom');
    });

    function renderMarkdown(el, md) {
        el.classList.remove('hidden');
        if (window.marked && window.DOMPurify && typeof window.DOMPurify.sanitize === 'function') {
            el.innerHTML = window.DOMPurify.sanitize(window.marked.parse(md), {USE_PROFILES: {html: true}});
        } else {
            el.textContent = md;
        }
    }

    function fail(msg) { errEl.textContent = msg; }

    function authHeaders() {
        var hdrs = {'Content-Type': 'application/json'};
        var tok = localStorage.getItem('web_token');
        if (tok) hdrs['X-Auth-Token'] = tok;
        return hdrs;
    }

    function parseBody(r) {
        return r.text().then(function (t) {
            var j = null;
            try { j = JSON.parse(t); } catch (e) {}
            return {status: r.status, body: j};
        });
    }

    function buildBody() {
        var url = urlEl.value.trim();
        if (!url) { fail('Вставьте ссылку на репозиторий'); return null; }
        var body = {url: url};
        if (periodEl.value === 'custom') {
            body.since = sinceEl.value;
            body.until = untilEl.value;
            if (!body.since || !body.until) { fail('Укажите обе даты'); return null; }
        } else {
            body.days = parseInt(periodEl.value, 10);
        }
        return body;
    }

    function setBusy(busy, brief) {
        goEl.disabled = busy;
        briefEl.disabled = busy;
        goEl.textContent = busy && !brief ? '⏳ Читаю историю и спрашиваю ИИ…' : '📜 Прочитать историю';
        briefEl.textContent = busy && brief ? '⏳ Сжимаю…' : '⚡ Короче';
    }

    function runAnalyze(brief) {
        errEl.textContent = '';
        metaEl.textContent = '';
        warnEl.textContent = '';
        resEl.classList.add('hidden');
        askEl.classList.add('hidden');
        answerEl.classList.add('hidden');
        var body = buildBody();
        if (!body) return;
        body.brief = brief;
        setBusy(true, brief);
        fetch('/api/repo_history/analyze', {method: 'POST', headers: authHeaders(), body: JSON.stringify(body)})
            .then(parseBody)
            .then(function (res) {
                if (res.status === 200 && res.body && res.body.summary) {
                    var b = res.body;
                    lastCtx = {url: body.url, days: body.days, since: body.since, until: body.until};
                    metaEl.textContent = b.repo + ' · ' + b.period + ' · коммитов: ' + b.commit_count +
                        (b.brief ? ' · кратко' : '') +
                        (b.memory_bank_files && b.memory_bank_files.length ? ' · memory_bank: ' + b.memory_bank_files.join(', ') : '');
                    if (b.truncated) warnEl.textContent = '⚠️ История длинная — показаны новейшие ' + b.commit_count + ' коммитов.';
                    renderMarkdown(resEl, b.summary);
                    askEl.classList.remove('hidden');
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
            .finally(function () { setBusy(false, brief); });
    }

    function ask() {
        errEl.textContent = '';
        if (!lastCtx) { fail('Сначала прочитайте историю репозитория'); return; }
        var q = questionEl.value.trim();
        if (!q) { fail('Введите вопрос'); return; }
        answerEl.classList.add('hidden');
        askBtnEl.disabled = true;
        askBtnEl.textContent = '⏳ Думаю…';
        var body = {url: lastCtx.url, days: lastCtx.days, since: lastCtx.since, until: lastCtx.until, question: q};
        fetch('/api/repo_history/ask', {method: 'POST', headers: authHeaders(), body: JSON.stringify(body)})
            .then(parseBody)
            .then(function (res) {
                if (res.status === 200 && res.body && res.body.answer) {
                    renderMarkdown(answerEl, res.body.answer);
                } else if (res.body && res.body.error) {
                    fail(res.body.error);
                } else if (res.status === 429) {
                    fail('Слишком много вопросов, подождите немного.');
                } else if (res.status === 502 || res.status === 504) {
                    fail('ИИ временно недоступен, попробуйте позже.');
                } else {
                    fail('Не удалось получить ответ (код ' + res.status + ').');
                }
            })
            .catch(function () { fail('Сервис недоступен, проверьте сеть.'); })
            .finally(function () {
                askBtnEl.disabled = false;
                askBtnEl.textContent = 'Спросить';
            });
    }

    goEl.addEventListener('click', function () { runAnalyze(false); });
    briefEl.addEventListener('click', function () { runAnalyze(true); });
    askBtnEl.addEventListener('click', ask);
    questionEl.addEventListener('keydown', function (e) { if (e.key === 'Enter') ask(); });
    urlEl.addEventListener('keydown', function (e) { if (e.key === 'Enter') runAnalyze(false); });
})();
</script>
</body>
</html>"""
