"""Shared COC 7e constants used across character parsers and room modules."""

ATTRIBUTE_LABELS: dict[str, str] = {
    "STR": "力量",
    "DEX": "敏捷",
    "POW": "意志",
    "CON": "体质",
    "APP": "外貌",
    "EDU": "教育",
    "SIZ": "体型",
    "INT": "智力",
    "LUCK": "幸运",
}

CN_ATTR_MAP: dict[str, str] = {v: k for k, v in ATTRIBUTE_LABELS.items()}

# COC 7e Damage Bonus / Build table (Str+Siz → (formula, build))
_DB_TABLE: list[tuple[int, str, int]] = [
    (64, "-2", -2),
    (84, "-1", -1),
    (124, "0", 0),
    (164, "+1D4", 1),
    (204, "+1D6", 2),
    (284, "+2D6", 3),
    (364, "+3D6", 4),
]


def compute_db_build(str_val: int, siz_val: int) -> tuple[str, int]:
    total = str_val + siz_val
    for threshold, formula, build in _DB_TABLE:
        if total <= threshold:
            return formula, build
    return "+4D6", 5
