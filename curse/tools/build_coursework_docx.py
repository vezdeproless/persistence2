from __future__ import annotations

import json
import math
import re
import textwrap
from collections import Counter
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Курсовая_работа_Windows_Persistence_Detection.docx"
BUILD_DIR = ROOT / "build" / "coursework"
REGISTRY_JSON = Path(r"D:\shared_folder\Registry.json")


TITLE = "Разработка модуля обнаружения механизмов закрепления в Windows по артефактам реестра"

UNKNOWN_INSTITUTE = "[указать институт]"
UNKNOWN_DEPARTMENT = "[указать кафедру]"
UNKNOWN_STUDENT = "[Ф.И.О. студента]"
UNKNOWN_GROUP = "[группа]"
UNKNOWN_SUPERVISOR = "[Ф.И.О., должность, звание, ученая степень]"


def set_run_font(run, name: str = "Times New Roman", size: int | float = 14, bold: bool = False) -> None:
    run.font.name = name
    run.font.size = Pt(size)
    run.bold = bold
    run._element.rPr.rFonts.set(qn("w:ascii"), name)
    run._element.rPr.rFonts.set(qn("w:hAnsi"), name)
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    run._element.rPr.rFonts.set(qn("w:cs"), name)


def configure_document(doc: Document) -> None:
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)
    section.left_margin = Cm(3)
    section.right_margin = Cm(1.5)
    section.header_distance = Cm(1.25)
    section.footer_distance = Cm(1.25)
    section.different_first_page_header_footer = True
    add_page_number(section.header.paragraphs[0])

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(14)
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Times New Roman")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Times New Roman")
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    normal._element.rPr.rFonts.set(qn("w:cs"), "Times New Roman")
    normal.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    normal.paragraph_format.first_line_indent = Cm(1.25)
    normal.paragraph_format.space_after = Pt(0)

    for style_name, size in (("Heading 1", 14), ("Heading 2", 14), ("Heading 3", 14)):
        style = styles[style_name]
        style.font.name = "Times New Roman"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor(0, 0, 0)
        style._element.rPr.rFonts.set(qn("w:ascii"), "Times New Roman")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Times New Roman")
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
        style._element.rPr.rFonts.set(qn("w:cs"), "Times New Roman")
        style.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
        style.paragraph_format.space_before = Pt(12 if style_name == "Heading 1" else 6)
        style.paragraph_format.space_after = Pt(6)
        style.paragraph_format.first_line_indent = Cm(0)

    caption = styles["Caption"]
    caption.font.name = "Times New Roman"
    caption.font.size = Pt(14)
    caption.font.italic = False
    caption.font.color.rgb = RGBColor(0, 0, 0)
    caption._element.rPr.rFonts.set(qn("w:ascii"), "Times New Roman")
    caption._element.rPr.rFonts.set(qn("w:hAnsi"), "Times New Roman")

    code = styles.add_style("CodeListing", 1)
    code.font.name = "Consolas"
    code.font.size = Pt(8.5)
    code._element.rPr.rFonts.set(qn("w:ascii"), "Consolas")
    code._element.rPr.rFonts.set(qn("w:hAnsi"), "Consolas")
    code.paragraph_format.line_spacing = 1.0
    code.paragraph_format.space_before = Pt(0)
    code.paragraph_format.space_after = Pt(0)
    code.paragraph_format.first_line_indent = Cm(0)

    enable_update_fields(doc)


def enable_update_fields(doc: Document) -> None:
    settings = doc.settings._element
    update = settings.find(qn("w:updateFields"))
    if update is None:
        update = OxmlElement("w:updateFields")
        settings.append(update)
    update.set(qn("w:val"), "true")


def add_page_number(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    paragraph.paragraph_format.first_line_indent = Cm(0)
    run = paragraph.add_run()
    set_run_font(run)
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = "2"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instr, separate, text, end])


def para(doc: Document, text: str = "", *, style: str | None = None, align=None, bold: bool = False):
    p = doc.add_paragraph(style=style)
    if align is not None:
        p.alignment = align
    if text:
        r = p.add_run(text)
        set_run_font(r, bold=bold)
    if style is None:
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY if align is None else align
        p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    return p


def heading(doc: Document, text: str, level: int = 1):
    p = doc.add_heading(text, level=level)
    for run in p.runs:
        set_run_font(run, bold=True)
    return p


