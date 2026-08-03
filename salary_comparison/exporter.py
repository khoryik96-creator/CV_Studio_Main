from __future__ import annotations

import math
import re
from datetime import datetime
from io import BytesIO
from typing import Any, Mapping
from xml.sax.saxutils import escape as xml_escape

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

REPORT_TITLE = "International Salary Comparison"
DISCLAIMER = (
    "Indicative planning only. Actual tax, payroll and statutory contributions may differ "
    "because of rebates, age, citizenship, residency stage, wage ceilings, benefits and "
    "payroll rounding. Review AI-updated rules and official sources before production use."
)

NAVY = "17324D"
BLUE = "2F75B5"
PALE_BLUE = "EAF3FB"
PALE_GREEN = "E8F7EF"
PALE_GREY = "F3F6F8"
MID_GREY = "DCE3EA"
DARK_GREY = "405064"
WHITE = "FFFFFF"

_XML_INVALID = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\uFFFE\uFFFF]")
_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def _clean_text(value: Any, fallback: str = "") -> str:
    text = _XML_INVALID.sub("", str(value if value is not None else fallback))
    return text.replace("\r\n", "\n").replace("\r", "\n")


def safe_filename(value: str, fallback: str = "salary-comparison") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", _clean_text(value).strip()).strip("-._")
    cleaned = (cleaned or fallback)[:100]
    if cleaned.upper().split(".", 1)[0] in _WINDOWS_RESERVED:
        cleaned = f"{fallback}-{cleaned}"
    return cleaned[:100]


def _scenario_name(scenario: Mapping[str, Any], fallback: str) -> str:
    return _clean_text(scenario.get("name") or fallback).strip() or fallback


def _money(value: Any, currency: str) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    if not math.isfinite(number):
        return "-"
    decimals = 0 if currency in {"IDR", "VND", "JPY", "KRW"} else 2
    return f"{currency} {number:,.{decimals}f}"


