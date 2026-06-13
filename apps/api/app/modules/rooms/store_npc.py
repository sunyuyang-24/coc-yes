"""NPC character creation for RoomStore (mixin)."""

from __future__ import annotations


class NpcMixin:
    """NPC creation methods mixed into RoomStore. Expects self to provide:
    _lock, _save(), _require_room(), _find_member(), _add_system_message(),
    add_character(), _now().
    """

    def create_npc(self, room_id: str, keeper_id: str, name: str) -> dict:
        label_map = {
            "STR": "力量", "DEX": "敏捷", "POW": "意志",
            "CON": "体质", "APP": "外貌", "EDU": "教育",
            "SIZ": "体型", "INT": "智力", "LUCK": "幸运",
        }
        character = {
            "basic": {"name": f"{name} (NPC)", "occupation": "NPC"},
            "attributes": [
                {"key": k, "label": v, "value": 50, "half": 25, "fifth": 10}
                for k, v in label_map.items()
            ],
            "status": {"hp": 10, "san": 50, "mp": 10, "luck": 50, "mov": 7, "armor": 0},
            "initialStatus": {"hp": 10, "san": 50, "mp": 10, "luck": 50, "mov": 7, "armor": 0},
            "skills": [
                {"name": "闪避", "value": 25, "half": 12, "fifth": 5},
            ],
            "weapons": [{"name": "拳头", "damage": "1d3", "skill": "拳头/摔跌"}],
            "background": {}, "experiences": [], "spells": [],
            "warnings": [], "sourceFileName": "npc",
            "isNpc": True,
        }
        return self.add_character(room_id, keeper_id, character, replace_existing=False)

    def create_npc_from_text(self, room_id: str, keeper_id: str, npc_text: str) -> dict:
        import re

        label_map = {
            "STR": "力量", "DEX": "敏捷", "POW": "意志",
            "CON": "体质", "APP": "外貌", "EDU": "教育",
            "SIZ": "体型", "INT": "智力", "LUCK": "幸运",
        }

        attrs: dict[str, int] = {k: 50 for k in label_map}
        name = "NPC"
        occupation = "NPC"
        skills: list[dict] = []
        weapons: list[dict] = []
        background_parts: list[str] = []
        hp_override: int | None = None
        san_override: int | None = None
        mp_override: int | None = None
        mov_override: int | None = None
        armor_override: int = 0
        db_override: str | None = None
        build_override: int | None = None

        text = npc_text.strip()

        # Name extraction
        name_prefixes = ["名称:", "姓名:", "名字:", "name:", "npc名:", "npc名称:"]
        for prefix in name_prefixes:
            if text.lower().startswith(prefix.lower()):
                rest = text[len(prefix):].lstrip()
                m = re.match(r'([^\n，,。.]+)', rest)
                if m:
                    name = m.group(1).strip()
                    text = rest[m.end():].strip()
                break
        else:
            first_line = text.split("\n")[0].strip()
            cn_attr_kw = ["力量", "体质", "体型", "敏捷", "智力", "外貌", "意志", "教育", "幸运", "理智", "生命"]
            has_cn_attr = any(kw in first_line for kw in cn_attr_kw)
            has_en_attr = bool(re.search(r'\b(STR|CON|DEX|APP|POW|SIZ|INT|EDU|LUCK)\s*\d+', first_line, re.IGNORECASE))
            if not has_cn_attr and not has_en_attr:
                name_match = re.match(r'^(.+?)(?:\s+\d+岁|\s*[，,]\s*\S+)?$', first_line)
                if name_match:
                    name = name_match.group(1).strip()
                    text = text[len(first_line):].strip()
                    age_m = re.search(r'(\d+)\s*岁', first_line)
                    occ_m = re.search(r'[，,]\s*(.+?)$', first_line)
                    if age_m:
                        background_parts.append(f"年龄: {age_m.group(1)}")
                    if occ_m:
                        occupation = occ_m.group(1).strip()

        # Section splitting
        section_markers = [
            (r'技能[：:]', 'skills'),
            (r'武器[：:]', 'weapons'),
            (r'背景[：:]', 'background'),
            (r'装备[：:]', 'weapons'),
            (r'描述[：:]', 'background'),
        ]

        sections: list[tuple[str, str]] = []
        current_type = "attrs"
        current_content: list[str] = []

        for line in text.split("\n"):
            line_stripped = line.strip()
            if not line_stripped:
                continue
            matched = False
            for pattern, stype in section_markers:
                m = re.match(pattern, line_stripped, re.IGNORECASE)
                if m:
                    if current_content:
                        sections.append((current_type, "\n".join(current_content)))
                    current_type = stype
                    current_content = [line_stripped[m.end():].strip()] if line_stripped[m.end():].strip() else []
                    matched = True
                    break
            if not matched:
                current_content.append(line_stripped)
        if current_content:
            sections.append((current_type, "\n".join(current_content)))

        for stype, content in sections:
            if stype == "attrs":
                attr_pattern_en = re.compile(r'\b(STR|CON|DEX|APP|POW|SIZ|INT|EDU|LUCK)\s*[：:=\s]*\s*(\d{1,3})\b', re.IGNORECASE)
                for m in attr_pattern_en.finditer(content):
                    key = m.group(1).upper()
                    val = int(m.group(2))
                    if 1 <= val <= 999:
                        attrs[key] = val

                cn_attr_map = {
                    "力量": "STR", "体质": "CON", "体型": "SIZ", "敏捷": "DEX",
                    "智力": "INT", "外貌": "APP", "意志": "POW", "教育": "EDU",
                    "幸运": "LUCK", "灵感": "INT",
                }
                for cn_name, en_key in cn_attr_map.items():
                    for m in re.finditer(re.escape(cn_name) + r'\s*[：:=\s]*\s*(\d{1,3})', content):
                        val = int(m.group(1))
                        if 1 <= val <= 999:
                            attrs[en_key] = val

                for m in re.finditer(r'\b(?:HP|生命值?)\s*[：:=\s]*\s*(\d{1,4})\b', content, re.IGNORECASE):
                    hp_override = int(m.group(1))
                for m in re.finditer(r'\b(?:SAN|理智值?|理智)\s*[：:=\s]*\s*(\d{1,4})\b', content, re.IGNORECASE):
                    san_override = int(m.group(1))
                for m in re.finditer(r'\b(?:MP|魔法值?)\s*[：:=\s]*\s*(\d{1,4})\b', content, re.IGNORECASE):
                    mp_override = int(m.group(1))
                for m in re.finditer(r'\b(?:MOV|移动速度?|移动)\s*[：:=\s]*\s*(\d{1,2})\b', content, re.IGNORECASE):
                    mov_override = int(m.group(1))
                for m in re.finditer(r'(?:护甲|装甲|ARMOR?)\s*[：:=\s]*\s*(\d{1,2})\b', content, re.IGNORECASE):
                    armor_override = int(m.group(1))
                for m in re.finditer(r'\b(DB|伤害加值)\s*[：:=\s]*\s*([+-]?\d{1,2}[dD]\d{1,2}|[+-]?\d+)\b', content, re.IGNORECASE):
                    db_override = m.group(2)
                for m in re.finditer(r'\bBUILD\s*[：:=\s]*\s*(\d{1,2})\b', content, re.IGNORECASE):
                    build_override = int(m.group(1))

                age_m = re.search(r'(?:年龄|岁数)?\s*[：:=\s]*\s*(\d{1,3})\s*岁', content)
                if age_m:
                    background_parts.append(f"年龄: {age_m.group(1)}")

                occ_m = re.search(r'(?:职业|OCCUPATION)\s*[：:=\s]*\s*(.+?)$', content, re.IGNORECASE | re.MULTILINE)
                if occ_m:
                    occupation = occ_m.group(1).strip()

            elif stype == "skills":
                skill_parts = re.split(r'[,，;；\n]', content)
                for part in skill_parts:
                    part = part.strip()
                    if not part:
                        continue
                    sm = re.match(r'(.+?)\s+(\d{1,3})\s*$', part)
                    if sm:
                        sname = sm.group(1).strip()
                        sval = int(sm.group(2))
                        if 0 <= sval <= 999:
                            skills.append({
                                "name": sname, "value": sval,
                                "half": sval // 2, "fifth": sval // 5,
                            })

            elif stype == "weapons":
                wp_lines = re.split(r'[\n;；]', content)
                for wp_line in wp_lines:
                    wp_line = wp_line.strip()
                    if not wp_line:
                        continue
                    wm = re.match(r'(.+?)\s+((?:\d+[dD]\d+(?:[+-]\d+)?)|(?:\d+))\s*$', wp_line)
                    if wm:
                        wname = wm.group(1).strip()
                        wdamage = wm.group(2).strip()
                        wskill = "格斗(斗殴)"
                        wname_lower = wname.lower()
                        if any(kw in wname_lower for kw in ["拳", "爪", "牙", "咬"]):
                            wskill = "格斗(斗殴)"
                        elif any(kw in wname_lower for kw in ["刀", "剑", "匕首", "矛", "枪", "棍", "斧", "锤"]):
                            wskill = wname if wname else "格斗(斗殴)"
                        elif any(kw in wname_lower for kw in ["弓", "弩", "箭"]):
                            wskill = "射击"
                        elif any(kw in wname_lower for kw in ["手枪", "步枪", "霰弹", "冲锋枪"]):
                            wskill = "射击"
                        weapons.append({
                            "name": wname, "damage": wdamage,
                            "skill": wskill if wskill else "格斗(斗殴)",
                        })
                    else:
                        weapons.append({
                            "name": wp_line, "damage": "1d3",
                            "skill": "格斗(斗殴)",
                        })

            elif stype == "background":
                background_parts.append(content)

        background_dict: dict[str, str] = {}
        if background_parts:
            bg_text = "\n".join(background_parts)
            for line in bg_text.split("\n"):
                if "：" in line or ":" in line:
                    parts = re.split(r'[：:]', line, maxsplit=1)
                    if len(parts) == 2:
                        background_dict[parts[0].strip()] = parts[1].strip()
                else:
                    background_dict.setdefault("描述", "")
                    background_dict["描述"] += line + "\n"
            background_dict = {k: v.strip() for k, v in background_dict.items() if v.strip()}

        if not skills:
            skills.append({"name": "闪避", "value": attrs["DEX"] // 2, "half": attrs["DEX"] // 4, "fifth": attrs["DEX"] // 10})

        if not weapons:
            weapons.append({"name": "拳头", "damage": "1d3", "skill": "拳头/摔跌"})

        con, siz = attrs["CON"], attrs["SIZ"]
        pow_val, dex = attrs["POW"], attrs["DEX"]
        hp_val = hp_override if hp_override is not None else max(1, (con + siz) // 10)
        san_val = san_override if san_override is not None else pow_val
        mp_val = mp_override if mp_override is not None else max(1, pow_val // 5)
        mov_val = mov_override if mov_override is not None else 7
        if dex < siz and mov_override is None:
            mov_val = 7
        elif dex > siz and mov_override is None:
            mov_val = 8

        attributes_list = [
            {"key": k, "label": v, "value": attrs[k], "half": attrs[k] // 2, "fifth": attrs[k] // 5}
            for k, v in label_map.items()
        ]

        character = {
            "basic": {"name": f"{name} (NPC)", "occupation": occupation},
            "attributes": attributes_list,
            "status": {"hp": hp_val, "san": san_val, "mp": mp_val,
                        "luck": attrs.get("LUCK", pow_val * 5),
                        "mov": mov_val, "armor": armor_override},
            "initialStatus": {"hp": hp_val, "san": san_val, "mp": mp_val,
                               "luck": attrs.get("LUCK", pow_val * 5),
                               "mov": mov_val, "armor": armor_override},
            "skills": skills,
            "weapons": weapons,
            "background": background_dict,
            "experiences": [],
            "spells": [],
            "warnings": [],
            "sourceFileName": f"npc-{name}",
            "isNpc": True,
        }

        return self.add_character(room_id, keeper_id, character, replace_existing=False)
