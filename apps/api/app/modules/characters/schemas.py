from pydantic import BaseModel, ConfigDict, Field


class CharacterAttributeUpdate(BaseModel):
    key: str = Field(min_length=1)
    value: int | None = Field(default=None, ge=0, le=999)


class UpdateCharacterRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    editor_id: str = Field(alias="editorId", min_length=1)
    basic: dict[str, str] | None = None
    attributes: list[CharacterAttributeUpdate] | None = None
    keeper_notes: str | None = Field(default=None, alias="keeperNotes", max_length=3000)
    locked_fields: list[str] | None = Field(default=None, alias="lockedFields")
