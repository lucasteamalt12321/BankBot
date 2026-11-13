"""Игровой Universe-модуль: чистая логика + интеграция с Telegram-вебхуком."""

import random
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine, text

import api.index as idx
from api import universe_runtime as universe


@pytest.fixture()
def engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'universe.db'}")
    idx._ensure_universe_tables(eng)
    yield eng
    eng.dispose()


def _status(engine, uid):
    with engine.connect() as conn:
        return (
            conn.execute(
                text(
                    "SELECT virus_type, infected_at, tea_cooldown_until FROM infection_status WHERE user_id = :u"
                ),
                {"u": uid},
            )
            .mappings()
            .first()
        )


# ── Чистая логика ──────────────────────────────────────────────────────────


def test_infect_creates_status_and_random_virus(engine):
    outcome, infection = universe.infect(engine, 101)

    assert outcome == "infected"
    assert infection is not None
    assert infection.virus_type in universe.VIRUSES
    assert infection.infected_at is not None
    assert _status(engine, 101)["virus_type"] == infection.virus_type


def test_infect_respects_explicit_virus_and_aliases(engine):
    outcome, infection = universe.infect(engine, 102, virus="ltl")

    assert outcome == "infected"
    assert infection.virus_type == universe.LTL_PARASITE
    assert universe.normalize_virus("Олеговирус") == universe.OLEGOVIRUS
    assert universe.normalize_virus("что-то") is None


def test_infect_immunity_blocks_reinfection_within_24h(engine):
    now = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
    universe.infect(engine, 103, virus=universe.OLEGOVIRUS, now=now)

    outcome, infection = universe.infect(
        engine, 103, virus=universe.LTL_PARASITE, now=now + timedelta(hours=23)
    )

    assert outcome == "immunity"
    assert infection.virus_type == universe.OLEGOVIRUS


def test_infect_allows_new_virus_after_immunity(engine):
    now = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
    universe.infect(engine, 104, virus=universe.OLEGOVIRUS, now=now)

    outcome, infection = universe.infect(
        engine, 104, virus=universe.LTL_PARASITE, now=now + timedelta(hours=25)
    )

    assert outcome == "infected"
    assert infection.virus_type == universe.LTL_PARASITE


def test_infect_only_if_healthy_does_not_reroll(engine):
    universe.infect(engine, 105, virus=universe.OLEGOVIRUS)

    outcome, infection = universe.infect(
        engine, 105, virus=universe.LTL_PARASITE, only_if_healthy=True
    )

    assert outcome == "already"
    assert infection.virus_type == universe.OLEGOVIRUS


def test_spread_requires_infected_source(engine):
    outcome, infection = universe.spread(engine, 110, 111)

    assert outcome == "not_infected"
    assert infection is None
    assert _status(engine, 111) is None


def test_spread_passes_virus_and_does_not_overwrite_target(engine):
    universe.infect(engine, 112, virus=universe.OLEGOVIRUS)

    outcome, infection = universe.spread(engine, 112, 113)
    assert outcome == "spread"
    assert infection.virus_type == universe.OLEGOVIRUS

    universe.cure(engine, 112)
    universe.infect(engine, 112, virus=universe.LTL_PARASITE)
    outcome, infection = universe.spread(engine, 112, 113)

    assert outcome == "target_infected"
    assert infection.virus_type == universe.OLEGOVIRUS


def test_cure_deletes_status_and_remembers_virus(engine):
    universe.infect(engine, 114, virus=universe.LTL_PARASITE)

    outcome, infection = universe.cure(engine, 114)

    assert outcome == "cured"
    assert infection.virus_type == universe.LTL_PARASITE
    assert _status(engine, 114) is None


def test_cure_healthy_user(engine):
    outcome, infection = universe.cure(engine, 115)

    assert outcome == "not_infected"
    assert infection is None


def test_tea_sets_cooldown_and_relieves_symptoms(engine):
    now = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
    universe.infect(engine, 116, virus=universe.OLEGOVIRUS, now=now)

    outcome, minutes, infection = universe.drink_tea(engine, 116, now=now)

    assert outcome == "relieved"
    assert minutes == 60
    assert infection.tea_until == now + universe.TEA_RELIEF
    assert not universe.is_symptomatic(infection, now + timedelta(minutes=30))
    assert universe.is_symptomatic(infection, now + timedelta(minutes=61))


