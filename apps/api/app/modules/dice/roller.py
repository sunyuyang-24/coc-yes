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

    if total == 0:
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

    fumble_threshold = 100 if target_value >= 50 else 96

    if total == 1:
        return {"level": "critical", "label": "大成功", "isSuccess": True}

    if total >= fumble_threshold:
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
