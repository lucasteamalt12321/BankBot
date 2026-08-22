"""Единая система тем (светлая/тёмная) для всех веб-страниц LTHub.

Используется как централизованный инжектор: ``inject_theme(html)`` добавляет
в <head> определения CSS-переменных (тёмная по умолчанию + светлая через
[data-theme="light"]) и скрипт без вспышки, а перед </body> — плавающую
кнопку-переключатель. Все страницы (api/index.py, reading_trainer.py и т.д.)
должны пропускать свой HTML через ``inject_theme``.

Цвета в стилях страниц заменяются на CSS-переменные (см. HEX_TO_VAR в
скрипте миграции), поэтому переключатель реально меняет оформление.
"""

from __future__ import annotations

# Определения переменных: тёмная тема — значения по умолчанию в :root,
# светлая — в [data-theme="light"].
THEME_CSS = """<style id="app-theme">
:root {
  color-scheme: dark;
  --bb-bg: #1a1a2e; --bb-card: #16213e; --bb-elev: #0f3460; --bb-border: #1a5276;
  --bb-text: #e0e0e0; --bb-text-soft: #cbd5e1; --bb-muted: #9ca3af; --bb-dim: #6b7280;
  --bb-primary: #e94560; --bb-primary-2: #d63851; --bb-gold: #f0c040;
  --bb-success: #4ade80; --bb-success-bg: #1b5e20; --bb-success-border: #2e7d32;
  --bb-danger-bg: #b71c1c; --bb-danger-border: #c62828;
  --gh-bg: #0d1117; --gh-card: #161b22; --gh-elev: #21262d; --gh-border: #30363d;
  --gh-text: #c9d1d9; --gh-text-2: #e6edf3; --gh-muted: #8b949e;
  --gh-link: #58a6ff; --gh-accent: #1f6feb; --gh-success: #238636;
  --gh-danger: #f85149; --gh-warn: #d29922; --gh-code: #0a1628; --gh-success-bg: #123b23;
}
[data-theme="light"] {
  color-scheme: light;
  --bb-bg: #eef0f7; --bb-card: #ffffff; --bb-elev: #e6e9f2; --bb-border: #c2cad8;
  --bb-text: #1f2330; --bb-text-soft: #3b4250; --bb-muted: #5c6373; --bb-dim: #8a90a0;
  --bb-primary: #d6334f; --bb-primary-2: #c02740; --bb-gold: #b58900;
  --bb-success: #15803d; --bb-success-bg: #dcfce7; --bb-success-border: #22c55e;
  --bb-danger-bg: #fee2e2; --bb-danger-border: #ef4444;
  --gh-bg: #ffffff; --gh-card: #f6f8fa; --gh-elev: #eaeef2; --gh-border: #d0d7de;
  --gh-text: #1f2328; --gh-text-2: #24292f; --gh-muted: #656d76;
  --gh-link: #0969da; --gh-accent: #0969da; --gh-success: #1a7f37;
  --gh-danger: #cf222e; --gh-warn: #9a6700; --gh-code: #f6f8fa; --gh-success-bg: #dafbe1;
}
body { background: var(--bb-bg); color: var(--bb-text); }
#theme-toggle {
  position: fixed; right: 16px; bottom: 16px; z-index: 9999;
  width: 44px; height: 44px; border-radius: 50%;
  border: 1px solid var(--bb-border); background: var(--bb-elev); color: var(--bb-text);
  font-size: 20px; line-height: 1; cursor: pointer;
  box-shadow: 0 4px 14px rgba(0,0,0,.35); transition: background .15s, color .15s;
}
#theme-toggle:hover { background: var(--bb-primary); color: #fff; }
</style>
<script id="app-theme-init">
(function () {
  try {
    var t = localStorage.getItem('theme');
    if (!t) {
      t = (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) ? 'light' : 'dark';
    }
    document.documentElement.setAttribute('data-theme', t);
  } catch (e) {}
})();
</script>"""

THEME_TOGGLE = """<script id="app-theme-toggle">
(function () {
  function apply(t) {
    document.documentElement.setAttribute('data-theme', t);
    try { localStorage.setItem('theme', t); } catch (e) {}
  }
  function current() { return document.documentElement.getAttribute('data-theme') || 'dark'; }
  function makeBtn() {
    var b = document.createElement('button');
    b.id = 'theme-toggle'; b.type = 'button';
    b.title = 'Сменить тему (светлая/тёмная)';
    b.setAttribute('aria-label', 'Сменить тему');
    b.textContent = current() === 'light' ? '☀️' : '🌙';
    b.addEventListener('click', function () {
      var n = current() === 'light' ? 'dark' : 'light';
      apply(n); b.textContent = n === 'light' ? '☀️' : '🌙';
    });
    document.body.appendChild(b);
  }
  if (document.readyState !== 'loading') makeBtn();
  else document.addEventListener('DOMContentLoaded', makeBtn);
})();
</script>"""


def inject_theme(html: str) -> str:
    """Вставляет тему в HTML страницы (идемпотентно)."""
    if "app-theme" not in html:
        if "</title>" in html:
            html = html.replace("</title>", "</title>\n" + THEME_CSS, 1)
        elif "<head>" in html:
            html = html.replace("<head>", "<head>\n" + THEME_CSS, 1)
    if "app-theme-toggle" not in html and "</body>" in html:
        html = html.replace("</body>", THEME_TOGGLE + "\n</body>", 1)
    return html
