from __future__ import annotations

import re
import secrets


_EXPRESSION_RE = re.compile(r"^\s*(?P<count>\d*)d(?P<sides>\d+)\s*(?P<modifier>[+-]\s*\d+)?\s*$", re.I)
_RNG = secrets.SystemRandom()


def roll_dice(expression: str, target_value: int | None = None, bonus_penalty: int = 0, label: str | None = None, hidden: bool = False) -> dict:
    count, sides, modifier = _parse_expression(expression)
    normalized = f"{count}d{sides}{_format_modifier(modifier)}"

    if count == 1 and sides == 100 and bonus_penalty != 0:
        total, breakdown = _roll_coc_d100(bonus_penalty)
    else:
        rolls = [_RNG.randint(1, sides) for _ in range(count)]
        total = sum(rolls) + modifier
        breakdown = [
            {
                "kind": "standard",
                "count": count,
                "sides": sides,
                "rolls": rolls,
                "modifier": modifier,
            }
        ]

    success = _classify_coc_success(total, target_value) if target_value is not None and sides == 100 else None

    return {
        "expression": normalized,
        "label": label.strip() if label else None,
        "total": total,
        "breakdown": breakdown,
        "targetValue": target_value,
        "bonusPenalty": bonus_penalty,
        "successLevel": success["level"] if success else None,
        "successLabel": success["label"] if success else None,
        
        "hidden": hidden,
    }


def _parse_expression(expression: str) -> tuple[int, int, int]:
    match = _EXPRESSION_RE.match(expression)

    if not match:
        raise ValueError("Dice expression must look like 1d100 or 2d6+3")

    count = int(match.group("count") or "1")
    sides = int(match.group("sides"))
    modifier = int((match.group("modifier") or "0").replace(" ", ""))

    if count < 1 or count > 100:
        raise ValueError("Dice count must be between 1 and 100")

    if sides < 2 or sides > 1000:
        raise ValueError("Dice sides must be between 2 and 1000")

    return count, sides, modifier


def _roll_coc_d100(bonus_penalty: int) -> tuple[int, list[dict]]:
    tens_count = abs(bonus_penalty) + 1
    tens_rolls = [_RNG.randint(0, 9) for _ in range(tens_count)]
    ones = _RNG.randint(0, 9)

    if bonus_penalty > 0:
        chosen_tens = min(tens_rolls)
    elif bonus_penalty < 0:
        chosen_tens = max(tens_rolls)
    else:
        chosen_tens = tens_rolls[0]

    total = chosen_tens * 10 + ones

    # Clamp 0 to 100 for d100 (00 = 100), but only for non-bonus contexts
    # bonus dice with all-zero tens + ones=0 should yield 0 (critical), not 100
    if total == 0 and bonus_penalty <= 0:
        total = 100

    return total, [
        {
            "kind": "coc_d100",
            "count": 1,
            "sides": 100,
            "rolls": [total],
            "modifier": 0,
            "tensRolls": tens_rolls,
            "ones": ones,
            "chosenTens": chosen_tens,
        }
    ]


def _classify_coc_success(total: int, target_value: int | None) -> dict:
    if target_value is None:
        return {
            "level": None,
            "label": None,
            "isSuccess": None,
        }

    if total == 1:
        return {"level": "critical", "label": "大成功", "isSuccess": True}

    # COC 7e CRB p90: skill<50 fumble 96-100, skill>=50 fumble 100 only
    if total == 100 or (target_value < 50 and total >= 96):
        return {"level": "fumble", "label": "大失败", "isSuccess": False}

    if total <= target_value // 5:
        return {"level": "extreme", "label": "极难成功", "isSuccess": True}

    if total <= target_value // 2:
        return {"level": "hard", "label": "困难成功", "isSuccess": True}

    if total <= target_value:
        return {"level": "regular", "label": "普通成功", "isSuccess": True}

    return {"level": "failure", "label": "失败", "isSuccess": False}


def _format_modifier(modifier: int) -> str:
    if modifier == 0:
        return ""

    if modifier > 0:
        return f"+{modifier}"

    return str(modifier)


# ---------------------------------------------------------------------------
# COC 7e Advanced Rules
# ---------------------------------------------------------------------------

