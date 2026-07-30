from pydantic import BaseModel, Field
from typing import Optional


# --- Room ---
class RoomCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    creator_name: str = Field(default="Я", min_length=1, max_length=100)


class RoomCreateResponse(BaseModel):
    room_id: str
    your_name: str
    your_password: str
    invite_link: str
    members: list[str]


class RoomJoin(BaseModel):
    room_id: str
    member_name: str = Field(..., min_length=1, max_length=100)


class RoomJoinResponse(BaseModel):
    ok: bool
    your_password: Optional[str] = None
    is_new: bool = False


class RoomInfo(BaseModel):
    room_id: str
    name: str
    status: str
    members: list[str]


# --- Chat ---
class ChatSendRequest(BaseModel):
    room_id: str
    member_name: str
    password: str
    message: str = Field(..., min_length=1, max_length=5000)


class ChatSendResponse(BaseModel):
    response: str
    intent_type: Optional[str] = None


class ChatFinishRequest(BaseModel):
    room_id: str
    member_name: str
    password: str


class ChatFinishResponse(BaseModel):
    ok: bool


# --- Report ---
class ReportGenerateRequest(BaseModel):
    room_id: str
    member_name: str
    password: str


class ReportGenerateResponse(BaseModel):
    report_text: str


# --- Error ---
class ErrorResponse(BaseModel):
    detail: str
