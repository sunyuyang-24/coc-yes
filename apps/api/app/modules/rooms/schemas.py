from pydantic import BaseModel, ConfigDict, Field


class CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class CreateRoomRequest(CamelModel):
    name: str = Field(min_length=1, max_length=80)
    keeper_name: str = Field(alias="keeperName", min_length=1, max_length=40)


class JoinRoomRequest(CamelModel):
    invite_code: str = Field(alias="inviteCode", min_length=4, max_length=16)
    display_name: str = Field(alias="displayName", min_length=1, max_length=40)


class SendMessageRequest(CamelModel):
    sender_id: str = Field(alias="senderId", min_length=1)
    content: str = Field(min_length=1, max_length=2000)
