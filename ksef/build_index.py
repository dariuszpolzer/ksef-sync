from pathlib import Path
import json


def build_batch_index(batch_dir: Path):
    batch_dir = Path(batch_dir)
    manifest_file = batch_dir / "manifest.json"

    if not manifest_file.exists():
        raise RuntimeError("Brak manifest.json w batchu")

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))

    invoices = manifest.get("invoices", [])
    pdf_info = manifest.get("pdf", {})

    html_rows = []

    for inv in invoices:
        filename = inv["filename"]
        nr_ksef = inv["nr_ksef"]

        xml_link = f"invoices/{filename}"
        pdf_link = f"pdf/{Path(filename).stem}.pdf"

        html_rows.append(f"""
<tr>
<td>{nr_ksef}</td>
<td><a href="{xml_link}" target="_blank">XML</a></td>
<td><a href="{pdf_link}" target="_blank">PDF</a></td>
</tr>
""")

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>KSeF batch {manifest["batch"]["batch_id"]}</title>

<style>
body {{
    font-family: Arial;
    margin: 40px;
}}

table {{
    border-collapse: collapse;
    width: 100%;
}}

th, td {{
    border: 1px solid #ccc;
    padding: 8px;
}}

th {{
    background: #f2f2f2;
}}

tr:hover {{
    background: #fafafa;
}}
</style>

</head>

<body>

<h2>KSeF Batch: {manifest["batch"]["batch_id"]}</h2>

<p>
Faktur: {manifest["batch"]["invoice_count"]}
</p>

<table>

<tr>
<th>Nr KSeF</th>
<th>XML</th>
<th>PDF</th>
</tr>

{''.join(html_rows)}

</table>

</body>
</html>
"""

    output_file = batch_dir / "index.html"
    output_file.write_text(html, encoding="utf-8")

    return output_file