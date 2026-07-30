import re
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import crud, schemas
from app.llm.prompts import build_system_prompt
from app.llm.client import chat_dialog

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


def _extract_needs(response_text: str, member_id: str) -> list[str]:
    needs = []
    lower = response_text.lower()
    patterns = [
        r'(?:тебе\s+)?важно\s+(.+)',
        r'(?:похоже|кажется|вижу),?\s+(?:что\s+)?(?:для\s+)?(?:тебя|тебе)\s+(.+?)(?:[.?!]|$)',
        r'(?:ценность|потребность|ценно)\s+(?:—\s+)?(.+?)(?:[.?!]|$)',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, lower)
        for m in matches:
            need = m.strip().rstrip(".,!?")
            if len(need) > 10 and need not in needs:
                needs.append(need)
    return needs


@router.post("/chat/send", response_model=schemas.ChatSendResponse)
async def send_message(body: schemas.ChatSendRequest, db: Session = Depends(get_db)):
    member = crud.verify_member(db, body.room_id, body.member_name, body.password)
    if not member:
        raise HTTPException(status_code=403, detail="Неверное имя участника или пароль")

    if member.finished:
        raise HTTPException(status_code=400, detail="Вы уже завершили диалог")

    room = crud.get_room(db, body.room_id)
    if not room or room.status != "active":
        raise HTTPException(status_code=400, detail="Комната недоступна")

    needs_text = crud.get_room_needs_text(db, body.room_id)
    members = crud.get_room_members(db, body.room_id)
    member_names = [m.display_name for m in members]
    system_prompt = build_system_prompt(room.name, member_names, room.spoke_count, needs_text)

    history = []
    for msg in crud.get_room_messages(db, body.room_id):
        history.append({"role": "user", "content": f"{msg['member_name']}: {msg['content']}"})
        if msg["response"]:
            history.append({"role": "assistant", "content": msg["response"]})

    current_message = f"{body.member_name}: {body.message}"
    response_text, intent_type = await chat_dialog(system_prompt, current_message, history)

    needs_found = _extract_needs(response_text, member.id)
    for need_text in needs_found:
        crud.add_need(db, body.room_id, need_text, member.id)

    msg = crud.create_message(
        db, member.id, body.message,
        response=response_text,
        intent_type=intent_type,
        needs_extracted=[{"need": n} for n in needs_found] if needs_found else None,
    )

    return schemas.ChatSendResponse(
        response=response_text,
        intent_type=intent_type,
    )


@router.post("/chat/finish", response_model=schemas.ChatFinishResponse)
def finish_dialog(body: schemas.ChatFinishRequest, db: Session = Depends(get_db)):
    member = crud.verify_member(db, body.room_id, body.member_name, body.password)
    if not member:
        raise HTTPException(status_code=403, detail="Неверное имя участника или пароль")

    if member.finished:
        raise HTTPException(status_code=400, detail="Вы уже завершили диалог")

    crud.finish_member(db, member)

    room = crud.get_room(db, body.room_id)
    if room:
        new_count = crud.count_spoken(db, body.room_id)
        room.spoke_count = new_count
        db.commit()

    return schemas.ChatFinishResponse(ok=True)