def test_tea_cooldown_and_healthy_user(engine):
    now = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
    universe.infect(engine, 117, virus=universe.OLEGOVIRUS, now=now)
    universe.drink_tea(engine, 117, now=now)

    outcome, minutes, _ = universe.drink_tea(
        engine, 117, now=now + timedelta(minutes=20)
    )
    assert outcome == "cooldown"
    assert minutes == 40

    outcome, minutes, infection = universe.drink_tea(engine, 118, now=now)
    assert outcome == "not_infected"
    assert minutes == 0
    assert infection is None


def test_modify_text_and_caption_depend_on_virus():
    oleg = universe.modify_text("привет мир", universe.OLEGOVIRUS)
    ltl = universe.modify_text("привет мир", universe.LTL_PARASITE)

    # Олеговирус вставляет вокальный тик между словами.
    assert any(tick in oleg for tick in universe.TICKS)
    assert "привет" in oleg
    assert "мир" in oleg
    assert ltl == "привет мир ☕"
    assert universe.caption_for(universe.OLEGOVIRUS) == ""
    assert "LTL" in universe.caption_for(universe.LTL_PARASITE)
    assert (
        len(universe.modify_text("а" * 500, universe.LTL_PARASITE))
        == universe.MAX_MODIFIED_LEN
    )
    assert (
        len(universe.modify_text("а" * 500, universe.OLEGOVIRUS))
        <= universe.MAX_MODIFIED_LEN
    )


def test_modify_text_is_deterministic_with_seeded_rng():
    first = universe.modify_text(
        "привет мир", universe.OLEGOVIRUS, rng=random.Random(7)
    )
    second = universe.modify_text(
        "привет мир", universe.OLEGOVIRUS, rng=random.Random(7)
    )

    assert first == second


def test_format_infected_message_prefixes_author_name():
    message = universe.format_infected_message(
        "Рома", "привет мир", universe.OLEGOVIRUS
    )

    assert message.startswith("Рома:\n")
    body = message.split("\n", 1)[1]
    assert any(tick in body for tick in universe.TICKS)
    assert "привет" in body


def test_display_name_falls_back_to_username_and_anonymous():
    assert (
        universe.display_name({"first_name": "Олег", "last_name": "Степан"})
        == "Олег Степан"
    )
    assert universe.display_name({"username": "oleg"}) == "oleg"
    assert universe.display_name({}) == "Аноним"
    assert universe.display_name(None) == "Аноним"


def test_status_text_for_healthy_and_infected(engine):
    assert "не заражены" in universe.status_text(None)

    now = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
    universe.infect(engine, 119, virus=universe.LTL_PARASITE, now=now)
    universe.drink_tea(engine, 119, now=now)
    text_value = universe.status_text(
        universe.load_infection(engine, 119), now + timedelta(minutes=5)
    )

    assert "LTL-паразит" in text_value
    assert "Чай: облегчение ещё 55 мин." in text_value


def test_leaderboard_orders_by_infection_time(engine):
    start = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
    universe.infect(engine, 121, virus=universe.OLEGOVIRUS, now=start)
    universe.infect(
        engine, 120, virus=universe.LTL_PARASITE, now=start + timedelta(hours=1)
    )

    board = universe.leaderboard(engine)

    assert [uid for uid, _, _ in board] == [121, 120]


def test_question_strength_detects_explicit_and_general_questions():
    assert universe.question_strength("кто такой олеговирус") == "strong"
    assert universe.question_strength("что за вирус") == "strong"
    assert universe.question_strength("почему ты кхм-кхм пишешь") == "strong"
    assert universe.question_strength("что это такое?") == "weak"
    assert universe.question_strength("что это") == "weak"
    assert universe.question_strength("привет, как дела") == ""
    assert universe.question_strength("") == ""


def test_is_virus_question_needs_active_chat_for_general_questions():
    assert universe.is_virus_question("кто такой олеговирус") is True
    assert universe.is_virus_question("что это") is False
    assert universe.is_virus_question("что это", active_chat=True) is True
    # Упоминание вируса в самом вопросе делает его явным.
    assert universe.is_virus_question("а кхм-кхм это что?") is True


