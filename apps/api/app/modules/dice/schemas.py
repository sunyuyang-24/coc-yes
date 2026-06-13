from pydantic import BaseModel, ConfigDict, Field


class RollDiceRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    roller_id: str = Field(alias="rollerId", min_length=1)
    expression: str = Field(min_length=2, max_length=40)
    label: str | None = Field(default=None, max_length=80)
    target_value: int | None = Field(default=None, alias="targetValue", ge=1, le=999)
    bonus_penalty: int = Field(default=0, alias="bonusPenalty", ge=-2, le=2)
    hidden: bool = Field(default=False)
    as_character_id: str | None = Field(default=None, alias="asCharacterId")
