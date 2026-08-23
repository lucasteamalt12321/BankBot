"""Единая система тем (светлая/тёмная) для всех веб-страниц LTHub.

Используется как централизованный инжектор: ``inject_theme(html)`` добавляет
в <head> определения CSS-переменных (тёмная по умолчанию + светлая через
[data-theme="light"]) и скрипт без вспышки, а перед </body> — плавающую
кнопку-переключатель.

Все страницы (``api/index.py``, ``reading_trainer.py`` и т.д.) пропускают свой
HTML через ``inject_theme``. Цвета в стилях страниц ссылаются на CSS-переменные
(``--bb-*`` и ``--gh-*`` — два параллельных неймспейса с одинаковым смыслом),
поэтому переключатель реально меняет оформление целиком.
"""

from __future__ import annotations

# Определения переменных: тёмная тема — значения по умолчанию в :root,
# светлая — в [data-theme="light"].
THEME_CSS = """<style id="app-theme">
:root {
  color-scheme: dark;
  /* Поверхности и текст */
  --bb-bg: #0f1420; --bb-panel: #171c2b; --bb-elev: #1f2638; --bb-border: #2a3346;
  --bb-text: #e6e9f0; --bb-text-soft: #c2c9d6; --bb-muted: #8b93a7; --bb-dim: #6b7280;
  --bb-ink: #cbd5e1;
  /* Бренд / акценты */
  --bb-primary: #5b8def; --bb-accent: #7aa2ff; --bb-accent2: #4a78d6; --bb-link: #7aa2ff;
  --bb-orange: #f0b429; --bb-gold: #f0c040;
  /* Статусы */
  --bb-green: #4ade80; --bb-green2: #22c55e; --bb-green3: #16a34a; --bb-green-panel: #14361f;
  --bb-red: #f87171; --bb-warn: #e3b341;
  --bb-success-bg: #14361f; --bb-success-border: #2e7d32; --bb-danger-bg: #3a1a1c; --bb-danger-border: #c62828;
  /* Параллельный неймспейс gh (тот же смысл) */
  --gh-bg: #0f1420; --gh-bg2: #1f2638; --gh-panel: #171c2b; --gh-elev: #1f2638; --gh-border: #2a3346;
  --gh-text: #e6e9f0; --gh-text2: #c2c9d6; --gh-muted: #8b93a7;
  --gh-accent: #5b8def; --gh-link: #7aa2ff; --gh-code: #0a1628;
  --gh-green: #4ade80; --gh-green-panel: #14361f; --gh-red: #f87171; --gh-warn: #e3b341;
  --gh-success: #2da44e; --gh-success-bg: #14361f;
}
[data-theme="light"] {
  color-scheme: light;
  --bb-bg: #eef1f7; --bb-panel: #ffffff; --bb-elev: #e6e9f2; --bb-border: #cdd4e1;
  --bb-text: #1f2430; --bb-text-soft: #3b4250; --bb-muted: #5c6373; --bb-dim: #8a90a0;
  --bb-ink: #1f2430;
  --bb-primary: #5b8def; --bb-accent: #4a90e8; --bb-accent2: #3b7fd6; --bb-link: #4a90e8;
  --bb-orange: #b5790a; --bb-gold: #a9790a;
  --bb-green: #16a34a; --bb-green2: #15803d; --bb-green3: #166534; --bb-green-panel: #dcfce7;
  --bb-red: #dc2626; --bb-warn: #b45309;
  --bb-success-bg: #dcfce7; --bb-success-border: #22c55e; --bb-danger-bg: #fee2e2; --bb-danger-border: #ef4444;
  --gh-bg: #eef1f7; --gh-bg2: #e6e9f2; --gh-panel: #ffffff; --gh-elev: #e6e9f2; --gh-border: #cdd4e1;
  --gh-text: #1f2430; --gh-text2: #3b4250; --gh-muted: #5c6373;
  --gh-accent: #5b8def; --gh-link: #4a90e8; --gh-code: #f5f7fa;
  --gh-green: #16a34a; --gh-green-panel: #dcfce7; --gh-red: #dc2626; --gh-warn: #b45309;
  --gh-success: #1a7f37; --gh-success-bg: #dcfce7;
}
/* Каркас страницы всегда темится (приоритет выше, чем у inline-стилей страниц) */
body { background: var(--bb-bg) !important; color: var(--bb-text) !important; }
#theme-toggle {
  position: fixed; left: 16px; bottom: 16px; z-index: 9999;
  width: 46px; height: 46px; border-radius: 50%;
  border: 1px solid var(--bb-border); background: var(--bb-elev); color: var(--bb-text);
  font-size: 20px; line-height: 1; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 16px rgba(0,0,0,.35); transition: background .15s, color .15s, transform .15s;
}
#theme-toggle:hover { background: var(--bb-primary); color: #fff; transform: scale(1.06); }
</style>
<script id="app-theme-init">
(function () {
  try {
    var t = localStorage.getItem('theme');
    if (!t) {
      t = (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light';
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
    var b = document.getElementById('theme-toggle');
    if (b) b.textContent = t === 'light' ? '☀️' : '🌙';
  }
  function current() { return document.documentElement.getAttribute('data-theme') || 'dark'; }
  function makeBtn() {
    var b = document.getElementById('theme-toggle');
    if (!b) {
      b = document.createElement('button');
      b.id = 'theme-toggle'; b.type = 'button';
      b.title = 'Сменить тему (светлая/тёмная)';
      b.setAttribute('aria-label', 'Сменить тему');
      document.body.appendChild(b);
    }
    b.textContent = current() === 'light' ? '☀️' : '🌙';
    b.onclick = function () { apply(current() === 'light' ? 'dark' : 'light'); };
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