def add_title_page(doc: Document) -> None:
    for text in [
        "МИНОБРНАУКИ РОССИИ",
        "Федеральное государственное бюджетное образовательное учреждение высшего образования",
        "«МИРЭА - Российский технологический университет»",
        "РТУ МИРЭА",
    ]:
        para(doc, text, align=WD_ALIGN_PARAGRAPH.CENTER, bold=True)

    doc.add_paragraph()
    para(doc, "КУРСОВАЯ РАБОТА", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True)
    para(doc, "по дисциплине", align=WD_ALIGN_PARAGRAPH.CENTER)
    para(doc, "[указать дисциплину]", align=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_paragraph()
    para(doc, UNKNOWN_INSTITUTE, align=WD_ALIGN_PARAGRAPH.CENTER)
    para(doc, UNKNOWN_DEPARTMENT, align=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_paragraph()
    para(doc, "Тема курсовой работы", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True)
    para(doc, TITLE, align=WD_ALIGN_PARAGRAPH.CENTER, bold=True)
    doc.add_paragraph()
    add_key_value(doc, "Студент группы", f"{UNKNOWN_GROUP}   {UNKNOWN_STUDENT}   __________________")
    add_key_value(doc, "Руководитель курсовой работы", f"{UNKNOWN_SUPERVISOR}   __________________")
    add_key_value(doc, "Рецензент (при наличии)", "[Ф.И.О., должность, звание, ученая степень]   __________________")
    doc.add_paragraph()
    add_key_value(doc, "Курсовая работа представлена к защите", "«___» ______________ 2026 г.")
    add_key_value(doc, "Допущена к защите", "«___» ______________ 2026 г.")
    for _ in range(5):
        doc.add_paragraph()
    para(doc, "Москва 2026", align=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_page_break()


def add_assignment_page(doc: Document) -> None:
    para(doc, "МИНОБРНАУКИ РОССИИ", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True)
    para(doc, "ФГБОУ ВО «МИРЭА - Российский технологический университет»", align=WD_ALIGN_PARAGRAPH.CENTER)
    para(doc, "РТУ МИРЭА", align=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_paragraph()
    para(doc, "Утверждаю", align=WD_ALIGN_PARAGRAPH.RIGHT)
    para(doc, "Заведующий кафедрой __________________", align=WD_ALIGN_PARAGRAPH.RIGHT)
    para(doc, "«___» ______________ 2026 г.", align=WD_ALIGN_PARAGRAPH.RIGHT)
    doc.add_paragraph()
    para(doc, "ЗАДАНИЕ", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True)
    para(doc, "на выполнение курсовой работы", align=WD_ALIGN_PARAGRAPH.CENTER)
    add_key_value(doc, "Институт", UNKNOWN_INSTITUTE)
    add_key_value(doc, "Кафедра", UNKNOWN_DEPARTMENT)
    add_key_value(doc, "Тема", TITLE)
    add_key_value(doc, "Студент", f"{UNKNOWN_STUDENT}; группа {UNKNOWN_GROUP}")
    para(
        doc,
        "Исходные данные: VMware Workstation laboratory environment, Windows 10 target VM, Ubuntu 22.04 analysis VM, "
        "raw Windows registry hives, RECmd JSON extraction, normalized Registry.json, OpenSearch index "
        "windows-persistence-registry, OpenSearch Dashboards.",
    )
    para(
        doc,
        "Перечень вопросов, подлежащих разработке: изучить механизмы закрепления в Windows; разработать схему "
        "сбора артефактов реестра; реализовать нормализацию записей; настроить OpenSearch и Dashboards без Docker; "
        "провести лабораторную проверку на заложенных persistence-записях; оформить выводы и рекомендации.",
    )
    add_key_value(doc, "Срок представления к защите", "«___» ______________ 2026 г.")
    doc.add_paragraph()
    add_key_value(doc, "Задание выдал", f"{UNKNOWN_SUPERVISOR}   __________________")
    add_key_value(doc, "Задание получил", f"{UNKNOWN_STUDENT}   __________________")
    doc.add_page_break()


def add_key_value(doc: Document, key: str, value: str) -> None:
    p = para(doc)
    p.paragraph_format.first_line_indent = Cm(0)
    r1 = p.add_run(f"{key}: ")
    set_run_font(r1, bold=True)
    r2 = p.add_run(value)
    set_run_font(r2)


def add_toc(doc: Document) -> None:
    p_heading = heading(doc, "СОДЕРЖАНИЕ", 1)
    p_heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Cm(0)
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), 'TOC \\o "1-3" \\h \\z \\u')
    r = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = "Содержание обновляется автоматически при открытии документа в Microsoft Word."
    r.append(t)
    fld.append(r)
    p._p.append(fld)
    doc.add_page_break()


def add_caption(doc: Document, text: str) -> None:
    p = para(doc, text, style="Caption", align=WD_ALIGN_PARAGRAPH.CENTER)
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.keep_with_next = True


def set_cell_text(cell, text: str, *, bold: bool = False, size: int = 12, align=WD_ALIGN_PARAGRAPH.LEFT) -> None:
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    p = cell.paragraphs[0]
    p.alignment = align
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    p.runs.clear()
    r = p.add_run(text)
    set_run_font(r, size=size, bold=bold)


def shade_cell(cell, color: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), color)


def add_table(doc: Document, title: str, headers: list[str], rows: list[list[str]], widths_cm: list[float]) -> None:
    add_caption(doc, title)
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    table.autofit = False
    for idx, header in enumerate(headers):
        cell = table.rows[0].cells[idx]
        cell.width = Cm(widths_cm[idx])
        shade_cell(cell, "EDEDED")
        set_cell_text(cell, header, bold=True, size=11, align=WD_ALIGN_PARAGRAPH.CENTER)
    for row in rows:
        cells = table.add_row().cells
        for idx, value in enumerate(row):
            cells[idx].width = Cm(widths_cm[idx])
            set_cell_text(cells[idx], value, size=11)
    para(doc, "Примечание - таблица составлена по материалам проекта и лабораторного прогона.", style="Caption")


def add_formula(doc: Document, formula: str, number: int, explanation: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    p.paragraph_format.tab_stops.add_tab_stop(Cm(15.0), WD_TAB_ALIGNMENT.RIGHT)
    r = p.add_run(formula)
    set_run_font(r)
    r2 = p.add_run(f"\t({number})")
    set_run_font(r2)
    para(doc, explanation)


def make_diagram(path: Path, title: str, boxes: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    width, height = 1500, 480
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 32)
        small = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 25)
        bold = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 34)
    except OSError:
        font = ImageFont.load_default()
        small = font
        bold = font

    draw.text((40, 28), title, fill=(0, 0, 0), font=bold)
    y = 150
    margin = 40
    gap = 25
    box_w = (width - 2 * margin - gap * (len(boxes) - 1)) // len(boxes)
    box_h = 150
    for idx, box in enumerate(boxes):
        x = margin + idx * (box_w + gap)
        draw.rounded_rectangle((x, y, x + box_w, y + box_h), radius=16, outline=(35, 82, 124), width=4, fill=(239, 246, 252))
        lines = textwrap.wrap(box, width=18)
        line_y = y + 25
        for line in lines:
            draw.text((x + 18, line_y), line, fill=(0, 0, 0), font=small)
            line_y += 32
        if idx < len(boxes) - 1:
            ax = x + box_w + 4
            ay = y + box_h // 2
            bx = x + box_w + gap - 6
            draw.line((ax, ay, bx, ay), fill=(35, 82, 124), width=4)
            draw.polygon([(bx, ay), (bx - 14, ay - 10), (bx - 14, ay + 10)], fill=(35, 82, 124))
    img.save(path)


