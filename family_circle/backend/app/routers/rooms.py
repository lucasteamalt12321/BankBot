from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import crud, schemas

router = APIRouter(prefix="/api", tags=["rooms"])


@router.post("/rooms", response_model=schemas.RoomCreateResponse)
def create_room(body: schemas.RoomCreate, db: Session = Depends(get_db)):
    result = crud.create_room(db, body.name, body.creator_name)
    return schemas.RoomCreateResponse(
        room_id=result["room_id"],
        your_name=result["your_name"],
        your_password=result["your_password"],
        invite_link=f"/?room_id={result['room_id']}",
        members=result["members"],
    )


@router.post("/rooms/join", response_model=schemas.RoomJoinResponse)
def join_room(body: schemas.RoomJoin, db: Session = Depends(get_db)):
    try:
        result = crud.join_room(db, body.room_id, body.member_name)
        return schemas.RoomJoinResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/rooms/{room_id}", response_model=schemas.RoomInfo)
def get_room(room_id: str, db: Session = Depends(get_db)):
    room = crud.get_room(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Комната не найдена")
    members = crud.get_room_members(db, room_id)
    return schemas.RoomInfo(
        room_id=room.id,
        name=room.name,
        status=room.status,
        members=[m.display_name for m in members],
    )


@router.delete("/rooms/{room_id}")
def delete_room(room_id: str, db: Session = Depends(get_db)):
    if not crud.delete_room(db, room_id):
        raise HTTPException(status_code=404, detail="Комната не найдена")
    return {"ok": True}
