from fastapi import APIRouter

router = APIRouter()


@router.get("/bootstrap")
async def bootstrap() -> dict[str, object]:
    return {
        "project": "COC Yes",
        "stage": "engineering-foundation",
        "modules": [
            {
                "key": "rooms",
                "label": "房间与成员",
                "status": "active",
            },
            {
                "key": "chat",
                "label": "文字聊天",
                "status": "active",
            },
            {
                "key": "dice",
                "label": "可信骰子",
                "status": "active",
            },
            {
                "key": "characters",
                "label": "角色卡解析",
                "status": "planned",
            },
            {
                "key": "rules",
                "label": "规则书检索",
                "status": "planned",
            },
        ],
    }