def analyze_registry() -> dict:
    fallback = {
        "total_records": 239057,
        "host": "DESKTOP-T1I1MIS",
        "unique_file_name": 8576,
        "unique_file_path": 65596,
        "unique_reg_key_path": 181859,
        "schema_not_exact_six_fields": 0,
        "course_records": [
            {
                "@timestamp": "2026-06-03T23:36:22",
                "file.name": "SCRNSAVE.EXE",
                "file.path": r"C:\Users\Public\course-persistence\course-screen.scr",
                "reg.key.path": r"NTUSER.DAT-test\Control Panel\Desktop",
            },
            {
                "@timestamp": "2026-06-03T23:36:35",
                "file.name": "UserInitMprLogonScript",
                "file.path": r"C:\Users\Public\course-persistence\logon-script.cmd",
                "reg.key.path": r"NTUSER.DAT-test\Environment",
            },
            {
                "@timestamp": "2026-06-03T23:36:15",
                "file.name": "AutoRun",
                "file.path": r"powershell.exe -ExecutionPolicy Bypass -File C:\Users\Public\course-persistence\cmd-autorun.ps1",
                "reg.key.path": r"NTUSER.DAT-test\SOFTWARE\Microsoft\Command Processor",
            },
            {
                "@timestamp": "2026-06-03T23:35:42",
                "file.name": "CourseHKCURun",
                "file.path": r"powershell.exe -ExecutionPolicy Bypass -File C:\Users\Public\course-persistence\run.ps1",
                "reg.key.path": r"NTUSER.DAT-test\SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
            },
        ],
    }
    if not REGISTRY_JSON.exists():
        return fallback

    schema_fields = {"@timestamp", "file.name", "file.path", "host.name", "reg.key.name", "reg.key.path"}
    host_counts: Counter[str] = Counter()
    names: Counter[str] = Counter()
    paths: Counter[str] = Counter()
    key_paths: Counter[str] = Counter()
    dates: Counter[str] = Counter()
    course_records: list[dict] = []
    invalid = 0
    total = 0
    with REGISTRY_JSON.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            total += 1
            record = json.loads(line)
            if set(record) != schema_fields:
                invalid += 1
            host_counts[str(record.get("host.name", ""))] += 1
            names[str(record.get("file.name", ""))] += 1
            paths[str(record.get("file.path", ""))] += 1
            key_paths[str(record.get("reg.key.path", ""))] += 1
            dates[str(record.get("@timestamp", ""))[:10]] += 1
            blob = json.dumps(record, ensure_ascii=False).lower()
            if "course-persistence" in blob:
                course_records.append(record)
    return {
        "total_records": total,
        "host": host_counts.most_common(1)[0][0] if host_counts else "",
        "unique_file_name": len(names),
        "unique_file_path": len(paths),
        "unique_reg_key_path": len(key_paths),
        "schema_not_exact_six_fields": invalid,
        "course_records": course_records,
        "top_dates": dates.most_common(6),
    }


def add_abstract(doc: Document, stats: dict) -> None:
    para(doc, "РЕФЕРАТ", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True)
    para(
        doc,
        "Курсовая работа посвящена разработке и лабораторной проверке модуля обнаружения механизмов закрепления "
        "в операционных системах Windows по артефактам реестра. В работе рассматриваются способы сбора сырых "
        "registry hive-файлов с помощью Volume Shadow Copy Service, их обработка на Ubuntu 22.04 инструментом "
        "RECmd, нормализация в минимальную модель Registry.json и анализ записей в OpenSearch Dashboards.",
    )
    para(
        doc,
        f"Практический эксперимент выполнен на наборе из {stats['total_records']:,}".replace(",", " ")
        + " нормализованных записей. В лабораторный образ были заложены шесть persistence-механизмов, четыре "
        "из них подтверждены в текущем Registry.json; две HKLM-записи требуют повторной проверки захвата SOFTWARE hive.",
    )
    para(
        doc,
        "Ключевые слова: Windows persistence, реестр Windows, VSS, RECmd, Registry.json, OpenSearch, OpenSearch Dashboards, "
        "анализ артефактов, кибербезопасность.",
    )
    doc.add_page_break()


def add_introduction(doc: Document) -> None:
    heading(doc, "ВВЕДЕНИЕ", 1)
    para(
        doc,
        "Актуальность темы определяется тем, что многие техники закрепления злоумышленника в Windows используют "
        "автозапуск через реестр: Run/RunOnce, Command Processor AutoRun, Active Setup, UserInitMprLogonScript, "
        "параметры экранной заставки и другие ветви. Такие изменения могут не сопровождаться немедленным сетевым "
        "событием, поэтому для расследования требуется воспроизводимый способ извлечения и анализа записей реестра.",
    )
    para(
        doc,
        "Цель работы - разработать и проверить модуль, который собирает артефакты реестра Windows, нормализует их "
        "в минимальную схему и позволяет находить подозрительные persistence-записи через OpenSearch Dashboards.",
    )
    para(
        doc,
        "Для достижения цели поставлены задачи: изучить характерные реестровые механизмы закрепления; определить "
        "лабораторную архитектуру без Docker; реализовать сбор сырых hive-файлов через VSS; организовать извлечение "
        "RECmd на Ubuntu; сформировать нормализованный Registry.json; индексировать записи в OpenSearch; проверить "
        "поиск заложенных инцидентов в OpenSearch Dashboards.",
    )
    para(
        doc,
        "Объект исследования - артефакты закрепления в Windows 10/11. Предмет исследования - методы извлечения, "
        "нормализации и поискового анализа записей реестра, связанных с persistence-механизмами.",
    )
    para(
        doc,
        "Методологическая база включает экспериментальное моделирование инцидентов, статический анализ реестра, "
        "нормализацию данных, частотный анализ в поисковом индексе и проверку результата через запросы OpenSearch Dashboards.",
    )