def test_virus_explainer_mentions_virus_and_recovery():
    oleg = universe.virus_explainer(universe.OLEGOVIRUS)
    ltl = universe.virus_explainer(universe.LTL_PARASITE)

    assert "олеговирус" in oleg.lower()
    assert "кхм-кхм" in oleg
    assert "/cure" in oleg
    assert "LTL-паразит" in ltl
    assert "/tea" in ltl
    # Без указанного вируса — объяснение олеговируса.
    assert universe.virus_explainer() == oleg


def test_chat_activity_records_and_expires(engine):
    now = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
    universe.mark_chat_activity(engine, -100500, universe.OLEGOVIRUS, now=now)

    activity = universe.chat_activity(engine, -100500, now=now + timedelta(minutes=10))
    assert activity is not None
    assert activity[0] == universe.OLEGOVIRUS

    assert universe.chat_activity(engine, -100500, now=now + timedelta(hours=5)) is None
    assert universe.chat_activity(engine, -100999, now=now) is None


# ── Telegram-вебхук ────────────────────────────────────────────────────────


def _update(text_value, *, uid=501, chat_id=None, message_id=1, reply_from=None):
    chat = uid if chat_id is None else chat_id
    message = {
        "message_id": message_id,
        "text": text_value,
        "chat": {"id": chat, "type": "private" if chat == uid else "group"},
        "from": {"id": uid, "first_name": "Tester"},
    }
    if reply_from is not None:
        message["reply_to_message"] = {
            "message_id": message_id - 1,
            "text": "чужое сообщение",
            "from": {"id": reply_from, "first_name": "Target"},
        }
    return {"update_id": 1, "message": message}


def _post(client, update):
    return client.post(f"/telegram/webhook/{idx.WEBHOOK_SECRET}", json=update)


@pytest.mark.allow_telegram
def test_webhook_infect_virus_cure_flow(engine):
    client = idx.app.test_client()
    ok = Mock(status_code=200, text="")

    with (
        patch("api.index.get_db_engine", return_value=engine),
        patch("api.index.requests.post", return_value=ok) as send,
    ):
        _post(client, _update("/infect олеговирус"))
        assert "Вы заражены «олеговирус»" in send.call_args.kwargs["json"]["text"]

        _post(client, _update("/virus"))
        assert "Заражение: «олеговирус»" in send.call_args.kwargs["json"]["text"]

        _post(client, _update("/cure"))
        assert "вылечены от «олеговирус»" in send.call_args.kwargs["json"]["text"]

    assert _status(engine, 501) is None


@pytest.mark.allow_telegram
def test_webhook_infected_message_is_replaced_in_group(engine):
    client = idx.app.test_client()
    ok = Mock(status_code=200, text="")
    universe.infect(engine, 502, virus=universe.OLEGOVIRUS)

    with (
        patch("api.index.get_db_engine", return_value=engine),
        patch("api.index.requests.post", return_value=ok) as send,
        patch("api.index.requests.delete") as delete,
    ):
        _post(client, _update("привет мир", uid=502, chat_id=-100500))

    delete.assert_called_once()
    payload = send.call_args.kwargs["json"]
    # Сообщение публикуется от имени бота с подписью автора.
    assert payload["text"].startswith("Tester:\n")
    body = payload["text"].split("\n", 1)[1]
    assert any(tick in body for tick in universe.TICKS)
    assert "привет" in body
    assert "заражён" not in payload["text"]


@pytest.mark.allow_telegram
def test_webhook_infection_marks_chat_active(engine):
    client = idx.app.test_client()
    ok = Mock(status_code=200, text="")
    universe.infect(engine, 506, virus=universe.OLEGOVIRUS)

    with (
        patch("api.index.get_db_engine", return_value=engine),
        patch("api.index.requests.post", return_value=ok),
        patch("api.index.requests.delete"),
    ):
        _post(client, _update("привет мир", uid=506, chat_id=-100500))

    assert universe.chat_activity(engine, -100500) is not None


