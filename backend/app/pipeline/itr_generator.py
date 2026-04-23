"""
ITR output generator: JSON, XML (ITR-1 schema), and PDF summary.
"""
from __future__ import annotations
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from loguru import logger
from app.pipeline.tax_engine import TaxResult
from app.pipeline.ner_extractor import ExtractionOutput


def _entities_to_dict(extraction: ExtractionOutput) -> dict:
    return {k: v.value for k, v in extraction.entities.items()}


def generate_itr_json(extraction: ExtractionOutput, tax_result: TaxResult, output_dir: Path) -> Path:
    """Generate ITR-1 JSON (simplified schema)."""
    ents = _entities_to_dict(extraction)
    itr = {
        "ITR": {
            "ITR1": {
                "CreationInfo": {
                    "SWCreatedBy": "TaxBuddyIndia",
                    "SWVersionNo": "1.0",
                    "JSONCreatedDate": datetime.utcnow().strftime("%Y-%m-%d"),
                },
                "Form_ITR1": {
                    "AssessmentYear": ents.get("assessment_year", "2024-25"),
                    "PersonalInfo": {
                        "AssesseeName": {
                            "FirstName": ents.get("employee_name", ""),
                        },
                        "PAN": ents.get("pan", ""),
                    },
                    "IncomeDeductions": {
                        "Salary": ents.get("gross_salary", 0),
                        "DeductionsUnderChVI_A": {
                            "Section80C": ents.get("section_80c", 0),
                            "Section80D": ents.get("section_80d", 0),
                            "Section80E": ents.get("section_80e", 0),
                            "Section80G": ents.get("section_80g", 0),
                        },
                    },
                    "TaxComputation": {
                        "Regime": tax_result.regime.upper(),
                        "GrossIncome": tax_result.gross_income,
                        "TotalDeductions": tax_result.total_deductions,
                        "TaxableIncome": tax_result.taxable_income,
                        "TaxLiability": tax_result.tax_before_cess,
                        "Surcharge": tax_result.surcharge,
                        "Rebate87A": tax_result.rebate_87a,
                        "Cess": tax_result.cess,
                        "TotalTax": tax_result.total_tax,
                        "TDSPaid": tax_result.tds_paid,
                        tax_result.refund_or_payable_label.replace(" ", ""): tax_result.refund_or_payable,
                    },
                    "Verification": {
                        "Declaration": "I solemnly declare that to the best of my knowledge and belief, the information given is correct and complete.",
                    },
                },
            }
        }
    }
    out_path = output_dir / f"ITR1_{uuid.uuid4().hex[:8]}.json"
    out_path.write_text(json.dumps(itr, indent=2))
    return out_path


def generate_itr_xml(extraction: ExtractionOutput, tax_result: TaxResult, output_dir: Path) -> Path:
    """Generate ITR-1 XML."""
    from lxml import etree

    ents = _entities_to_dict(extraction)

    root = etree.Element("ITR")
    itr1 = etree.SubElement(root, "ITR1")

    ci = etree.SubElement(itr1, "CreationInfo")
    etree.SubElement(ci, "SWCreatedBy").text = "TaxBuddyIndia"
    etree.SubElement(ci, "JSONCreatedDate").text = datetime.utcnow().strftime("%Y-%m-%d")

    pi = etree.SubElement(itr1, "PersonalInfo")
    etree.SubElement(pi, "PAN").text = str(ents.get("pan", ""))
    etree.SubElement(pi, "Name").text = str(ents.get("employee_name", ""))

    inc = etree.SubElement(itr1, "IncomeDeductions")
    etree.SubElement(inc, "GrossSalary").text = str(ents.get("gross_salary", 0))

    ded = etree.SubElement(inc, "DeductionsChVI_A")
    etree.SubElement(ded, "Section80C").text = str(ents.get("section_80c", 0))
    etree.SubElement(ded, "Section80D").text = str(ents.get("section_80d", 0))

    tc = etree.SubElement(itr1, "TaxComputation")
    etree.SubElement(tc, "Regime").text = tax_result.regime.upper()
    etree.SubElement(tc, "TaxableIncome").text = str(tax_result.taxable_income)
    etree.SubElement(tc, "TotalTax").text = str(round(tax_result.total_tax, 2))
    etree.SubElement(tc, "TDSPaid").text = str(tax_result.tds_paid)
    etree.SubElement(tc, tax_result.refund_or_payable_label.replace(" ", "")).text = str(round(tax_result.refund_or_payable, 2))

    out_path = output_dir / f"ITR1_{uuid.uuid4().hex[:8]}.xml"
    tree = etree.ElementTree(root)
    tree.write(str(out_path), pretty_print=True, xml_declaration=True, encoding="UTF-8")
    return out_path