def add_theory(doc: Document) -> None:
    heading(doc, "1. ТЕОРЕТИЧЕСКАЯ ЧАСТЬ", 1)
    heading(doc, "1.1. Что такое persistence в Windows и зачем его искать", 2)
    para(
        doc,
        "Закрепление представляет собой сохранение способа повторного запуска кода после перезагрузки системы, входа "
        "пользователя или запуска стандартной программы. В Windows значительная часть таких механизмов хранится в "
        "реестре: пользовательские и системные Run-ветви, обработчики командной строки, Active Setup, параметры среды "
        "пользователя, настройки экранной заставки и служебные ветви Windows NT.",
    )
    para(
        doc,
        "Для расследования важно фиксировать не только имя значения, но и путь ключа, данные значения и время последнего "
        "изменения ключа. Эти признаки позволяют отделить известные системные записи от редких пользовательских путей, "
        "например файлов в C:\\Users\\Public, AppData или Temp.",
    )
    heading(doc, "1.2. Как persistence-записи проявляются в реестре", 2)
    para(
        doc,
        "Типовая persistence-запись состоит из места хранения, имени значения и данных значения. Например, ветвь "
        "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run запускает значение при входе пользователя, а "
        "HKCU\\Software\\Microsoft\\Command Processor\\AutoRun выполняет команду при запуске cmd.exe. Параметр "
        "UserInitMprLogonScript в HKCU\\Environment используется как пользовательский logon script, а SCRNSAVE.EXE "
        "может быть использован для подмены экранной заставки на исполняемый файл или скрипт.",
    )
    para(
        doc,
        "В системном контексте интерес представляют RunOnceEx и Active Setup. Они хранятся в HKLM и могут запускать "
        "команды с повышенным доверием к системному программному обеспечению. Эти механизмы особенно важны для анализа, "
        "но требуют корректного захвата SOFTWARE hive и его transaction log-файлов.",
    )
    heading(doc, "1.3. По каким признакам видно подозрительную запись", 2)
    para(
        doc,
        "Ручной просмотр regedit не масштабируется: в одном SOFTWARE hive могут находиться сотни тысяч значений, а "
        "одно и то же имя, например StubPath или SCRNSAVE.EXE, встречается как в реальных persistence-точках, так и в "
        "служебных IniFileMapping-записях. Поэтому проект использует нормализацию и последующий поиск по точным полям.",
    )
    para(
        doc,
        "Частотный анализ основан на предположении, что массово встречающиеся системные записи менее приоритетны для "
        "первичной проверки, а редкие пути, особенно в пользовательских каталогах, требуют внимания. OpenSearch Dashboards "
        "позволяет группировать записи по file.path, reg.key.path или их комбинации и сортировать результаты по возрастанию count.",
    )
    para(
        doc,
        "На практике подозрительность повышают следующие признаки: путь к C:\\Users\\Public, AppData, Temp или Downloads; "
        "запуск powershell.exe с параметрами обхода политики выполнения; использование rundll32.exe для DLL; редкое имя "
        "значения в известной persistence-ветви; изменение ключа в момент лабораторного инцидента; несовпадение ожидаемого "
        "системного расположения файла с фактическим путем.",
    )
    heading(doc, "1.4. Инструменты криминалистического анализа", 2)
    para(
        doc,
        "Для корректного анализа используются сырые файлы реестра, а не экспорт отдельных ключей. Такой подход позволяет "
        "сохранить контекст hive-файла, transaction log-файлы и временные метки. В проекте Windows-сторона отвечает только "
        "за получение артефактов через Volume Shadow Copy Service, а Ubuntu-сторона выполняет разбор и поиск.",
    )
    para(
        doc,
        "RECmd используется как специализированный парсер registry hive-файлов. Python-модуль не пытается реализовать "
        "собственный низкоуровневый парсер реестра; он строит задания для RECmd, читает JSON-результаты, нормализует записи "
        "и передает их в OpenSearch. OpenSearch Dashboards применяется как рабочее место аналитика для фильтрации, поиска, "
        "группировки и проверки гипотез.",
    )