def _rate(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    return f"{number * 100:.1f}%" if math.isfinite(number) else "-"


def _number(value: Any, decimals: int = 2) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    return f"{number:,.{decimals}f}" if math.isfinite(number) else "-"


def _yes_no(value: Any) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return "Yes" if str(value).strip().lower() in {"yes", "true", "1", "on"} else "No"


def _variable_bonus_input(scenario: Mapping[str, Any]) -> str:
    mode = str(scenario.get("variable_bonus_mode") or "").strip().casefold()
    if not mode:
        mode = "months" if scenario.get("variable_bonus_months") not in (None, "") else "percentage"
    if mode == "months":
        return f"{_number(scenario.get('variable_bonus_months', 0), 1)} months of monthly base"
    return f"{_rate(scenario.get('variable_bonus_pct', 0))} of annual base"


def _input_rows(scenario: Mapping[str, Any], result: Mapping[str, Any]) -> list[tuple[str, str]]:
    currency = str(result["local_currency"])
    employee_override = scenario.get("employee_contribution_rate_override")
    employer_override = scenario.get("employer_contribution_rate_override")
    cap_override = scenario.get("contribution_cap_override")
    fx_override = scenario.get("fx_rate_override")
    return [
        ("Country", str(result["country"])),
        ("Tax year", str(result["tax_year"])),
        ("Residency", str(result["residency"])),
        ("Local currency", currency),
        ("Monthly base", _money(scenario.get("monthly_base", 0), currency)),
        ("Monthly fixed allowance", _money(scenario.get("monthly_fixed_allowance", 0), currency)),
        ("Guaranteed bonus months", _number(scenario.get("guaranteed_bonus_months", 0), 1)),
        ("Sign-On Bonus", _money(scenario.get("sign_on_bonus", scenario.get("fixed_annual_bonus", 0)), currency)),
        ("Variable performance bonus", _variable_bonus_input(scenario)),
        ("Other taxable income", _money(scenario.get("other_taxable_income", 0), currency)),
        ("Personal tax reliefs", _money(scenario.get("personal_tax_reliefs", 0), currency)),
        ("Other after-tax deductions", _money(scenario.get("other_after_tax_deductions", 0), currency)),
        ("Employee contribution override", "Automatic" if employee_override in (None, "") else _rate(employee_override)),
        ("Employer contribution override", "Automatic" if employer_override in (None, "") else _rate(employer_override)),
        ("Contribution remuneration cap", "Automatic" if cap_override in (None, "") else _money(cap_override, currency)),
        ("Include bonus in contribution base", _yes_no(scenario.get("include_bonus_in_contribution_base", True))),
        ("Reporting currency", str(result["reporting_currency"])),
        ("FX rate", f"1 {currency} = {_number(result['fx_rate'], 6)} {result['reporting_currency']}"),
        ("Manual FX override", "No" if fx_override in (None, "") else "Yes"),
    ]


def _result_rows(result: Mapping[str, Any]) -> list[tuple[str, str]]:
    currency = str(result["local_currency"])
    reporting = str(result["reporting_currency"])
    return [
        ("Annual base", _money(result["annual_base"], currency)),
        ("Annual fixed allowance", _money(result["annual_fixed_allowance"], currency)),
        ("Guaranteed bonus", _money(result["guaranteed_bonus"], currency)),
        ("Sign-On Bonus", _money(result.get("sign_on_bonus", result.get("fixed_annual_bonus", 0)), currency)),
        ("Variable performance bonus", _money(result["variable_bonus"], currency)),
        ("Other taxable income", _money(result["other_taxable_income"], currency)),
        ("Gross annual cash", _money(result["gross_annual_cash"], currency)),
        ("Gross monthly cash", _money(result["gross_monthly_cash"], currency)),
        ("Contribution base", _money(result["contribution_base"], currency)),
        ("Employee contribution rate", _rate(result["employee_contribution_rate"])),
        ("Employer contribution rate", _rate(result["employer_contribution_rate"])),
        ("Employee contribution", _money(result["employee_contribution"], currency)),
        ("Employer contribution", _money(result["employer_contribution"], currency)),
        ("Taxable income", _money(result["taxable_income"], currency)),
        ("Estimated income tax", _money(result["estimated_income_tax"], currency)),
        ("Marginal income tax rate", _rate(result["marginal_income_tax_rate"])),
        ("Net annual cash", _money(result["net_annual_cash"], currency)),
        ("Net monthly cash", _money(result["net_monthly_cash"], currency)),
        ("Total Gross plus Employer EPF", _money(result["total_employer_cost"], currency)),
        ("Effective tax rate on gross", _rate(result["effective_income_tax_rate"])),
        ("Total employee deduction rate", _rate(result["total_employee_deduction_rate"])),
        ("Net annual - reporting currency", _money(result["net_annual_reporting"], reporting)),
        ("Total Gross plus Employer EPF - reporting currency", _money(result["employer_cost_reporting"], reporting)),
    ]


def _comparison_rows(comparison: Mapping[str, Any]) -> list[tuple[str, str]]:
    currency = str(comparison["reporting_currency"])
    return [
        ("Reporting currency", currency),
        ("Net annual difference", _money(comparison["net_annual_difference"], currency)),
        ("Net uplift versus Scenario A", _rate(comparison["net_uplift_rate"])),
        ("Total Gross plus Employer EPF difference", _money(comparison["employer_cost_difference"], currency)),
    ]


def _rule_note(result: Mapping[str, Any]) -> str:
    meta = result.get("rule_metadata") or {}
    tax_status = "tax brackets verified" if meta.get("tax_brackets_verified") else "tax brackets require review"
    contribution_status = "contribution rule verified" if meta.get("contribution_rule_verified") else "contribution rule requires review"
    updated = _clean_text(meta.get("last_updated") or "not recorded")
    return _clean_text(f"Rule status: {tax_status}; {contribution_status}; last updated {updated}.")


def _set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def _set_cell_text(cell, text: str, *, bold: bool = False, color: str = DARK_GREY, size: float = 9) -> None:
    text = _clean_text(text)
    cell.text = ""
    paragraph = cell.paragraphs[0]
    paragraph.paragraph_format.space_after = Pt(0)
    run = paragraph.add_run(text)
    run.bold = bold
    run.font.name = "Aptos"
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor.from_string(color)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def _word_table(document: Document, rows: list[tuple[str, str]], *, title: str) -> None:
    heading = document.add_paragraph()
    heading.paragraph_format.space_before = Pt(8)
    heading.paragraph_format.space_after = Pt(4)
    run = heading.add_run(title.upper())
    run.bold = True
    run.font.name = "Aptos"
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor.from_string(BLUE)

    table = document.add_table(rows=1, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table.columns[0].width = Inches(2.25)
    table.columns[1].width = Inches(2.15)
    header = table.rows[0].cells
    _set_cell_text(header[0], "Metric", bold=True, color=WHITE)
    _set_cell_text(header[1], "Value", bold=True, color=WHITE)
    _set_cell_shading(header[0], NAVY)
    _set_cell_shading(header[1], NAVY)
    for index, (label, value) in enumerate(rows):
        cells = table.add_row().cells
        _set_cell_text(cells[0], label, color=DARK_GREY)
        _set_cell_text(cells[1], value, bold=label in {"Net annual cash", "Net monthly cash", "Total Gross plus Employer EPF"}, color=NAVY)
        if index % 2:
            _set_cell_shading(cells[0], PALE_GREY)
            _set_cell_shading(cells[1], PALE_GREY)


def build_docx_report(
    scenario_a_input: Mapping[str, Any],
    scenario_b_input: Mapping[str, Any],
    result_a: Mapping[str, Any],
    result_b: Mapping[str, Any],
    comparison: Mapping[str, Any],
    fx_metadata: Mapping[str, Any],
) -> bytes:
    """Build a stable three-page landscape Word report.

    Page 1 is a concise comparison. Pages 2 and 3 contain one scenario each,
    with inputs and calculated results in parallel columns. Keeping each
    scenario on its own page avoids Word/LibreOffice orphaning a nested-table
    heading at a page boundary.
    """
    document = Document()
    section = document.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width
    section.top_margin = Inches(0.45)
    section.bottom_margin = Inches(0.45)
    section.left_margin = Inches(0.55)
    section.right_margin = Inches(0.55)

    styles = document.styles
    styles["Normal"].font.name = "Aptos"
    styles["Normal"].font.size = Pt(8.5)

    def set_page_title(title_text: str, subtitle_text: str | None = None) -> None:
        title = document.add_paragraph()
        title.alignment = WD_ALIGN_PARAGRAPH.LEFT
        title.paragraph_format.space_before = Pt(0)
        title.paragraph_format.space_after = Pt(2)
        title.paragraph_format.keep_with_next = True
        title_run = title.add_run(_clean_text(title_text))
        title_run.bold = True
        title_run.font.name = "Aptos Display"
        title_run.font.size = Pt(20)
        title_run.font.color.rgb = RGBColor.from_string(NAVY)
        if subtitle_text:
            subtitle = document.add_paragraph()
            subtitle.paragraph_format.space_before = Pt(0)
            subtitle.paragraph_format.space_after = Pt(7)
            subtitle.paragraph_format.keep_with_next = True
            subtitle_run = subtitle.add_run(_clean_text(subtitle_text))
            subtitle_run.font.name = "Aptos"
            subtitle_run.font.size = Pt(8)
            subtitle_run.font.color.rgb = RGBColor.from_string(DARK_GREY)

    def add_compact_metric_table(cell, rows: list[tuple[str, str]], title_text: str) -> None:
        heading = cell.add_paragraph()
        heading.paragraph_format.space_before = Pt(0)
        heading.paragraph_format.space_after = Pt(2)
        heading.paragraph_format.keep_with_next = True
        run = heading.add_run(_clean_text(title_text.upper()))
        run.bold = True
        run.font.name = "Aptos"
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor.from_string(BLUE)

        table = cell.add_table(rows=1, cols=2)
        table.autofit = False
        table.columns[0].width = Inches(2.35)
        table.columns[1].width = Inches(2.25)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        header = table.rows[0].cells
        _set_cell_text(header[0], "Metric", bold=True, color=WHITE, size=7)
        _set_cell_text(header[1], "Value", bold=True, color=WHITE, size=7)
        _set_cell_shading(header[0], NAVY)
        _set_cell_shading(header[1], NAVY)

        key_labels = {
            "Gross annual cash", "Gross monthly cash", "Net annual cash",
            "Net monthly cash", "Total Gross plus Employer EPF",
        }
        for index, (label, value) in enumerate(rows):
            cells = table.add_row().cells
            _set_cell_text(cells[0], label, color=DARK_GREY, size=6.8)
            _set_cell_text(cells[1], value, bold=label in key_labels, color=NAVY, size=6.8)
            if index % 2:
                _set_cell_shading(cells[0], PALE_GREY)
                _set_cell_shading(cells[1], PALE_GREY)
            for current_cell in cells:
                tc_pr = current_cell._tc.get_or_add_tcPr()
                tc_mar = tc_pr.first_child_found_in("w:tcMar")
                if tc_mar is None:
                    tc_mar = OxmlElement("w:tcMar")
                    tc_pr.append(tc_mar)
                for edge, value_twips in (("top", "20"), ("left", "45"), ("bottom", "20"), ("right", "45")):
                    node = tc_mar.find(qn(f"w:{edge}"))
                    if node is None:
                        node = OxmlElement(f"w:{edge}")
                        tc_mar.append(node)
                    node.set(qn("w:w"), value_twips)
                    node.set(qn("w:type"), "dxa")

    # Page 1: report overview.
    set_page_title(
        REPORT_TITLE,
        f"Generated {datetime.now().strftime('%d %b %Y, %H:%M')} | "
        f"Reporting currency: {_clean_text(comparison['reporting_currency'])}",
    )

    summary_table = document.add_table(rows=1, cols=4)
    summary_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    summary_table.autofit = False
    summary_items = _comparison_rows(comparison)
    for index, (label, value) in enumerate(summary_items):
        cell = summary_table.rows[0].cells[index]
        cell.width = Inches(2.55)
        _set_cell_shading(cell, NAVY if index == 1 else PALE_BLUE)
        cell.text = ""
        paragraph = cell.paragraphs[0]
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(0)
        label_run = paragraph.add_run(_clean_text(label) + "\n")
        label_run.bold = True
        label_run.font.name = "Aptos"
        label_run.font.size = Pt(7.5)
        label_run.font.color.rgb = RGBColor.from_string(WHITE if index == 1 else BLUE)
        value_run = paragraph.add_run(_clean_text(value))
        value_run.bold = True
        value_run.font.name = "Aptos Display"
        value_run.font.size = Pt(12)
        value_run.font.color.rgb = RGBColor.from_string(WHITE if index == 1 else NAVY)

    spacer = document.add_paragraph()
    spacer.paragraph_format.space_after = Pt(2)

    reporting = str(comparison["reporting_currency"])
    overview_rows = [
        ("Gross annual cash", _money(result_a["gross_annual_cash"] * result_a["fx_rate"], reporting), _money(result_b["gross_annual_cash"] * result_b["fx_rate"], reporting)),
        ("Gross monthly cash", _money(result_a["gross_monthly_cash"] * result_a["fx_rate"], reporting), _money(result_b["gross_monthly_cash"] * result_b["fx_rate"], reporting)),
        ("Net annual cash", _money(result_a["net_annual_reporting"], reporting), _money(result_b["net_annual_reporting"], reporting)),
        ("Net monthly cash", _money(result_a["net_monthly_cash"] * result_a["fx_rate"], reporting), _money(result_b["net_monthly_cash"] * result_b["fx_rate"], reporting)),
        ("Total Gross plus Employer EPF", _money(result_a["employer_cost_reporting"], reporting), _money(result_b["employer_cost_reporting"], reporting)),
        ("Marginal tax rate", _rate(result_a["marginal_income_tax_rate"]), _rate(result_b["marginal_income_tax_rate"])),
        ("Effective tax rate on gross", _rate(result_a["effective_income_tax_rate"]), _rate(result_b["effective_income_tax_rate"])),
        ("Employee deduction rate", _rate(result_a["total_employee_deduction_rate"]), _rate(result_b["total_employee_deduction_rate"])),
    ]
    overview = document.add_table(rows=1, cols=3)
    overview.alignment = WD_TABLE_ALIGNMENT.CENTER
    overview.autofit = False
    overview.columns[0].width = Inches(3.55)
    overview.columns[1].width = Inches(3.3)
    overview.columns[2].width = Inches(3.3)
    headers = overview.rows[0].cells
    for cell, text in zip(headers, ("Metric", _scenario_name(scenario_a_input, "Scenario A"), _scenario_name(scenario_b_input, "Scenario B"))):
        _set_cell_text(cell, text, bold=True, color=WHITE, size=8)
        _set_cell_shading(cell, NAVY)
    for row_index, (label, value_a, value_b) in enumerate(overview_rows):
        cells = overview.add_row().cells
        _set_cell_text(cells[0], label, color=DARK_GREY, size=8)
        _set_cell_text(cells[1], value_a, bold=label in {"Net annual cash", "Net monthly cash", "Total Gross plus Employer EPF"}, color=NAVY, size=8)
        _set_cell_text(cells[2], value_b, bold=label in {"Net annual cash", "Net monthly cash", "Total Gross plus Employer EPF"}, color=NAVY, size=8)
        if row_index % 2:
            for cell in cells:
                _set_cell_shading(cell, PALE_GREY)
        if label in {"Net annual cash", "Net monthly cash"}:
            for cell in cells:
                _set_cell_shading(cell, PALE_GREEN)

    disclaimer = document.add_paragraph()
    disclaimer.paragraph_format.space_before = Pt(8)
    disclaimer.paragraph_format.space_after = Pt(0)
    disclaimer_run = disclaimer.add_run(DISCLAIMER)
    disclaimer_run.italic = True
    disclaimer_run.font.name = "Aptos"
    disclaimer_run.font.size = Pt(7.5)
    disclaimer_run.font.color.rgb = RGBColor.from_string(DARK_GREY)

    # Pages 2 and 3: one scenario per page with two parallel detail tables.
    scenario_specs = (
        (scenario_a_input, result_a, "Scenario A", fx_metadata.get("scenario_a") or {}),
        (scenario_b_input, result_b, "Scenario B", fx_metadata.get("scenario_b") or {}),
    )
    for scenario, result, fallback, fx in scenario_specs:
        document.add_page_break()
        set_page_title(
            _scenario_name(scenario, fallback),
            f"{result['country']} | {result['tax_year']} | {result['residency']} | {_rule_note(result)}",
        )
        columns = document.add_table(rows=1, cols=2)
        columns.alignment = WD_TABLE_ALIGNMENT.CENTER
        columns.autofit = False
        columns.columns[0].width = Inches(5.0)
        columns.columns[1].width = Inches(5.0)
        left, right = columns.rows[0].cells
        left.text = ""
        right.text = ""
        add_compact_metric_table(left, _input_rows(scenario, result), "Inputs and assumptions")
        add_compact_metric_table(right, _result_rows(result), "Calculated results")

        fx_note = document.add_paragraph()
        fx_note.paragraph_format.space_before = Pt(4)
        fx_note.paragraph_format.space_after = Pt(0)
        fx_run = fx_note.add_run(_clean_text(
            f"FX source: {fx.get('source', 'not recorded')}"
            + (" (cached)" if fx.get("cached") else "")
            + ("; stale fallback used" if fx.get("stale") else "")
        ))
        fx_run.font.name = "Aptos"
        fx_run.font.size = Pt(7)
        fx_run.font.color.rgb = RGBColor.from_string(DARK_GREY)

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_run = footer.add_run("CV Studio Salary Comparison")
    footer_run.font.name = "Aptos"
    footer_run.font.size = Pt(7.5)
    footer_run.font.color.rgb = RGBColor.from_string(DARK_GREY)

    output = BytesIO()
    document.save(output)
    return output.getvalue()

def _pdf_styles():
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=23,
            textColor=colors.HexColor(f"#{NAVY}"),
            alignment=TA_LEFT,
            spaceAfter=2 * mm,
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor(f"#{DARK_GREY}"),
            spaceAfter=5 * mm,
        ),
        "section": ParagraphStyle(
            "Section",
            parent=styles["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=7.8,
            leading=9,
            textColor=colors.HexColor(f"#{BLUE}"),
            spaceBefore=1.2 * mm,
            spaceAfter=0.7 * mm,
        ),
        "scenario": ParagraphStyle(
            "Scenario",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11.5,
            leading=13,
            textColor=colors.HexColor(f"#{NAVY}"),
            spaceAfter=1 * mm,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=6.4,
            leading=7.3,
            textColor=colors.HexColor(f"#{DARK_GREY}"),
        ),
        "cell": ParagraphStyle(
            "Cell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=5.9,
            leading=6.8,
            textColor=colors.HexColor(f"#{DARK_GREY}"),
        ),
        "value": ParagraphStyle(
            "Value",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=5.9,
            leading=6.8,
            alignment=TA_RIGHT,
            textColor=colors.HexColor(f"#{NAVY}"),
        ),
        "disclaimer": ParagraphStyle(
            "Disclaimer",
            parent=styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=6.4,
            leading=7.3,
            textColor=colors.HexColor(f"#{DARK_GREY}"),
        ),
    }


def _pdf_metric_table(rows: list[tuple[str, str]], styles: Mapping[str, ParagraphStyle], width: float) -> Table:
    data = [
        [Paragraph(xml_escape(_clean_text(label)), styles["cell"]), Paragraph(xml_escape(_clean_text(value)), styles["value"])]
        for label, value in rows
    ]
    table = Table(data, colWidths=[width * 0.53, width * 0.47], repeatRows=0)
    commands: list[tuple] = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 1.1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.1),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor(f"#{MID_GREY}")),
    ]
    for idx in range(len(data)):
        if idx % 2:
            commands.append(("BACKGROUND", (0, idx), (-1, idx), colors.HexColor(f"#{PALE_GREY}")))
    table.setStyle(TableStyle(commands))
    return table


