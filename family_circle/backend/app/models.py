import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Room(Base):
    __tablename__ = "rooms"

    id = Column(String(20), primary_key=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    status = Column(String(20), default="active", nullable=False)
    participants_total = Column(Integer, nullable=False)
    spoke_count = Column(Integer, default=0, nullable=False)

    members = relationship("Member", back_populates="room", cascade="all, delete-orphan")
    needs = relationship("Need", back_populates="room", cascade="all, delete-orphan")
    final_reports = relationship("FinalReport", back_populates="room", cascade="all, delete-orphan")


class Member(Base):
    __tablename__ = "members"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    room_id = Column(String(20), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    display_name = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    finished = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    room = relationship("Room", back_populates="members")
    messages = relationship("Message", back_populates="member", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    member_id = Column(String(36), ForeignKey("members.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    response = Column(Text, nullable=True)
    intent_type = Column(String(20), nullable=True)
    needs_extracted = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    member = relationship("Member", back_populates="messages")


class Need(Base):
    __tablename__ = "needs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    room_id = Column(String(20), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    need_text = Column(Text, nullable=False)
    member_id = Column(String(36), ForeignKey("members.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    room = relationship("Room", back_populates="needs")


class FinalReport(Base):
    __tablename__ = "final_reports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    room_id = Column(String(20), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    report_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    room = relationship("Room", back_populates="final_reports")