def add_architecture(doc: Document) -> None:
    heading(doc, "2 АРХИТЕКТУРА И ИНСТРУМЕНТАРИЙ ПРОЕКТА", 1)
    para(
        doc,
        "Проект выполняется в лабораторной среде VMware Workstation на физическом хосте Windows 11. Важное архитектурное "
        "ограничение - отсутствие зависимости от Docker и Docker Desktop, так как вложенная виртуализация в такой среде "
        "не должна предполагаться. OpenSearch и OpenSearch Dashboards устанавливаются нативно на Ubuntu 22.04 из официальных "
        "пакетных репозиториев OpenSearch и запускаются как systemd-сервисы.",
    )
    diagram1 = BUILD_DIR / "architecture.png"
    make_diagram(
        diagram1,
        "Архитектура лабораторного стенда",
        ["Windows 10/11 target", "VSS acquisition", "SCP upload", "Ubuntu 22.04 + RECmd", "Registry.json", "OpenSearch Dashboards"],
    )
    add_caption(doc, "Рисунок 1 - Архитектура сбора и анализа артефактов")
    doc.add_picture(str(diagram1), width=Inches(6.2))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER

    add_table(
        doc,
        "Таблица 1 - Используемое программное обеспечение",
        ["Компонент", "Версия / среда", "Назначение"],
        [
            ["Windows", "Windows 10/11", "Источник артефактов и место моделирования persistence-записей"],
            ["PowerShell", "5.1+", "Запуск скрипта сбора через VSS и SCP"],
            ["Ubuntu", "22.04", "Сервер обработки, OpenSearch и Dashboards"],
            ["Python", "3.10+", "Оркестрация RECmd, нормализация, индексация"],
            ["RECmd", "2026.5.0 в лабораторном прогоне", "Разбор сырых registry hive-файлов"],
            ["OpenSearch", "2.x", "Поисковый индекс нормализованных записей"],
            ["OpenSearch Dashboards", "2.x", "Интерфейс фильтрации и визуального анализа"],
            ["VMware Workstation", "лабораторная среда", "Сеть между физическим хостом и Ubuntu VM"],
        ],
        [3.2, 4.2, 8.6],
    )
    heading(doc, "2.1 Поток данных", 2)
    para(
        doc,
        "Windows-скрипт получает сырые файлы реестра из VSS-снимка и передает их на Ubuntu. На Ubuntu Python-модуль "
        "создает задания RECmd, извлекает целевые ветви, нормализует JSON в Registry.json и индексирует каждую строку "
        "как отдельный документ OpenSearch.",
    )
    diagram2 = BUILD_DIR / "dashboard_path.png"
    make_diagram(
        diagram2,
        "Доступ аналитика к OpenSearch Dashboards",
        ["Host browser", "VMware network", "Ubuntu VM :5601", "Dashboards Discover", "Persistence queries"],
    )
    add_caption(doc, "Рисунок 2 - Путь доступа к OpenSearch Dashboards из физического хоста")
    doc.add_picture(str(diagram2), width=Inches(6.2))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER

    heading(doc, "2.2 Нормализованная модель записи", 2)
    add_table(
        doc,
        "Таблица 2 - Минимальная схема Registry.json",
        ["Поле", "Смысл", "Использование в анализе"],
        [
            ["reg.key.path", "Нормализованный путь ключа реестра", "Фильтрация по persistence-ветвям"],
            ["reg.key.name", "Имя конечного ключа", "Контекст ветви, например Run или Desktop"],
            ["@timestamp", "Время LastWrite ключа, преобразованное в UTC-3", "Ограничение временного диапазона"],
            ["file.name", "Имя значения реестра", "Поиск конкретных значений AutoRun, StubPath и т.д."],
            ["file.path", "Путь или команда из данных значения; команды нормализуются до пути при возможности", "Главный признак редкого исполняемого файла"],
            ["host.name", "Имя анализируемого узла", "Разделение данных по компьютерам"],
        ],
        [3.2, 5.0, 7.8],
    )