def opposed_check(actor_total: int, actor_target: int, opponent_total: int, opponent_target: int) -> dict:
    """COC 7e 对抗检定 (CRB p90-92)：
    双方各投 1d100，比较成功等级。成功等级高者胜。
    同等级则比较出目（越接近目标值越好）。
    """
    a_level = _get_success_level_order(actor_total, actor_target)
    o_level = _get_success_level_order(opponent_total, opponent_target)

    if a_level > o_level:
        return {"winner": "actor", "actorLevel": a_level, "opponentLevel": o_level, "reason": "成功等级更高"}
    elif o_level > a_level:
        return {"winner": "opponent", "actorLevel": a_level, "opponentLevel": o_level, "reason": "成功等级更高"}
    # 同等级比较出目质量
    a_quality = actor_total / max(actor_target, 1)
    o_quality = opponent_total / max(opponent_target, 1)
    if a_quality < o_quality:
        return {"winner": "actor", "actorLevel": a_level, "opponentLevel": o_level, "reason": "同等级出目更优"}
    elif o_quality < a_quality:
        return {"winner": "opponent", "actorLevel": a_level, "opponentLevel": o_level, "reason": "同等级出目更优"}
    return {"winner": "tie", "actorLevel": a_level, "opponentLevel": o_level, "reason": "完全相同"}


def pushing_check(total: int, target: int, is_pushed: bool = False) -> dict:
    """COC 7e 推动检定 (CRB p79)：
    失败后可选择推动，再次投掷。但如果推动后仍然失败，后果更严重。
    返回推动是否允许及建议文本。
    """
    result = _classify_coc_success(total, target)
    if result["isSuccess"]:
        return {"canPush": False, "message": "检定已成功，无需推动"}
    if is_pushed and not result["isSuccess"]:
        return {"canPush": False, "message": "推动检定失败，后果加重（KP 决定具体后果）"}
    return {"canPush": True, "message": "可推动检定：再次投掷，但失败后果更严重（CRB p79）"}


def first_aid_check(hp_current: int, hp_max: int) -> dict:
    """COC 7e 急救 (CRB p66)：
    成功恢复 1 HP。
    """
    return {
        "healAmount": 1,
        "hpAfter": min(hp_current + 1, hp_max),
        "message": f"急救成功，恢复 1 HP（{hp_current} → {min(hp_current + 1, hp_max)}）",
    }


def medicine_check(hp_current: int, hp_max: int) -> dict:
    """COC 7e 医学治疗 (CRB p66)：
    成功给恢复奖励骰，恢复 1d3 HP。
    """
    import secrets
    heal = secrets.SystemRandom().randint(1, 3)
    return {
        "healAmount": heal,
        "hpAfter": min(hp_current + heal, hp_max),
        "message": f"医学治疗成功，恢复 {heal} HP（{hp_current} → {min(hp_current + heal, hp_max)}）",
    }


def major_wound_check(damage: int, hp_max: int) -> dict:
    """COC 7e 重伤判定 (CRB p124)：
    单次伤害 >= HP 最大值的一半即为重伤。
    """
    is_major = damage >= (hp_max // 2)
    return {
        "isMajorWound": is_major,
        "threshold": hp_max // 2,
        "message": f"重伤！单次伤害 {damage} >= 重伤阈值 {hp_max // 2}" if is_major else "未达到重伤阈值",
    }


def insanity_check(san_loss: int, current_san: int, max_san: int) -> dict:
    """COC 7e 疯狂判定 (CRB p156-164)：
    - 单次 SAN 损失 >= 5 → 临时疯狂
    - SAN 归零 → 不定疯狂
    """
    result = {
        "sanLoss": san_loss,
        "currentSAN": current_san,
        "maxSAN": max_san,
        "temporaryInsanity": False,
        "indefiniteInsanity": False,
        "message": "",
    }
    if san_loss >= 5 and current_san > 0:
        result["temporaryInsanity"] = True
        result["message"] = f"临时疯狂！单次 SAN 损失 {san_loss} >= 5（CRB p156）"
    if current_san <= 0:
        result["indefiniteInsanity"] = True
        result["message"] = f"不定疯狂！SAN 已归零（CRB p164）"
    return result


def weapon_malfunction_check(total: int, malf_value: int = 96) -> dict:
    """COC 7e 武器卡壳判定 (CRB p92-93)：
    投出 malf 值（默认 96+）则武器卡壳。
    """
    is_malf = total >= malf_value
    return {
        "isMalfunction": is_malf,
        "malfValue": malf_value,
        "message": f"武器卡壳！出目 {total} >= {malf_value}" if is_malf else "武器正常",
    }


def _get_success_level_order(total: int, target: int) -> int:
    """返回成功等级排序值：5=大成功, 4=极难, 3=困难, 2=普通, 1=失败, 0=大失败"""
    result = _classify_coc_success(total, target)
    order = {"critical": 5, "extreme": 4, "hard": 3, "regular": 2, "failure": 1, "fumble": 0}
    return order.get(result["level"], 1)
