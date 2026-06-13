from __future__ import annotations

from io import BytesIO
import re
from zipfile import ZipFile
import xml.etree.ElementTree as ET


NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


class XlsxReader:
    def __init__(self, content: bytes) -> None:
        self._bytes = BytesIO(content)
        self.archive = ZipFile(self._bytes)
        self.shared_strings = self._read_shared_strings()
        self.sheets = self._read_sheets()
        self.defined_names = self._read_defined_names()

    def close(self) -> None:
        """Explicitly close the underlying ZipFile to release OS resources."""
        self.archive.close()
        self._bytes.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def cells(self, sheet_name: str) -> dict[str, str]:
        path = self.sheets[sheet_name]
        root = ET.fromstring(self.archive.read(path))
        result: dict[str, str] = {}

        for cell in root.findall(".//m:c", NS):
            ref = cell.attrib.get("r")

            if not ref:
                continue

            value = self._cell_value(cell)

            if value != "":
                result[ref] = value

        return result

    def _cell_value(self, cell: ET.Element) -> str:
        cell_type = cell.attrib.get("t")
        value_node = cell.find("m:v", NS)

        if cell_type == "s" and value_node is not None and value_node.text is not None:
            index = int(value_node.text)
            return self.shared_strings[index] if index < len(self.shared_strings) else value_node.text

        if cell_type == "inlineStr":
            return "".join(text.text or "" for text in cell.findall(".//m:t", NS)).strip()

        if value_node is not None and value_node.text is not None:
            return value_node.text.strip()

        return ""

    def _read_shared_strings(self) -> list[str]:
        try:
            root = ET.fromstring(self.archive.read("xl/sharedStrings.xml"))
        except KeyError:
            return []

        strings: list[str] = []

        for item in root.findall("m:si", NS):
            strings.append("".join(text.text or "" for text in item.findall(".//m:t", NS)).strip())

        return strings

    def _read_sheets(self) -> dict[str, str]:
        try:
            workbook = ET.fromstring(self.archive.read("xl/workbook.xml"))
            rels = ET.fromstring(self.archive.read("xl/_rels/workbook.xml.rels"))
        except KeyError as error:
            raise ValueError("Not a valid .xlsx file") from error
        rel_targets = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
        sheets: dict[str, str] = {}

        for sheet in workbook.findall(".//m:sheet", NS):
            rel_id = sheet.attrib.get(f"{{{NS['r']}}}id")
            target = rel_targets.get(rel_id or "")

            if not target:
                continue

            sheets[sheet.attrib["name"]] = "xl/" + target.lstrip("/")

        return sheets

    def _read_defined_names(self) -> dict[str, str]:
        workbook = ET.fromstring(self.archive.read("xl/workbook.xml"))
        names: dict[str, str] = {}

        for defined in workbook.findall(".//m:definedName", NS):
            name = defined.attrib.get("name")

            if not name or not defined.text:
                continue

            match = re.search(r"!\$?([A-Z]+)\$?(\d+)", defined.text)

            if match:
                names[name] = f"{match.group(1)}{match.group(2)}"

        return names
