import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import crud, schemas
from app.llm.prompts import build_synthesis_prompt
from app.llm.client import generate_synthesis

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["report"])


@router.post("/report/generate", response_model=schemas.ReportGenerateResponse)
async def generate_report(body: schemas.ReportGenerateRequest, db: Session = Depends(get_db)):
    member = crud.verify_member(db, body.room_id, body.member_name, body.password)
    if not member:
        raise HTTPException(status_code=403, detail="Неверное имя участника или пароль")

    room = crud.get_room(db, body.room_id)
    if not room or room.status != "active":
        raise HTTPException(status_code=400, detail="Комната недоступна")

    existing = crud.get_report(db, body.room_id)
    if existing:
        return schemas.ReportGenerateResponse(report_text=existing.report_text)

    needs_text = crud.get_room_needs_text(db, body.room_id)
    prompt = build_synthesis_prompt(needs_text)

    report_text = await generate_synthesis(prompt)

    crud.save_report(db, body.room_id, report_text)

    return schemas.ReportGenerateResponse(report_text=report_text)
