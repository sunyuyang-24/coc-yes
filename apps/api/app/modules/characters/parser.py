from __future__ import annotations

from app.modules.characters.xlsx_reader import XlsxReader


ATTRIBUTE_LABELS = {
    "STR": "力量",
    "DEX": "敏捷",
    "POW": "意志",
    "CON": "体质",
    "APP": "外貌",
    "EDU": "教育",
    "SIZ": "体型",
    "INT": "智力",
    "Luck": "幸运",
}

ATTRIBUTE_FALLBACK_REFS = {
    "STR": "U3",
    "DEX": "AA3",
    "POW": "AG3",
    "CON": "U5",
    "APP": "AA5",
    "EDU": "AG5",
    "SIZ": "U7",
    "INT": "AA7",
    "Luck": "AG7",
}

BASIC_REFS = {
    "name": "E3",
    "player": "E4",
    "era": "M4",
    "occupation": "E5",
    "occupationNo": "M5",
    "age": "E6",
    "gender": "M6",
    "residence": "E7",
    "hometown": "M7",
    "currentTime": "E8",
}

STATUS_REFS = {
    "hp": "E10",
    "san": "N10",
    "mp": "W10",
    "mov": "AF10",
    "armor": "AN10",
    "damageBonus": "AP52",
    "build": "AP55",
}

BACKGROUND_REFS = {
    "appearance": "AA61",
    "ideology": "AA63",
    "significantPeople": "AA65",
    "meaningfulLocations": "AA67",
    "treasuredPossessions": "AA69",
    "traits": "AA71",
    "injuries": "AA75",
    "phobiasManias": "AA77",
}


def parse_character_card(content: bytes, filename: str) -> dict:
    workbook = XlsxReader(content)

    if "人物卡" not in workbook.sheets:
        raise ValueError("Workbook does not contain a 人物卡 sheet")

    cells = workbook.cells("人物卡")

    return {
        "sourceFileName": filename,
        "basic": _parse_basic(cells),
        "attributes": _parse_attributes(cells, workbook.defined_names),
        "status": _parse_status(cells),
        "skills": _parse_skills(cells),
        "weapons": _parse_weapons(cells),
        "background": _parse_background(cells),
        "experiences": _parse_experiences(cells),
        "spells": _parse_spells(cells),
        "warnings": _parse_warnings(cells),
    }


def _parse_basic(cells: dict[str, str]) -> dict:
    return {key: _clean(cells.get(ref)) for key, ref in BASIC_REFS.items()}


def _parse_attributes(cells: dict[str, str], defined_names: dict[str, str]) -> list[dict]:
    attributes: list[dict] = []

    for key, label in ATTRIBUTE_LABELS.items():
        ref = defined_names.get(key, ATTRIBUTE_FALLBACK_REFS[key])
        value = _number(cells.get(ref))

        attributes.append(
            {
                "key": "LUCK" if key == "Luck" else key,
                "label": label,
                "value": value,
                "half": value // 2 if value is not None else None,
                "fifth": value // 5 if value is not None else None,
            }
        )

    return attributes


def _parse_status(cells: dict[str, str]) -> dict:
    return {key: _number(cells.get(ref)) for key, ref in STATUS_REFS.items()}


def _parse_skills(cells: dict[str, str]) -> list[dict]:
    skills: list[dict] = []

    for row in range(16, 50):
        _append_skill(skills, cells, f"F{row}", f"R{row}")
        _append_skill(skills, cells, f"AB{row}", f"AN{row}")

    return skills


def _append_skill(skills: list[dict], cells: dict[str, str], name_ref: str, value_ref: str) -> None:
    name = _clean(cells.get(name_ref))

    if not name or name.startswith("#"):
        return

    value = _number(cells.get(value_ref))

    skills.append(
        {
            "name": name,
            "value": value,
            "half": value // 2 if value is not None else None,
            "fifth": value // 5 if value is not None else None,
        }
    )


def _parse_weapons(cells: dict[str, str]) -> list[dict]:
    weapons: list[dict] = []

    for row in range(53, 59):
        name = _clean(cells.get(f"B{row}"))

        if not name or name == "无":
            continue

        weapons.append(
            {
                "name": name,
                "type": _clean(cells.get(f"G{row}")),
                "skill": _clean(cells.get(f"M{row}")),
                "value": _number(cells.get(f"Q{row}")),
                "damage": _clean(cells.get(f"W{row}")),
                "range": _clean(cells.get(f"AA{row}")),
                "attacks": _clean(cells.get(f"AE{row}")),
                "ammo": _clean(cells.get(f"AG{row}")),
                "malfunction": _clean(cells.get(f"AJ{row}")),
            }
        )

    return weapons


def _parse_background(cells: dict[str, str]) -> dict:
    return {key: _clean(cells.get(ref)) for key, ref in BACKGROUND_REFS.items()}


def _parse_experiences(cells: dict[str, str]) -> list[dict]:
    experiences: list[dict] = []

    for row in range(97, 112):
        module = _clean(cells.get(f"B{row}"))
        change = _clean(cells.get(f"J{row}"))
        note = _clean(cells.get(f"AK{row}"))

        if module or change or note:
            experiences.append({"module": module, "change": change, "note": note})

    return experiences


def _parse_spells(cells: dict[str, str]) -> list[dict]:
    spells: list[dict] = []

    for row in range(114, 117):
        name = _clean(cells.get(f"Y{row}"))

        if not name or name.startswith("例："):
            continue

        spells.append(
            {
                "name": name,
                "cost": _clean(cells.get(f"AC{row}")),
                "effect": _clean(cells.get(f"AH{row}")),
            }
        )

    return spells


def _parse_warnings(cells: dict[str, str]) -> list[str]:
    warnings: list[str] = []
    missing_attributes = [
        "LUCK" if key == "Luck" else key
        for key, ref in ATTRIBUTE_FALLBACK_REFS.items()
        if _number(cells.get(ref)) is None
    ]

    if not _clean(cells.get("E3")):
        warnings.append("未读取到调查员姓名，可能是空白模板或非当前模板。")

    if len(missing_attributes) == len(ATTRIBUTE_FALLBACK_REFS):
        warnings.append("未读取到主要属性数值，上传文件可能仍为空白卡。")
    elif missing_attributes:
        warnings.append(f"缺少属性数值：{', '.join(missing_attributes)}。")

    return warnings


def _clean(value: str | None) -> str:
    if value is None:
        return ""

    return " ".join(value.replace("\n", " ").split()).strip()


def _number(value: str | None) -> int | None:
    cleaned = _clean(value)

    if not cleaned or cleaned.startswith("#"):
        return None

    try:
        return int(float(cleaned))
    except ValueError:
        return None
