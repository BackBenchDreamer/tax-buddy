from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.schemas import ITRGenerationResult, TaxComputationResult


class OutputService:
    def generate(self, document_id: int, output_dir: Path, extraction: dict[str, Any], validation: dict[str, Any], tax: TaxComputationResult) -> ITRGenerationResult:
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / f"itr_{document_id}_{timestamp}.json"
        xml_path = output_dir / f"itr_{document_id}_{timestamp}.xml"
        report_path = output_dir / f"itr_{document_id}_{timestamp}.pdf"

        payload = {
            "document_id": document_id,
            "generated_at": datetime.utcnow().isoformat(),
            "extraction": extraction,
            "validation": validation,
            "tax": json.loads(tax.model_dump_json()),
            "itr_form": self._form_payload(extraction, tax),
        }
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        xml_path.write_text(self._to_xml(payload), encoding="utf-8")
        self._write_pdf(report_path, payload)
        return ITRGenerationResult(
            document_id=document_id,
            json_path=str(json_path),
            xml_path=str(xml_path),
            report_path=str(report_path),
            payload=payload,
        )

    def _form_payload(self, extraction: dict[str, Any], tax: TaxComputationResult) -> dict[str, Any]:
        entity_map = {entity["label"]: entity["value"] for entity in extraction.get("entities", [])}
        return {
            "itr_type": "ITR-1",
            "pan": entity_map.get("PAN"),
            "tan": entity_map.get("TAN"),
            "taxable_income": tax.taxable_income,
            "tax_liability": tax.tax_liability,
            "refund_payable": tax.refund_payable,
            "entities": extraction.get("entities", []),
        }

    def _to_xml(self, payload: dict[str, Any]) -> str:
        root = ET.Element("ITRDocument")
        for key, value in payload.items():
            element = ET.SubElement(root, key)
            element.text = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        return ET.tostring(root, encoding="unicode")

    def _write_pdf(self, report_path: Path, payload: dict[str, Any]) -> None:
        pdf = canvas.Canvas(str(report_path), pagesize=A4)
        width, height = A4
        y = height - 48
        pdf.setTitle("Tax Buddy Summary Report")
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(48, y, "Tax Buddy Summary Report")
        y -= 28
        pdf.setFont("Helvetica", 10)
        lines = [
            f"Document ID: {payload['document_id']}",
            f"Generated At: {payload['generated_at']}",
            f"Taxable Income: {payload['tax']['taxable_income']}",
            f"Tax Liability: {payload['tax']['tax_liability']}",
            f"Refund/Payable: {payload['tax']['refund_payable']}",
            "Validation Issues:",
        ]
        for issue in payload["validation"].get("issues", []):
            lines.append(f"- {issue['field']}: {issue['message']} ({issue['severity']})")
        for line in lines:
            pdf.drawString(48, y, line[:110])
            y -= 16
            if y < 72:
                pdf.showPage()
                y = height - 48
                pdf.setFont("Helvetica", 10)
        pdf.save()
