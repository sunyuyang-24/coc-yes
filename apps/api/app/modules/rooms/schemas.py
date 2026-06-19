from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, Literal


class CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class CreateRoomRequest(CamelModel):
    name: str = Field(min_length=1, max_length=80, pattern=r"\S")
    keeper_name: str = Field(alias="keeperName", min_length=1, max_length=40, pattern=r"\S")
    password: Optional[str] = Field(default=None, max_length=32)
    role: Optional[str] = Field(default="player")


class JoinRoomRequest(CamelModel):
    invite_code: str = Field(alias="inviteCode", min_length=4, max_length=16)
    display_name: str = Field(alias="displayName", min_length=1, max_length=40, pattern=r"\S")
    password: Optional[str] = Field(default=None, max_length=32)
    role: Optional[str] = Field(default="player")


class ReplyToRef(BaseModel):
    id: str
    sender_name: str = Field(alias="senderName")
    content: str


class AttachmentRef(CamelModel):
    url: str
    filename: str
    size: int
    content_type: str = Field(alias="contentType")


class SendMessageRequest(CamelModel):
    sender_id: Optional[str] = Field(default=None, alias="senderId")
    content: str = Field(min_length=0, max_length=2000)
    reply_to: Optional[ReplyToRef] = Field(default=None, alias="replyTo")
    type: Optional[str] = Field(default="text")
    private_to: Optional[str] = Field(default=None, alias="privateTo")
    whisper_to: Optional[str] = Field(default=None, alias="whisperTo")
    mention_ids: Optional[list[str]] = Field(default=None, alias="mentionIds")
    attachments: Optional[list[AttachmentRef]] = Field(default=None)
    as_character_id: Optional[str] = Field(default=None, alias="asCharacterId")


# ── Structured Skill/Attribute Check ──

class CheckRequest(CamelModel):
    character_id: str = Field(alias="characterId")
    skill_name: Optional[str] = Field(default=None, alias="skillName")
    attribute_key: Optional[str] = Field(default=None, alias="attributeKey")
    difficulty: str = Field(default="regular")
    hidden: bool = Field(default=False)
    editor_id: Optional[str] = Field(default=None, alias="editorId")
    opponent_character_id: Optional[str] = Field(default=None, alias="opponentCharacterId")
    opponent_skill_name: Optional[str] = Field(default=None, alias="opponentSkillName")
    opponent_attribute_key: Optional[str] = Field(default=None, alias="opponentAttributeKey")


class SanCheckRequest(CamelModel):
    character_id: str = Field(alias="characterId")
    success_loss: str = Field(alias="successLoss")
    failure_loss: str = Field(alias="failureLoss")
    hidden: bool = Field(default=False)


# ── Combat (COC 7e Melee) ──

CombatActionType = Literal["melee_attack", "melee_maneuver", "skip"]
CombatDefenseType = Literal["dodge", "fight_back", "maneuver", "none"]


class CombatDeclarationModel(CamelModel):
    character_id: str = Field(alias="characterId")
    action_type: CombatActionType = Field(alias="actionType")
    weapon_index: Optional[int] = Field(default=None, alias="weaponIndex")
    target_character_ids: list[str] = Field(alias="targetCharacterIds")

    @field_validator("target_character_ids")
    @classmethod
    def _single_melee_target(cls, v: list[str]) -> list[str]:
        if len(v) > 1:
            raise ValueError("近战攻击只能声明一个目标")
        return v


class CombatDefenseModel(CamelModel):
    intent_id: str = Field(alias="intentId")
    defender_character_id: str = Field(alias="defenderCharacterId")
    defense_type: CombatDefenseType = Field(alias="defenseType")
    weapon_index: Optional[int] = Field(default=None, alias="weaponIndex")


class DeclareCombatIntentsRequest(CamelModel):
    member_id: str = Field(alias="memberId")
    declarations: list[CombatDeclarationModel]


class DeclareCombatDefensesRequest(CamelModel):
    member_id: str = Field(alias="memberId")
    defenses: list[CombatDefenseModel]


class ResolveCombatRequest(CamelModel):
    editor_id: str = Field(alias="editorId")


class NextCombatRoundRequest(CamelModel):
    editor_id: str = Field(alias="editorId")


# Legacy alias (keep old field-level interface for backwards compat reference)
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
