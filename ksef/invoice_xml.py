from __future__ import annotations

from pathlib import Path

from defusedxml import ElementTree as ET

KSEF_FA3_NAMESPACE = "http://crd.gov.pl/wzor/2025/06/25/13775/"

KSEF_SCHEMAS = {
    "invoice": {
        "logical_name": "FA(3)",
        "namespace": KSEF_FA3_NAMESPACE,
        "published_date": "2025-06-25",
    }
}


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _namespace(tag: str) -> str:
    return tag.split("}", 1)[0][1:] if tag.startswith("{") else ""


def _has_descendant(root: ET.Element, name: str) -> bool:
    return any(_local_name(element.tag) == name for element in root.iter())


def classify_ksef_invoice_xml(path: str | Path) -> dict:
    path = Path(path)

    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        return {"ok": False, "reason": f"XML parse error: {exc}", "schema": None}

    if _local_name(root.tag) != "Faktura":
        return {"ok": False, "reason": "root element is not Faktura", "schema": None}

    namespace = _namespace(root.tag)
    schema = None
    if namespace == KSEF_FA3_NAMESPACE:
        schema = KSEF_SCHEMAS["invoice"]

    required = ("Fa", "Podmiot1", "Podmiot2", "FaWiersz")
    missing = [name for name in required if not _has_descendant(root, name)]
    if missing:
        return {
            "ok": False,
            "reason": f"missing KSeF invoice elements: {', '.join(missing)}",
            "schema": schema,
        }

    return {
        "ok": True,
        "reason": "KSeF invoice XML",
        "schema": schema
        or {
            "logical_name": "unknown",
            "namespace": namespace,
            "published_date": None,
        },
    }