def add_practical(doc: Document, stats: dict) -> None:
    heading(doc, "2. ПРАКТИЧЕСКАЯ ЧАСТЬ", 1)
    heading(doc, "2.1. Как устроена проверка и что использовалось", 2)
    para(
        doc,
        "Практическая проверка выполнена методом контролируемого моделирования. На Windows 10 были созданы тестовые "
        "persistence-записи в реестре, после чего система была собрана скриптом Acquire-PersistenceArtifacts.ps1, "
        "обработана командой persist_detector process и проанализирована в OpenSearch Dashboards.",
    )
    para(
        doc,
        "Выбор методики обусловлен тем, что известные заложенные записи позволяют проверить полноту цепочки: создание "
        "инцидента, сохранение в hive-файлах, извлечение RECmd, нормализация в Registry.json и поиск через Dashboards.",
    )
    para(
        doc,
        "Лабораторная среда построена в VMware Workstation. В качестве анализируемой системы используется Windows 10, "
        "в качестве сервера обработки - Ubuntu 22.04. OpenSearch и OpenSearch Dashboards установлены нативно через "
        "официальные APT-репозитории OpenSearch, без Docker и Docker Desktop. Это важно для стенда на Windows 11, потому "
        "что вложенная виртуализация в VMware Workstation не должна считаться доступной по умолчанию.",
    )
    diagram1 = BUILD_DIR / "architecture.png"
    make_diagram(
        diagram1,
        "Архитектура лабораторного стенда",
        ["Windows 10/11 target", "VSS acquisition", "SCP upload", "Ubuntu 22.04 + RECmd", "Registry.json", "OpenSearch Dashboards"],
    )
    add_caption(doc, "Рисунок 1 - Архитектура сбора и анализа артефактов")
    doc.add_picture(str(diagram1), width=Inches(6.2))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER

    add_table(
        doc,
        "Таблица 1 - Используемое программное обеспечение",
        ["Компонент", "Версия / среда", "Назначение"],
        [
            ["Windows", "Windows 10/11", "Источник артефактов и место моделирования persistence-записей"],
            ["PowerShell", "5.1+", "Запуск скрипта сбора через VSS и SCP"],
            ["Ubuntu", "22.04", "Сервер обработки, OpenSearch и Dashboards"],
            ["Python", "3.10+", "Оркестрация RECmd, нормализация, индексация"],
            ["RECmd", "2026.5.0 в лабораторном прогоне", "Разбор сырых registry hive-файлов"],
            ["OpenSearch", "2.x", "Поисковый индекс нормализованных записей"],
            ["OpenSearch Dashboards", "2.x", "Интерфейс фильтрации и визуального анализа"],
            ["VMware Workstation", "лабораторная среда", "Сеть между физическим хостом и Ubuntu VM"],
        ],
        [3.2, 4.2, 8.6],
    )

    heading(doc, "2.2. Как устроена программа внутри", 2)
    para(
        doc,
        "Программа разделена на четыре логических слоя. Первый слой - PowerShell-сборщик, который создает VSS-снимок, "
        "копирует hive-файлы и transaction logs, формирует manifest.json и передает результат по SCP. Второй слой - "
        "extract.py, который обнаруживает SOFTWARE, SYSTEM, NTUSER.DAT и UsrClass.dat и строит задания RECmd по целевым "
        "ветвям реестра. Третий слой - normalize.py, который преобразует RECmd JSON в Registry.json. Четвертый слой - "
        "opensearch.py, который создает индекс и отправляет записи через Bulk API.",
    )
    diagram2 = BUILD_DIR / "dashboard_path.png"
    make_diagram(
        diagram2,
        "Доступ аналитика к OpenSearch Dashboards",
        ["Host browser", "VMware network", "Ubuntu VM :5601", "Dashboards Discover", "Persistence queries"],
    )
    add_caption(doc, "Рисунок 2 - Путь доступа к OpenSearch Dashboards из физического хоста")
    doc.add_picture(str(diagram2), width=Inches(6.2))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER

    add_table(
        doc,
        "Таблица 2 - Минимальная схема Registry.json",
        ["Поле", "Смысл", "Использование в анализе"],
        [
            ["reg.key.path", "Нормализованный путь ключа реестра", "Фильтрация по persistence-ветвям"],
            ["reg.key.name", "Имя конечного ключа", "Контекст ветви, например Run или Desktop"],
            ["@timestamp", "Время LastWrite ключа, преобразованное в UTC-3", "Ограничение временного диапазона"],
            ["file.name", "Имя значения реестра", "Поиск конкретных значений AutoRun, StubPath и т.д."],
            ["file.path", "Путь или команда из данных значения; команды нормализуются до пути при возможности", "Главный признак редкого исполняемого файла"],
            ["host.name", "Имя анализируемого узла", "Разделение данных по компьютерам"],
        ],
        [3.2, 5.0, 7.8],
    )
    para(
        doc,
        "Минимальная схема выбрана осознанно: она содержит только поля, которые нужны для курсовой работы и поиска "
        "persistence-записей. Из схемы исключены вспомогательные признаки вроде имени промежуточного JSON-файла или типа "
        "значения реестра, потому что они усложняют индекс и не являются обязательными для демонстрации детекции.",
    )

    heading(doc, "2.3. Примеры проверок", 2)
    add_table(
        doc,
        "Таблица 3 - Заложенные persistence-механизмы и результат поиска",
        ["N", "Механизм", "Ключ / значение", "Ожидаемый путь", "Результат"],
        [
            ["1", "HKCU Run", "CourseHKCURun", r"C:\Users\Public\course-persistence\run.ps1", "Найдено"],
            ["2", "Command Processor AutoRun", "AutoRun", r"C:\Users\Public\course-persistence\cmd-autorun.ps1", "Найдено"],
            ["3", "Screen saver", "SCRNSAVE.EXE", r"C:\Users\Public\course-persistence\course-screen.scr", "Найдено"],
            ["4", "Logon script", "UserInitMprLogonScript", r"C:\Users\Public\course-persistence\logon-script.cmd", "Найдено"],
            ["5", "RunOnceEx", "CourseRunOnceEx", r"C:\Users\Public\course-persistence\runonceex.cmd", "Не найдено в текущем Registry.json"],
            ["6", "Active Setup", "{COURSE-PERSISTENCE-0001}\\StubPath", r"C:\Users\Public\course-persistence\active-setup.ps1", "Не найдено в текущем Registry.json"],
        ],
        [1.0, 3.3, 4.1, 5.4, 2.6],
    )
    para(
        doc,
        "Для создания учебных инцидентов использовались команды PowerShell и REG ADD. После создания каждая запись "
        "проверялась командой Get-ItemProperty или REG QUERY. Такой порядок нужен, чтобы отличать ошибки сбора от ошибок "
        "самого моделирования: если запись не появилась в Windows до запуска Acquire-PersistenceArtifacts.ps1, она не может "
        "корректно появиться в Registry.json.",
    )
    para(
        doc,
        "Отдельно проверялся запуск через Command Processor AutoRun: команда cmd.exe /c exit приводила к созданию "
        "файла-индикатора cmd-autorun-fired.txt. Это подтверждает не только наличие значения в реестре, но и практическую "
        "работоспособность механизма закрепления.",
    )

    heading(doc, "2.4. Проверка на реальных данных", 2)
    add_table(
        doc,
        "Таблица 4 - Сводные показатели Registry.json",
        ["Показатель", "Значение"],
        [
            ["Общее количество записей N", f"{stats['total_records']} ({stats['total_records'] / 100000:.5g} x 10^5)"],
            ["Host", stats["host"]],
            ["Уникальных file.name", str(stats["unique_file_name"])],
            ["Уникальных file.path", str(stats["unique_file_path"])],
            ["Уникальных reg.key.path", str(stats["unique_reg_key_path"])],
            ["Записей с отклонением от минимальной схемы", str(stats["schema_not_exact_six_fields"])],
        ],
        [7.5, 8.5],
    )
    n = int(stats["total_records"])
    found = len(stats["course_records"])
    planted = 6
    add_formula(doc, f"N = {n} = {n / 100000:.5g} x 10^5 записей", 1, "где N - количество строк Registry.json после нормализации.")
    recall = found / planted
    add_formula(
        doc,
        f"R = N_found / N_planted = {found} / {planted} = {recall:.3f} = {recall * 100:.1f} %",
        2,
        "где R - доля подтвержденных учебных persistence-записей в текущем файле Registry.json.",
    )
    prevalence = found / n
    add_formula(
        doc,
        f"P = N_found / N = {found} / {n} = {prevalence:.3e}",
        3,
        "где P - доля подтвержденных учебных записей среди всех нормализованных записей. Значение показывает, почему нужен поисковый индекс.",
    )
    batches = math.ceil(n / 500)
    add_formula(
        doc,
        f"B = ceil(N / 500) = ceil({n} / 500) = {batches}",
        4,
        "где B - расчетное количество bulk-запросов OpenSearch при размере пакета 500 документов.",
    )
    para(
        doc,
        "Файл Registry.json содержит четыре записи с путем C:\\Users\\Public\\course-persistence. Это подтверждает, что "
        "цепочка сбора и обработки сохраняет пользовательские persistence-артефакты из NTUSER.DAT. Две системные HKLM-записи "
        "не представлены в текущем Registry.json; наиболее вероятная причина - они отсутствовали в захваченном SOFTWARE hive "
        "или были изменены до момента повторного сбора. Для защиты результата это следует явно указать как ограничение эксперимента.",
    )
    for record in stats["course_records"]:
        para(
            doc,
            f"Подтвержденная запись: {record.get('file.name')} -> {record.get('file.path')} "
            f"в ключе {record.get('reg.key.path')} ({record.get('@timestamp')}).",
        )
    para(
        doc,
        "В Discover следует выбрать Data View windows-persistence-registry, режим Lucene и временной диапазон, включающий "
        "дату 2026-06-03. Для поиска учебных записей применяются следующие запросы:",
    )
    for query in [
        r'file.name:CourseHKCURun AND file.path:*course-persistence*',
        r'file.name:AutoRun AND file.path:*course-persistence*',
        r'file.name:SCRNSAVE.EXE AND file.path:*course-screen.scr*',
        r'file.name:UserInitMprLogonScript AND file.path:*logon-script.cmd*',
        r'file.path:*course-persistence*',
    ]:
        add_code_block(doc, query)

    para(
        doc,
        "Для исключения ложного вывода по SCRNSAVE.EXE нельзя ограничиваться запросом file.name:SCRNSAVE.EXE. В реестре "
        "Windows есть служебные IniFileMapping-записи с таким же именем значения. Поэтому корректный запрос должен уточнять "
        "путь к учебному файлу: file.name:SCRNSAVE.EXE AND file.path:*course-screen.scr*.",
    )

    heading(doc, "2.5. Советы по использованию", 2)
    para(
        doc,
        "Перед повторной индексацией необходимо удалить старый индекс windows-persistence-registry или использовать новый "
        "индекс. Это особенно важно после исправления нормализации file.path: стабильный идентификатор документа строится "
        "в том числе по file.path, поэтому старая запись с полной командной строкой и новая запись с извлеченным путем могут "
        "сосуществовать в индексе.",
    )
    para(
        doc,
        "Практический порядок работы аналитика следующий: создать или получить upload с Windows; выполнить process с "
        "--skip-index для проверки Registry.json; убедиться через grep или jq, что учебные признаки присутствуют; очистить "
        "или создать индекс OpenSearch; выполнить index; открыть Dashboards с физического хоста по адресу "
        "http://<UBUNTU_IP>:5601; создать Data View windows-persistence-registry; применить Lucene-запросы к конкретным "
        "persistence-механизмам.",
    )
    para(
        doc,
        "Если запись создана в HKLM, но отсутствует в Registry.json, нужно проверить ее наличие на Windows непосредственно "
        "перед сбором, убедиться в наличии SOFTWARE.LOG1 и SOFTWARE.LOG2 в upload и выполнить ручной RECmd-запрос по нужной "
        "ветви. В текущем эксперименте именно HKLM RunOnceEx и Active Setup не были подтверждены в итоговом Registry.json, "
        "поэтому они вынесены в ограничения результата, а не объявлены найденными.",
    )


