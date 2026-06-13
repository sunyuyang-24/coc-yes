from __future__ import annotations

import re
import secrets


_EXPRESSION_RE = re.compile(r"^\s*(?P<count>\d*)d(?P<sides>\d+)\s*(?P<modifier>[+-]\s*\d+)?\s*$", re.I)
_RNG = secrets.SystemRandom()


def roll_dice(expression: str, target_value: int | None = None, bonus_penalty: int = 0, label: str | None = None, hidden: bool = False) -> dict:
    count, sides, modifier = _parse_expression(expression)
    normalized = f"{count}d{sides}{_format_modifier(modifier)}"

    if count == 1 and sides == 100:
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

    # Compute effective d100 result for each tens die
    # 00 + 0 = 100, 00 + 1 = 1, 10 + 0 = 10, etc.
    def _effective(tens: int) -> int:
        return 100 if tens == 0 and ones == 0 else tens * 10 + ones

    scores = [_effective(t) for t in tens_rolls]

    if bonus_penalty > 0:
        best_idx = scores.index(min(scores))
        chosen_tens = tens_rolls[best_idx]
        total = scores[best_idx]
    elif bonus_penalty < 0:
        worst_idx = scores.index(max(scores))
        chosen_tens = tens_rolls[worst_idx]
        total = scores[worst_idx]
    else:
        chosen_tens = tens_rolls[0]
        total = _effective(chosen_tens)

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


def _classify_coc_success(total: int, target_value: int) -> dict:
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

def opposed_check(actor_total: int, actor_target: int, opponent_total: int, opponent_target: int,
                  defender_wins_tie: bool = False) -> dict:
    """COC 7e 对抗检定 (CRB p90-92)。

    双方各投 1d100，比较成功等级。成功等级高者胜。
    同等级：技能值高者胜（CRB p90）。若技能相同则平局。

    战斗特例（CRB p108）：
    - 闪避：平局时防守方胜（defender_wins_tie=True）
    - 反击：平局时攻击方胜（defender_wins_tie=False）
    """
    a_order = _get_success_level_order(actor_total, actor_target)
    o_order = _get_success_level_order(opponent_total, opponent_target)

    def _winner_by_skill():
        if actor_target > opponent_target:
            return "actor"
        elif opponent_target > actor_target:
            return "opponent"
        return "tie"

    if a_order > o_order:
        return {"winner": "actor", "actorLevel": a_order, "opponentLevel": o_order, "reason": "成功等级更高"}
    elif o_order > a_order:
        return {"winner": "opponent", "actorLevel": a_order, "opponentLevel": o_order, "reason": "成功等级更高"}

    # Same success level: higher skill wins (CRB p90), or tie rule for combat
    if defender_wins_tie:
        winner = "opponent"  # dodger/defender wins ties (CRB p108 dodge)
    else:
        # Attacker wins ties for fight-back (CRB p108)
        by_skill = _winner_by_skill()
        winner = "actor" if by_skill == "tie" else by_skill

    # Build reason
    if winner == "actor":
        reason = f"同等级，攻击方胜（技能值{actor_target} vs {opponent_target}）"
    else:
        reason = f"同等级，防守方胜（技能值{opponent_target} vs {actor_target}）"

    return {"winner": winner, "actorLevel": a_order, "opponentLevel": o_order, "reason": reason}


def pushing_check(total: int, target: int, is_pushed: bool = False) -> dict:
    """COC 7e 推动检定 (CRB p79)：
    失败后可选择推动，再次投掷。但如果推动后仍然失败，后果更严重。
    返回推动是否允许及建议文本。
    """
    result = _classify_coc_success(total, target)
    if result["level"] == "fumble":
        return {"canPush": False, "message": "大失败无法推动检定（CRB p84）"}
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
    is_major = damage * 2 >= hp_max
    return {
        "isMajorWound": is_major,
        "threshold": hp_max // 2,
        "message": f"重伤！单次伤害 {damage} >= 重伤阈值 {hp_max // 2}" if is_major else "未达到重伤阈值",
    }


def insanity_check(san_loss: int, current_san: int, max_san: int = 99, cumulative_daily_loss: int = 0, int_value: int = 50, pre_loss_san: int | None = None) -> dict:
    """COC 7e 疯狂判定 (CRB p156-164).

    - SAN=0: 永久疯狂，调查员退场
    - 单次损失>=5且SAN>0: 需投INT检定，成功则临时疯狂
    - 单日累计损失 >= 当前SAN的1/5: 不定期疯狂
    """
    result = {
        "sanLoss": san_loss,
        "currentSAN": current_san,
        "maxSAN": max_san,
        "temporaryInsanity": False,
        "indefiniteInsanity": False,
        "permanentInsanity": False,
        "needsIntRoll": False,
        "message": "",
    }

    # Permanent: SAN reaches 0 (CRB p156)
    if current_san <= 0:
        result["permanentInsanity"] = True
        result["message"] = "永久疯狂！SAN 归零，调查员退场（CRB p156）"
        return result

    # Temporary: >= 5 SAN loss in one event triggers INT check (CRB p155)
    if san_loss >= 5:
        result["needsIntRoll"] = True
        result["message"] = f"SAN 损失 {san_loss} >= 5，需 INT 检定（CRB p155）"

    # Indefinite: cumulative daily loss >= 1/5 of pre-loss SAN (CRB p156)
    threshold_san = pre_loss_san if pre_loss_san is not None else current_san
    daily_threshold = max(threshold_san // 5, 1)
    if cumulative_daily_loss + san_loss >= daily_threshold:
        result["indefiniteInsanity"] = True
        if result["message"]:
            result["message"] += f"；单日累计损失已达阈值 {daily_threshold}"
        else:
            result["message"] = f"不定期疯狂！单日累计 SAN 损失 >= {daily_threshold}（CRB p156）"

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
