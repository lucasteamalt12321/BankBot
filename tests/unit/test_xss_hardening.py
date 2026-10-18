"""BUG-04: XSS-хардеринг для страниц, рендерящих текст из LLM.

Проверяем, что клиентский JS экранирует значения перед вставкой в DOM:
- `/md2pdf`: вывод `marked` обязательно проходит через DOMPurify.sanitize;
- `/ai_chat`: `src` у `<img>` из ответа модели экранируется и валидируется;
- `api/reading_trainer.py`: предложения и вопросы экранируются.
"""

from api.index import app
from api.reading_trainer import HTML_CONTENT


def test_md2pdf_sanitizes_marked_output():
    body = app.test_client().get("/md2pdf").get_data(as_text=True)
    assert "dompurify" in body.lower()
    assert "DOMPurify.sanitize" in body
    assert "sanitizeHtml" in body
    # «сырой» вывод marked больше не вставляется напрямую
    assert "page.innerHTML = out;" not in body


def test_ai_chat_escapes_image_src():
    body = app.test_client().get("/ai_chat").get_data(as_text=True)
    # src валидируется и экранируется, а не склеивается «как есть»
    assert "data:image" in body
    assert 'src="\' + src + \'"' not in body
    assert "&quot;" in body


def test_reading_trainer_escapes_llm_text():
    assert "function escHtml" in HTML_CONTENT
    assert "escHtml(s)" in HTML_CONTENT
    assert "escHtml(q.question)" in HTML_CONTENT
    # предложения из LLM не склеиваются без экранирования
    assert "'<div class=\"sentence\">' + s + '</div>'" not in HTML_CONTENT
