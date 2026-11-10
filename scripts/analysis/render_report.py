"""Render repository Markdown as a paginated report; no inference artifacts are read."""

import argparse
from html import escape
from pathlib import Path
from textwrap import wrap

import matplotlib
from markdown_it import MarkdownIt
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    LongTable,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
)


def inline(children):
    result = []
    links = []
    for token in children or []:
        if token.type == "text":
            result.append(escape(token.content))
        elif token.type == "code_inline":
            result.append(f'<font name="ReportMono">{escape(token.content)}</font>')
        elif token.type in {"strong_open", "strong_close", "em_open", "em_close"}:
            tag = "b" if token.type.startswith("strong") else "i"
            result.append(f"<{tag}>" if token.type.endswith("open") else f"</{tag}>")
        elif token.type in {"softbreak", "hardbreak"}:
            result.append(" " if token.type == "softbreak" else "<br/>")
        elif token.type == "link_open":
            href = token.attrGet("href") or ""
            external = href.startswith(("https://", "http://"))
            links.append(external)
            if external:
                result.append(f'<a href="{escape(href, quote=True)}" color="#225577">')
        elif token.type == "link_close":
            if links.pop():
                result.append("</a>")
        elif token.type != "image":
            result.append(escape(token.content))
    return "".join(result)


def render(source, output, status="Draft - follow-up synthesis pending", append=()):
    fonts = Path(matplotlib.get_data_path()) / "fonts/ttf"
    for family in ("DejaVuSerif", "DejaVuSans", "DejaVuSansMono"):
        suffixes = (
            ("", "-Bold", "-Italic", "-BoldItalic")
            if family == "DejaVuSerif"
            else ("", "-Bold", "-Oblique", "-BoldOblique")
        )
        alias = {
            "DejaVuSerif": "Report",
            "DejaVuSans": "ReportSans",
            "DejaVuSansMono": "ReportMono",
        }[family]
        for suffix, style in zip(suffixes, ("", "Bold", "Italic", "BoldItalic"), strict=True):
            pdfmetrics.registerFont(TTFont(alias + style, str(fonts / f"{family}{suffix}.ttf")))
        pdfmetrics.registerFontFamily(
            alias,
            normal=alias,
            bold=alias + "Bold",
            italic=alias + "Italic",
            boldItalic=alias + "BoldItalic",
        )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "ReportBody",
            fontName="Report",
            fontSize=9.5,
            leading=13.5,
            spaceAfter=7,
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            "ReportCell", fontName="ReportSans", fontSize=7.2, leading=10, splitLongWords=True
        )
    )
    styles.add(
        ParagraphStyle(
            "ReportCode",
            fontName="ReportMono",
            fontSize=7,
            leading=9,
            spaceAfter=10,
            backColor=colors.HexColor("#f3f5f6"),
        )
    )
    for level, size in ((1, 20), (2, 13), (3, 11)):
        styles.add(
            ParagraphStyle(
                f"ReportH{level}",
                fontName="ReportSansBold",
                fontSize=size,
                leading=size * 1.25,
                spaceBefore=14 if level > 1 else 0,
                spaceAfter=9,
                keepWithNext=True,
            )
        )
    parser = MarkdownIt("commonmark").enable("table")
    tokens = []
    for markdown in (source, *append):
        parsed = parser.parse(markdown.read_text())
        for token in parsed:
            for child in token.children or []:
                if child.type == "image":
                    child.attrSet("src", str((markdown.parent / child.attrGet("src")).resolve()))
        tokens.extend(parsed)
    flow = []
    width = 6.8 * inch
    i = 0
    list_depth = 0
    while i < len(tokens):
        token = tokens[i]
        if token.type in {"bullet_list_open", "ordered_list_open"}:
            list_depth += 1
        elif token.type in {"bullet_list_close", "ordered_list_close"}:
            list_depth -= 1
        elif token.type == "heading_open":
            level = min(int(token.tag[1:]), 3)
            flow.append(Paragraph(inline(tokens[i + 1].children), styles[f"ReportH{level}"]))
            i += 2
        elif token.type == "paragraph_open":
            content = tokens[i + 1]
            images = [t for t in content.children or [] if t.type == "image"]
            if images:
                for img in images:
                    path = source.parent / img.attrGet("src")
                    if not path.is_file():
                        raise ValueError(f"Missing report image: {path.name}")
                    image = Image(str(path))
                    factor = min(width / image.imageWidth, 4.6 * inch / image.imageHeight)
                    image.drawWidth = image.imageWidth * factor
                    image.drawHeight = image.imageHeight * factor
                    block = [Spacer(1, 6), image, Spacer(1, 7)]
                    if (
                        i + 4 < len(tokens)
                        and tokens[i + 3].type == "paragraph_open"
                        and tokens[i + 4].children
                        and tokens[i + 4].children[0].type == "em_open"
                    ):
                        block.append(
                            Paragraph(inline(tokens[i + 4].children), styles["ReportBody"])
                        )
                        i += 3
                    flow.append(KeepTogether(block))
            else:
                flow.append(
                    Paragraph(
                        inline(content.children),
                        styles["ReportBody"],
                        bulletText="•" if list_depth else None,
                    )
                )
            i += 2
        elif token.type in {"fence", "code_block"}:
            lines = [
                part
                for line in token.content.splitlines()
                for part in (wrap(line, width=100, replace_whitespace=False) or [""])
            ]
            flow.append(Preformatted("\n".join(lines), styles["ReportCode"]))
        elif token.type == "table_open":
            rows, cells = [], []
            while tokens[i].type != "table_close":
                t = tokens[i]
                if t.type == "tr_open":
                    cells = []
                elif t.type == "inline":
                    cells.append(Paragraph(inline(t.children), styles["ReportCell"]))
                elif t.type == "tr_close":
                    rows.append(cells)
                i += 1
            lengths = [
                max(len(row[c].getPlainText()) for row in rows) ** 0.55 for c in range(len(rows[0]))
            ]
            col_widths = [width * n / sum(lengths) for n in lengths]
            table = LongTable(rows, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf1")),
                        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#667788")),
                        ("LINEBELOW", (0, -1), (-1, -1), 0.4, colors.HexColor("#aab3bb")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 5),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
            flow.extend([table, Spacer(1, 10)])
        i += 1
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output),
        pagesize=(8.5 * inch, 11 * inch),
        rightMargin=0.85 * inch,
        leftMargin=0.85 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.65 * inch,
        title="Agent Safety Monitoring",
        author="Tatsuhiro Shimizu",
    )

    def page(canvas, doc):
        canvas.saveState()
        canvas.setFont("ReportSans", 7)
        canvas.setFillColor(colors.HexColor("#555e68"))
        canvas.drawString(0.85 * inch, 0.35 * inch, status)
        canvas.drawRightString(7.65 * inch, 0.35 * inch, str(doc.page))
        canvas.restoreState()

    doc.build(flow, onFirstPage=page, onLaterPages=page)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--append", type=Path, nargs="*", default=[])
    parser.add_argument("--status", default="Draft - follow-up synthesis pending")
    args = parser.parse_args()
    print(render(args.source, args.output, args.status, args.append))