def generate_pdf_summary(extraction: ExtractionOutput, tax_result: TaxResult, output_dir: Path) -> Path:
    """Generate a human-readable PDF tax summary."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.units import cm

        ents = _entities_to_dict(extraction)
        out_path = output_dir / f"TaxSummary_{uuid.uuid4().hex[:8]}.pdf"
        doc = SimpleDocTemplate(str(out_path), pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        story = []

        # Title
        title_style = ParagraphStyle("Title", parent=styles["Heading1"], fontSize=18, spaceAfter=6)
        story.append(Paragraph("Tax Buddy India — Tax Summary", title_style))
        story.append(Paragraph(f"Generated: {datetime.utcnow().strftime('%d %b %Y')}", styles["Normal"]))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#10b981")))
        story.append(Spacer(1, 0.4*cm))

        # Personal Info
        story.append(Paragraph("Personal Information", styles["Heading2"]))
        personal = [
            ["PAN", ents.get("pan", "N/A")],
            ["Employee Name", ents.get("employee_name", "N/A")],
            ["Employer Name", ents.get("employer_name", "N/A")],
            ["Assessment Year", ents.get("assessment_year", "2024-25")],
        ]
        t = Table(personal, colWidths=[6*cm, 10*cm])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d1fae5")),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f0fdf4")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.4*cm))

        # Tax Computation
        story.append(Paragraph(f"Tax Computation — {tax_result.regime.title()} Regime", styles["Heading2"]))
        tax_rows = [
            ["Item", "Amount (₹)"],
            ["Gross Income", f"{tax_result.gross_income:,.0f}"],
            ["Total Deductions", f"({tax_result.total_deductions:,.0f})"],
            ["Taxable Income", f"{tax_result.taxable_income:,.0f}"],
            ["Tax Before Cess", f"{tax_result.tax_before_cess:,.0f}"],
            ["Surcharge", f"{tax_result.surcharge:,.0f}"],
            ["Rebate u/s 87A", f"({tax_result.rebate_87a:,.0f})"],
            [f"Cess ({tax_result.cess_rate*100:.0f}%)", f"{tax_result.cess:,.0f}"],
            ["Total Tax Liability", f"{tax_result.total_tax:,.2f}"],
            ["TDS Paid", f"({tax_result.tds_paid:,.0f})"],
            [tax_result.refund_or_payable_label, f"{tax_result.refund_or_payable:,.2f}"],
        ]
        t2 = Table(tax_rows, colWidths=[10*cm, 6*cm])
        t2.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#10b981")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0fdf4")]),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fef3c7")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t2)
        story.append(Spacer(1, 0.4*cm))

        # Disclaimer
        disc = ParagraphStyle("Disclaimer", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#6b7280"))
        story.append(Paragraph("Disclaimer: This is an estimate for educational purposes only. Consult a qualified CA for final filing.", disc))

        doc.build(story)
        return out_path
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        # Return a placeholder path
        out_path = output_dir / "summary_unavailable.txt"
        out_path.write_text(f"PDF generation failed: {e}")
        return out_path
