"""Unit tests for the core.canon module and the /canon web page + APIs."""

from __future__ import annotations

import json

import pytest

from api.index import app
from core.canon import (
    CANON_DOC_URL,
    CANON_VERSION,
    canon_sections,
    canon_version,
    find_canon,
    load_canon_text,
    render_markdown,
)
from core.canon.glossary import GLOSSARY_TERMS
from core.canon.prayers import PRAYERS
from core.canon.questions import TRIVIA_QUESTIONS
from core.canon.works import CANON_WORKS, works_by_kind, works_by_level


class TestCanonModule:
    def test_text_loaded(self):
        text = load_canon_text()
        assert len(text) > 5000
        assert "БЛОК 1. ПРАВИЛА" in text
        assert "ГЛОССАРИЙ" in text

    def test_version_matches_file(self):
        assert canon_version() == CANON_VERSION
        assert "2.9" in CANON_VERSION

    def test_doc_url(self):
        assert CANON_DOC_URL.startswith("https://docs.google.com/document/d/")

    def test_sections(self):
        sections = canon_sections()
        assert len(sections) == 4
        titles = [s["title"] for s in sections]
        assert any("ПРАВИЛА" in t for t in titles)
        assert any("ГЛОССАРИЙ" in t for t in titles)
        for section in sections:
            assert section["content"]

    def test_find_canon_hit(self):
        results = find_canon("олеговирус", limit=5)
        assert results
        assert results[0]["section"]

    def test_find_canon_glossary_fallback(self):
        results = find_canon("Хранитель конфет")
        assert results

    def test_find_canon_miss(self):
        assert find_canon("несуществующийтерминxyz") == []


class TestCanonWorks:
    def test_pool_not_empty(self):
        assert len(CANON_WORKS) >= 15

    def test_levels_valid(self):
        valid = {"high", "medium", "low", "archive"}
        for work in CANON_WORKS:
            assert work.canon_level in valid
            assert work.title

    def test_high_level_has_tracks_and_articles(self):
        high = works_by_level("high")
        kinds = {w.kind for w in high}
        assert "track" in kinds
        assert "article" in kinds

    def test_works_by_kind(self):
        tracks = works_by_kind("track")
        assert tracks
        assert all(w.kind == "track" for w in tracks)


class TestCanonGlossary:
    def test_terms_not_empty(self):
        assert len(GLOSSARY_TERMS) >= 20

    def test_eight_nine_present(self):
        assert any(t.term == "eight-nine" for t in GLOSSARY_TERMS)


class TestCanonQuestions:
    def test_pool_matches_bot_and_api(self):
        # Единый пул из core.canon — источник для bot и api.
        assert len(TRIVIA_QUESTIONS) == 24

    def test_ids_unique(self):
        ids = [q["id"] for q in TRIVIA_QUESTIONS]
        assert len(ids) == len(set(ids))


class TestCanonPrayers:
    def test_prayers_not_empty(self):
        assert len(PRAYERS) == 15

    def test_prayers_contain_tea_and_eight_nine(self):
        for prayer in PRAYERS:
            assert "Чай" in prayer or "чай" in prayer
            assert "eight-nine" in prayer


class TestRenderMarkdown:
    def test_bold_and_links(self):
        html = render_markdown("Трек **«Рома»** – https://t.me/lucasteamgroup/17764")
        assert "<strong>" in html
        assert '<a href="https://t.me/lucasteamgroup/17764"' in html

    def test_escaping(self):
        html = render_markdown("a <b> & c")
        assert "<b>" not in html
        assert "&lt;b&gt;" in html


class TestCanonPage:
    def setup_method(self):
        self.client = app.test_client()

    def test_page_renders_full_text(self):
        resp = self.client.get("/canon")
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        # Оригинальный текст канона целиком.
        assert "Вселенная Олеговируса и LTL-паразита: канон" in body
        assert "БЛОК 1. ПРАВИЛА" in body
        assert "ГЛОССАРИЙ" in body
        assert "eight-nine" in body
        # Вкладки.
        assert "Полный текст" in body
        assert "Произведения" in body
        # Структурированные данные инлайном.
        assert "ALL_WORKS" in body
        assert "ALL_TERMS" in body

    def test_page_renders_markdown_links(self):
        body = self.client.get("/canon").get_data(as_text=True)
        assert "t.me/lucasteamgroup/17764" in body

    def test_api_canon_text(self):
        resp = self.client.get("/api/canon/text")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "БЛОК 1. ПРАВИЛА" in data["text"]
        assert data["version"] == CANON_VERSION

    def test_api_canon_works_filters(self):
        all_works = self.client.get("/api/canon/works").get_json()
        assert all_works["total"] == len(CANON_WORKS)
        high = self.client.get("/api/canon/works?level=high").get_json()
        assert high["total"] == len(works_by_level("high"))
        tracks = self.client.get("/api/canon/works?kind=track").get_json()
        assert tracks["total"] == len(works_by_kind("track"))

    def test_api_canon_glossary_search(self):
        all_terms = self.client.get("/api/canon/glossary").get_json()
        assert all_terms["total"] == len(GLOSSARY_TERMS)
        tea = self.client.get("/api/canon/glossary?q=%D1%87%D0%B0%D0%B9").get_json()
        assert tea["total"] >= 1

    def test_api_canon_search(self):
        results = self.client.get("/api/canon/search?q=%D0%BE%D0%BB%D0%B5%D0%B3%D0%BE%D0%B2%D0%B8%D1%80%D1%83%D1%81").get_json()
        assert results["total"] >= 1
