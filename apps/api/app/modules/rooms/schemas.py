from pydantic import BaseModel, ConfigDict, Field
from typing import Optional


class CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class CreateRoomRequest(CamelModel):
    name: str = Field(min_length=1, max_length=80)
    keeper_name: str = Field(alias="keeperName", min_length=1, max_length=40)
    password: Optional[str] = Field(default=None, max_length=32)
    role: Optional[str] = Field(default="player")


class JoinRoomRequest(CamelModel):
    invite_code: str = Field(alias="inviteCode", min_length=4, max_length=16)
    display_name: str = Field(alias="displayName", min_length=1, max_length=40)
    password: Optional[str] = Field(default=None, max_length=32)
    role: Optional[str] = Field(default="player")


class ReplyToRef(BaseModel):
    id: str
    sender_name: str = Field(alias="senderName")
    content: str


class SendMessageRequest(CamelModel):
    sender_id: Optional[str] = Field(default=None, alias="senderId")
    content: str = Field(min_length=1, max_length=2000)
    reply_to: Optional[ReplyToRef] = Field(default=None, alias="replyTo")
    type: Optional[str] = Field(default="text")
    private_to: Optional[str] = Field(default=None, alias="privateTo")
    whisper_to: Optional[str] = Field(default=None, alias="whisperTo")
    mention_ids: Optional[list[str]] = Field(default=None, alias="mentionIds")


# ── Structured Skill/Attribute Check ──

class CheckRequest(CamelModel):
    character_id: str = Field(alias="characterId")
    skill_name: Optional[str] = Field(default=None, alias="skillName")
    attribute_key: Optional[str] = Field(default=None, alias="attributeKey")
    difficulty: str = Field(default="regular")
    hidden: bool = Field(default=False)


class SanCheckRequest(CamelModel):
    character_id: str = Field(alias="characterId")
    success_loss: str = Field(alias="successLoss")
    failure_loss: str = Field(alias="failureLoss")
    hidden: bool = Field(default=False)


# ── Combat ──

class CombatActionRequest(CamelModel):
    attacker_id: str = Field(alias="attackerId")
    weapon_index: int = Field(default=0, alias="weaponIndex")
    defender_id: str = Field(alias="defenderId")
    action_type: str = Field(default="attack", alias="actionType")
    hidden: bool = Field(default=False)


# ── Chase ──

class ChaseActionRequest(CamelModel):
    participant_id: str = Field(alias="participantId")
    action_type: str = Field(default="speed_check", alias="actionType")
    weapon_index: Optional[int] = Field(default=None, alias="weaponIndex")
    hidden: bool = Field(default=False)


# ── Module Intro ──

class UpdateIntroRequest(CamelModel):
    editor_id: str = Field(alias="editorId")
    intro: str = Field(default="", max_length=5000)