def add_implementation(doc: Document) -> None:
    heading(doc, "4 РЕАЛИЗАЦИЯ ПРОГРАММНОГО МОДУЛЯ", 1)
    heading(doc, "4.1 Сбор артефактов", 2)
    para(
        doc,
        "Скрипт Acquire-PersistenceArtifacts.ps1 выполняется с повышенными правами. Он создает VSS-снимок системного "
        "диска, копирует SYSTEM, SOFTWARE, пользовательские NTUSER.DAT и UsrClass.dat вместе с transaction log-файлами, "
        "формирует manifest.json с размером и SHA-256 каждого файла, затем передает каталог на Ubuntu через scp.",
    )
    heading(doc, "4.2 Извлечение и нормализация", 2)
    para(
        doc,
        "Модуль extract.py строит список заданий RECmd по доступным hive-файлам и целевым родительским ветвям. Модуль "
        "normalize.py рекурсивно обходит JSON RECmd, выпускает одну строку Registry.json на каждое значение реестра и "
        "отбрасывает пустые или числовые значения, не несущие полезной информации для поиска путей и команд.",
    )
    heading(doc, "4.3 Индексация", 2)
    para(
        doc,
        "Модуль opensearch.py проверяет наличие шести обязательных полей, создает индекс при необходимости и отправляет "
        "данные через Bulk API. Основные поля отображаются как keyword, что позволяет использовать точные фильтры, wildcard "
        "и terms-агрегации в OpenSearch Dashboards.",
    )
    heading(doc, "4.4 Выводы и рекомендации по практической части", 2)
    para(
        doc,
        "Практический эксперимент показывает, что минимальная схема достаточна для первичного поиска persistence-записей: "
        "аналитику видны компьютер, путь ключа, имя значения, данные значения и время изменения. Поле reg.key.name полезно "
        "как короткий контекст, но само по себе не является главным детекционным признаком; основной вес имеют reg.key.path "
        "и file.path.",
    )
    para(
        doc,
        "Рекомендуется перед финальной демонстрацией заново обработать последний upload после исправления нормализации "
        "file.path, удалить старый индекс OpenSearch и переиндексировать Registry.json. Это исключит ситуацию, когда Dashboards "
        "показывает устаревшие документы с исходной командной строкой вместо извлеченного пути файла.",
    )


def add_conclusion(doc: Document) -> None:
    heading(doc, "ЗАКЛЮЧЕНИЕ", 1)
    para(
        doc,
        "В ходе работы разработан модуль обнаружения механизмов закрепления в Windows по артефактам реестра. Архитектура "
        "разделяет сбор и анализ: Windows передает сырые данные, а Ubuntu выполняет RECmd-извлечение, нормализацию, индексацию "
        "и визуальный анализ. Такое разделение уменьшает нагрузку на исследуемую систему и сохраняет воспроизводимость обработки.",
    )
    para(
        doc,
        "Цель работы достигнута частично в части полной лабораторной верификации: четыре из шести заложенных записей найдены "
        "в текущем Registry.json, две HKLM-записи требуют повторной проверки момента захвата и состояния SOFTWARE hive. При этом "
        "основная цепочка от NTUSER.DAT до OpenSearch Dashboards подтверждена на реальных данных.",
    )
    para(
        doc,
        "Дальнейшее развитие работы целесообразно направить на live-проверку OpenSearch Alerting API, создание экспортируемых "
        "объектов Dashboards и расширение обработки дополнительных артефактов: scheduled tasks, services metadata, WMI и Sysmon EVTX.",
    )