@pytest.mark.allow_telegram
def test_webhook_answers_explicit_virus_question(engine):
    client = idx.app.test_client()
    ok = Mock(status_code=200, text="")

    with (
        patch("api.index.get_db_engine", return_value=engine),
        patch("api.index.requests.post", return_value=ok) as send,
    ):
        _post(client, _update("кто такой олеговирус", uid=507, chat_id=-100500))

    payload = send.call_args.kwargs["json"]
    assert "олеговирус" in payload["text"].lower()
    assert "/cure" in payload["text"]


@pytest.mark.allow_telegram
def test_webhook_answers_general_question_only_in_active_chat(engine):
    client = idx.app.test_client()
    ok = Mock(status_code=200, text="")

    with (
        patch("api.index.get_db_engine", return_value=engine),
        patch("api.index.requests.post", return_value=ok) as send,
    ):
        # Вируса в чате нет — на общее «что это?» бот не отвечает.
        _post(client, _update("что это", uid=508, chat_id=-100500))
        send.assert_not_called()

        universe.mark_chat_activity(engine, -100500, universe.OLEGOVIRUS)
        _post(client, _update("что это", uid=509, chat_id=-100500))

    payload = send.call_args.kwargs["json"]
    assert "олеговирус" in payload["text"].lower()


@pytest.mark.allow_telegram
def test_webhook_question_is_not_swallowed_by_infection(engine):
    client = idx.app.test_client()
    ok = Mock(status_code=200, text="")
    universe.infect(engine, 509, virus=universe.OLEGOVIRUS)

    with (
        patch("api.index.get_db_engine", return_value=engine),
        patch("api.index.requests.post", return_value=ok) as send,
        patch("api.index.requests.delete") as delete,
    ):
        _post(client, _update("что это за вирус", uid=509, chat_id=-100500))

    payload = send.call_args.kwargs["json"]
    assert "олеговирус" in payload["text"].lower()
    # Вопрос не переписывается вирусом и не удаляется.
    delete.assert_not_called()


@pytest.mark.allow_telegram
def test_webhook_tea_temporarily_stops_symptoms(engine):
    client = idx.app.test_client()
    ok = Mock(status_code=200, text="")
    universe.infect(engine, 503, virus=universe.LTL_PARASITE)

    with (
        patch("api.index.get_db_engine", return_value=engine),
        patch("api.index.requests.post", return_value=ok) as send,
        patch("api.index.requests.delete") as delete,
    ):
        _post(client, _update("/tea", uid=503))
        assert send.call_args.kwargs["json"]["text"].startswith("☕")

        send.reset_mock()
        _post(client, _update("просто текст", uid=503, message_id=2))

    send.assert_not_called()
    delete.assert_not_called()


@pytest.mark.allow_telegram
def test_webhook_mention_auto_infects_and_keeps_commands_working(engine):
    client = idx.app.test_client()
    ok = Mock(status_code=200, text="")

    with (
        patch("api.index.get_db_engine", return_value=engine),
        patch("api.index.requests.post", return_value=ok) as send,
        patch("api.index.requests.delete"),
    ):
        _post(client, _update("привет @olegchekmarev12", uid=504, chat_id=-100500))
        assert send.call_args is not None
        assert _status(engine, 504) is not None

        send.reset_mock()
        _post(client, _update("/cure@olegchekmarev12", uid=504, chat_id=-100500))
        assert "вылечены" in send.call_args.kwargs["json"]["text"]
        assert _status(engine, 504) is None


@pytest.mark.allow_telegram
def test_webhook_spread_requires_reply_and_infected_source(engine):
    client = idx.app.test_client()
    ok = Mock(status_code=200, text="")

    with (
        patch("api.index.get_db_engine", return_value=engine),
        patch("api.index.requests.post", return_value=ok) as send,
    ):
        _post(client, _update("/spread", uid=505, chat_id=-100500))
        assert "Ответь командой" in send.call_args.kwargs["json"]["text"]

        _post(client, _update("/spread", uid=505, chat_id=-100500, reply_from=506))
        assert "Ты сам не заражён" in send.call_args.kwargs["json"]["text"]

        universe.infect(engine, 505, virus=universe.OLEGOVIRUS)
        _post(
            client,
            _update("/spread", uid=505, chat_id=-100500, reply_from=506, message_id=3),
        )
        assert "Заражение передано" in send.call_args.kwargs["json"]["text"]

    assert _status(engine, 506)["virus_type"] == universe.OLEGOVIRUS
