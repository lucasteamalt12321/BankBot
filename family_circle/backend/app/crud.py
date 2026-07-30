import hashlib
import json
import secrets
import random
import os
from sqlalchemy.orm import Session
from sqlalchemy import select
from app import models, crypto


# --- Password hashing ---
def _hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    return salt + ":" + hashlib.sha256((salt + password).encode()).hexdigest()


def _check_password(password: str, stored: str) -> bool:
    salt, hsh = stored.split(":", 1)
    return hashlib.sha256((salt + password).encode()).hexdigest() == hsh


# --- Rooms ---
def _generate_room_id(db: Session) -> str:
    while True:
        rid = str(random.randint(100000, 999999))
        if not db.get(models.Room, rid):
            return rid


def _generate_password(length: int = 5) -> str:
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(chars) for _ in range(length))


def create_room(db: Session, name: str, creator_name: str) -> dict:
    room = models.Room(id=_generate_room_id(db), name=name, participants_total=1)
    db.add(room)
    db.flush()

    creator_display = creator_name.strip() or "Я"
    raw_password = _generate_password()

    member = models.Member(
        room_id=room.id,
        display_name=creator_display,
        password_hash=_hash_password(raw_password),
    )
    db.add(member)

    db.commit()
    db.refresh(room)

    return {
        "room_id": room.id,
        "your_name": creator_display,
        "your_password": raw_password,
        "members": [m.display_name for m in get_room_members(db, room.id)],
    }


def join_room(db: Session, room_id: str, member_name: str) -> dict:
    room = get_room(db, room_id)
    if not room:
        raise ValueError("Комната не найдена")

    existing = get_member_by_name(db, room_id, member_name)
    if existing:
        return {"ok": True, "your_password": None, "is_new": False}

    raw_password = _generate_password()
    member = models.Member(
        room_id=room_id,
        display_name=member_name.strip(),
        password_hash=_hash_password(raw_password),
    )
    db.add(member)
    db.commit()

    room.participants_total = room.participants_total + 1
    db.commit()

    return {"ok": True, "your_password": raw_password, "is_new": True}


def get_room(db: Session, room_id: str) -> models.Room | None:
    return db.get(models.Room, room_id)


def delete_room(db: Session, room_id: str) -> bool:
    room = db.get(models.Room, room_id)
    if not room:
        return False
    db.delete(room)
    db.commit()
    return True


def get_room_members(db: Session, room_id: str) -> list[models.Member]:
    return list(db.execute(
        select(models.Member).where(models.Member.room_id == room_id)
    ).scalars().all())


def get_member_by_name(db: Session, room_id: str, name: str) -> models.Member | None:
    return db.execute(
        select(models.Member).where(
            models.Member.room_id == room_id,
            models.Member.display_name == name,
        )
    ).scalar_one_or_none()


def verify_member(db: Session, room_id: str, name: str, password: str) -> models.Member | None:
    member = get_member_by_name(db, room_id, name)
    if not member:
        return None
    if not _check_password(password, member.password_hash):
        return None
    return member


# --- Messages ---
def get_room_messages(db: Session, room_id: str) -> list[dict]:
    msgs = db.execute(
        select(models.Message, models.Member.display_name)
        .join(models.Member, models.Message.member_id == models.Member.id)
        .where(models.Member.room_id == room_id)
        .order_by(models.Message.created_at)
    ).all()
    result = []
    for msg, name in msgs:
        result.append({
            "content": crypto.decrypt(msg.content),
            "response": crypto.decrypt(msg.response) if msg.response else None,
            "member_name": name,
        })
    return result


def create_message(
    db: Session,
    member_id: str,
    content: str,
    response: str | None = None,
    intent_type: str | None = None,
    needs_extracted: list[dict] | None = None,
) -> models.Message:
    msg = models.Message(
        member_id=member_id,
        content=crypto.encrypt(content),
        response=crypto.encrypt(response) if response else None,
        intent_type=intent_type,
        needs_extracted=crypto.encrypt(json.dumps(needs_extracted, ensure_ascii=False)) if needs_extracted else None,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


# --- Needs ---
def add_need(db: Session, room_id: str, need_text: str, member_id: str | None = None) -> models.Need:
    need = models.Need(room_id=room_id, need_text=need_text, member_id=member_id)
    db.add(need)
    db.commit()
    db.refresh(need)
    return need


def get_room_needs_text(db: Session, room_id: str) -> str:
    needs = list(db.execute(
        select(models.Need).where(models.Need.room_id == room_id)
    ).scalars().all())
    if not needs:
        return "Пока нет зафиксированных потребностей."
    lines = [f"- {n.need_text}" for n in needs]
    return "\n".join(lines)


# --- Members ---
def finish_member(db: Session, member: models.Member) -> None:
    member.finished = True
    db.commit()


def count_spoken(db: Session, room_id: str) -> int:
    return db.execute(
        select(models.Member).where(
            models.Member.room_id == room_id,
            models.Member.finished,
        )
    ).scalars().all().__len__()


# --- Reports ---
def save_report(db: Session, room_id: str, report_text: str) -> models.FinalReport:
    report = models.FinalReport(room_id=room_id, report_text=report_text)
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def get_report(db: Session, room_id: str) -> models.FinalReport | None:
    return db.execute(
        select(models.FinalReport).where(
            models.FinalReport.room_id == room_id
        ).order_by(models.FinalReport.created_at.desc())
    ).scalar_one_or_none()