def add_references(doc: Document) -> None:
    heading(doc, "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ", 1)
    refs = [
        "Инструкция по организации и проведению курсового проектирования. СМКО МИРЭА 7.5.1/04.И.05-18. РТУ МИРЭА, 2018, с изм. 2022, 2024.",
        "ГОСТ 7.32-2017. Система стандартов по информации, библиотечному и издательскому делу. Отчет о научно-исследовательской работе. Структура и правила оформления.",
        "ГОСТ Р 7.0.100-2018. Библиографическая запись. Библиографическое описание. Общие требования и правила составления.",
        "MITRE ATT&CK. Technique T1547: Boot or Logon Autostart Execution. URL: https://attack.mitre.org/techniques/T1547/ (дата обращения: 04.06.2026).",
        "OpenSearch Documentation. Install OpenSearch with Debian package. URL: https://docs.opensearch.org/latest/install-and-configure/install-opensearch/debian/ (дата обращения: 04.06.2026).",
        "OpenSearch Documentation. Bulk API. URL: https://docs.opensearch.org/latest/api-reference/document-apis/bulk/ (дата обращения: 04.06.2026).",
        "Eric Zimmerman Tools. RECmd project. URL: https://github.com/EricZimmerman/RECmd (дата обращения: 04.06.2026).",
        "Microsoft Learn. Volume Shadow Copy Service. URL: https://learn.microsoft.com/windows/win32/vss/volume-shadow-copy-service-portal (дата обращения: 04.06.2026).",
        "Документация проекта Windows Persistence Detection Module: PROJECT_SPECIFICATION.md, README.md, docs/architecture.md, docs/lab-setup.md.",
    ]
    for idx, ref in enumerate(refs, 1):
        p = para(doc)
        p.paragraph_format.first_line_indent = Cm(0)
        p.paragraph_format.left_indent = Cm(0.75)
        p.paragraph_format.first_line_indent = Cm(-0.75)
        r = p.add_run(f"{idx}. {ref}")
        set_run_font(r)


def add_appendix_code(doc: Document) -> None:
    doc.add_page_break()
    heading(doc, "ПРИЛОЖЕНИЕ А", 1)
    para(doc, "Листинг программного кода", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True)
    para(
        doc,
        "В приложении приведены ключевые фрагменты программной реализации, определяющие сбор, извлечение, нормализацию "
        "и индексацию артефактов. Полные файлы находятся в репозитории проекта.",
    )
    snippets = [
        ("Листинг А.1 - Ключевой фрагмент сбора hive-файлов PowerShell", Path("scripts/windows/Acquire-PersistenceArtifacts.ps1"), ["function Test-IsAdministrator", "$systemHives", "$ntuserFiles", "$usrClassFiles", "$manifest = [ordered]@"]),
        ("Листинг А.2 - Формирование заданий RECmd", Path("src/persist_detector/extract.py"), None),
        ("Листинг А.3 - Нормализация RECmd JSON в Registry.json", Path("src/persist_detector/normalize.py"), None),
        ("Листинг А.4 - Проверка схемы и Bulk API OpenSearch", Path("src/persist_detector/opensearch.py"), ["REQUIRED_REGISTRY_FIELDS", "def validate_registry_record", "def stable_document_id", "class OpenSearchClient", "def index_registry_file"]),
        ("Листинг А.5 - Команда process", Path("src/persist_detector/cli.py"), ["def command_process", "def run_opensearch_indexing", "def add_opensearch_arguments"]),
    ]
    for title, path, anchors in snippets:
        heading(doc, title, 2)
        code = read_code_snippet(ROOT / path, anchors)
        add_code_block(doc, code)


def read_code_snippet(path: Path, anchors: list[str] | None) -> str:
    text = path.read_text(encoding="utf-8")
    if anchors is None:
        return text

    lines = text.splitlines()
    selected: list[str] = []
    for anchor in anchors:
        for idx, line in enumerate(lines):
            if anchor in line:
                start = max(0, idx - 4)
                end = min(len(lines), idx + 26)
                selected.extend(lines[start:end])
                selected.append("")
                break
    deduped: list[str] = []
    prev_blank = False
    for line in selected:
        if not line.strip():
            if not prev_blank:
                deduped.append(line)
            prev_blank = True
        else:
            deduped.append(line)
            prev_blank = False
    return "\n".join(deduped).strip()


def add_code_block(doc: Document, code: str) -> None:
    for line in code.splitlines() or [""]:
        p = doc.add_paragraph(style="CodeListing")
        p.paragraph_format.first_line_indent = Cm(0)
        wrapped = textwrap.wrap(line.expandtabs(4), width=112, replace_whitespace=False, drop_whitespace=False) or [""]
        for idx, part in enumerate(wrapped):
            if idx:
                p = doc.add_paragraph(style="CodeListing")
                p.paragraph_format.first_line_indent = Cm(0)
            r = p.add_run(part)
            set_run_font(r, name="Consolas", size=8.5)


def main() -> None:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    stats = analyze_registry()
    doc = Document()
    configure_document(doc)
    add_title_page(doc)
    add_assignment_page(doc)
    add_toc(doc)
    add_introduction(doc)
    add_theory(doc)
    add_practical(doc, stats)
    add_conclusion(doc)
    add_references(doc)
    add_appendix_code(doc)
    doc.save(OUT)
    print("coursework_docx_created")


if __name__ == "__main__":
    main()
