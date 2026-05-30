from ksef.invoice_xml import classify_ksef_invoice_xml

FA3_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Faktura xmlns="http://crd.gov.pl/wzor/2025/06/25/13775/">
  <Podmiot1><DaneIdentyfikacyjne><NIP>6791444505</NIP></DaneIdentyfikacyjne></Podmiot1>
  <Podmiot2><DaneIdentyfikacyjne><NIP>1234567890</NIP></DaneIdentyfikacyjne></Podmiot2>
  <Fa>
    <P_1>2026-04-01</P_1>
    <P_2>FV/1/2026</P_2>
    <FaWiersz><P_7>Usługa</P_7><P_11>100</P_11><P_12>23</P_12></FaWiersz>
  </Fa>
</Faktura>
"""


def test_classify_ksef_invoice_xml_accepts_fa3_invoice(tmp_path):
    path = tmp_path / "invoice.xml"
    path.write_text(FA3_XML, encoding="utf-8")

    result = classify_ksef_invoice_xml(path)

    assert result["ok"] is True
    assert result["schema"]["logical_name"] == "FA(3)"


def test_classify_ksef_invoice_xml_rejects_random_xml(tmp_path):
    path = tmp_path / "random.xml"
    path.write_text("<Root><Value>not invoice</Value></Root>", encoding="utf-8")

    result = classify_ksef_invoice_xml(path)

    assert result["ok"] is False
    assert result["reason"] == "root element is not Faktura"