def _pdf_scenario_block(
    scenario: Mapping[str, Any],
    result: Mapping[str, Any],
    fallback: str,
    fx: Mapping[str, Any],
    styles: Mapping[str, ParagraphStyle],
    width: float,
) -> list[Any]:
    return [
        Paragraph(xml_escape(_scenario_name(scenario, fallback)), styles["scenario"]),
        Paragraph(
            xml_escape(f"{result['country']} | {result['tax_year']} | {result['residency']}") + "<br/>" + xml_escape(_rule_note(result)),
            styles["small"],
        ),
        Paragraph("INPUTS AND ASSUMPTIONS", styles["section"]),
        _pdf_metric_table(_input_rows(scenario, result), styles, width),
        Paragraph("CALCULATED RESULTS", styles["section"]),
        _pdf_metric_table(_result_rows(result), styles, width),
        Spacer(1, 1.5 * mm),
        Paragraph(
            xml_escape(_clean_text(
                f"FX source: {fx.get('source', 'not recorded')}"
                + (" (cached)" if fx.get("cached") else "")
                + ("; stale fallback used" if fx.get("stale") else "")
            )),
            styles["small"],
        ),
    ]


def build_pdf_report(
    scenario_a_input: Mapping[str, Any],
    scenario_b_input: Mapping[str, Any],
    result_a: Mapping[str, Any],
    result_b: Mapping[str, Any],
    comparison: Mapping[str, Any],
    fx_metadata: Mapping[str, Any],
) -> bytes:
    output = BytesIO()
    page_size = landscape(A4)
    document = SimpleDocTemplate(
        output,
        pagesize=page_size,
        leftMargin=11 * mm,
        rightMargin=11 * mm,
        topMargin=8 * mm,
        bottomMargin=10 * mm,
        title=REPORT_TITLE,
        author="CV Studio",
    )
    styles = _pdf_styles()
    story: list[Any] = [
        Paragraph(REPORT_TITLE, styles["title"]),
        Paragraph(
            f"Generated {datetime.now().strftime('%d %b %Y, %H:%M')} | "
            f"Reporting currency: {xml_escape(_clean_text(comparison['reporting_currency']))}",
            styles["subtitle"],
        ),
    ]

    summary_data = []
    for idx, (label, value) in enumerate(_comparison_rows(comparison)):
        label_style = ParagraphStyle(
            f"SummaryLabel{idx}", parent=styles["small"], fontName="Helvetica-Bold",
            textColor=colors.white if idx == 1 else colors.HexColor(f"#{BLUE}"),
        )
        value_style = ParagraphStyle(
            f"SummaryValue{idx}", parent=styles["scenario"], fontSize=11,
            textColor=colors.white if idx == 1 else colors.HexColor(f"#{NAVY}"),
        )
        summary_data.append([Paragraph(xml_escape(_clean_text(label)), label_style), Paragraph(xml_escape(_clean_text(value)), value_style)])
    summary = Table([summary_data], colWidths=[document.width / 4] * 4)
    summary_style: list[tuple] = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(f"#{MID_GREY}")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor(f"#{MID_GREY}")),
    ]
    for idx in range(4):
        summary_style.append(("BACKGROUND", (idx, 0), (idx, 0), colors.HexColor(f"#{NAVY if idx == 1 else PALE_BLUE}")))
    summary.setStyle(TableStyle(summary_style))
    story.extend([summary, Spacer(1, 5 * mm)])

    reporting = str(comparison["reporting_currency"])
    overview_header = ParagraphStyle(
        "OverviewHeader",
        parent=styles["value"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=8,
        textColor=colors.white,
    )
    overview_rows = [
        [
            Paragraph("Metric", overview_header),
            Paragraph(xml_escape(_scenario_name(scenario_a_input, "Scenario A")), overview_header),
            Paragraph(xml_escape(_scenario_name(scenario_b_input, "Scenario B")), overview_header),
        ],
        [Paragraph("Gross annual cash", styles["cell"]), Paragraph(_money(result_a["gross_annual_cash"] * result_a["fx_rate"], reporting), styles["value"]), Paragraph(_money(result_b["gross_annual_cash"] * result_b["fx_rate"], reporting), styles["value"])],
        [Paragraph("Gross monthly cash", styles["cell"]), Paragraph(_money(result_a["gross_monthly_cash"] * result_a["fx_rate"], reporting), styles["value"]), Paragraph(_money(result_b["gross_monthly_cash"] * result_b["fx_rate"], reporting), styles["value"])],
        [Paragraph("Net annual cash", styles["cell"]), Paragraph(_money(result_a["net_annual_reporting"], reporting), styles["value"]), Paragraph(_money(result_b["net_annual_reporting"], reporting), styles["value"])],
        [Paragraph("Net monthly cash", styles["cell"]), Paragraph(_money(result_a["net_monthly_cash"] * result_a["fx_rate"], reporting), styles["value"]), Paragraph(_money(result_b["net_monthly_cash"] * result_b["fx_rate"], reporting), styles["value"])],
        [Paragraph("Total Gross plus Employer EPF", styles["cell"]), Paragraph(_money(result_a["employer_cost_reporting"], reporting), styles["value"]), Paragraph(_money(result_b["employer_cost_reporting"], reporting), styles["value"])],
        [Paragraph("Marginal tax rate", styles["cell"]), Paragraph(_rate(result_a["marginal_income_tax_rate"]), styles["value"]), Paragraph(_rate(result_b["marginal_income_tax_rate"]), styles["value"])],
        [Paragraph("Effective tax rate on gross", styles["cell"]), Paragraph(_rate(result_a["effective_income_tax_rate"]), styles["value"]), Paragraph(_rate(result_b["effective_income_tax_rate"]), styles["value"])],
        [Paragraph("Employee deduction rate", styles["cell"]), Paragraph(_rate(result_a["total_employee_deduction_rate"]), styles["value"]), Paragraph(_rate(result_b["total_employee_deduction_rate"]), styles["value"])],
    ]
    overview = Table(overview_rows, colWidths=[document.width * 0.36, document.width * 0.32, document.width * 0.32])
    overview.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(f"#{NAVY}")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor(f"#{MID_GREY}")),
        ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor(f"#{PALE_GREEN}")),
        ("BACKGROUND", (0, 4), (-1, 4), colors.HexColor(f"#{PALE_GREEN}")),
    ]))
    story.extend([
        Paragraph("SIDE-BY-SIDE OVERVIEW", styles["section"]),
        overview,
        Spacer(1, 5 * mm),
        Paragraph(DISCLAIMER, styles["disclaimer"]),
        PageBreak(),
    ])

    story.extend(_pdf_scenario_block(
        scenario_a_input, result_a, "Scenario A", fx_metadata.get("scenario_a") or {}, styles, document.width
    ))
    story.append(PageBreak())
    story.extend(_pdf_scenario_block(
        scenario_b_input, result_b, "Scenario B", fx_metadata.get("scenario_b") or {}, styles, document.width
    ))
    story.extend([Spacer(1, 4 * mm), Paragraph(DISCLAIMER, styles["disclaimer"])])

    def page_footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor(f"#{MID_GREY}"))
        canvas.setLineWidth(0.4)
        canvas.line(11 * mm, 8 * mm, page_size[0] - 11 * mm, 8 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor(f"#{DARK_GREY}"))
        canvas.drawString(11 * mm, 4.5 * mm, "CV Studio Salary Comparison")
        canvas.drawRightString(page_size[0] - 11 * mm, 4.5 * mm, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
    return output.getvalue()
