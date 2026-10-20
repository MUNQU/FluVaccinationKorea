"""Read influenza data from the KDCA weekly sentinel bulletins.

Input: `data/raw/kdca_sentinel/manifest.csv` and the files in `bulletins/`.
Each file is turned into plain text once (`text/`, cached): PDF with
`pdftotext -layout`, HWP with `hwp5html` (tables become lines of cells).

Output: `data/processed/kdca_sentinel_bulletins.csv` (common format). Every
row keeps the bulletin it comes from in `category` as `reported_in=YYYY-WW`,
because the same week appears in several bulletins and values are revised.

Indicators:
- `ili_per_1000`: ILI per 1,000 outpatients, national and by age group.
- `ili_epidemic_threshold`: epidemic threshold of the season.
- `hosp_flu_inpatients`: influenza inpatients reported by the hospital-level
  acute respiratory infection (ARI) sentinel network.
- `sari_new_patients`, `sari_flu_positive`: severe acute respiratory
  infection (SARI) sentinel, new patients and influenza-positive patients.
- `flu_specimens_tested`, `flu_specimens_positive`, `flu_positivity`:
  clinic-level influenza virus surveillance, as stated in the text.

Usage: .venv/bin/python -E -s scripts/kdca_sentinel_bulletins.py
"""

import csv
import html
import json
import re
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from common import RAW, REGIONS, epi_week, epi_week_start, mmwr_week_start, write_tidy
from kdca_sentinel_process import SOURCE

KS = RAW / "kdca_sentinel"
TEXT = KS / "text"

NUM = r"\d+(?:\.\d+)?"
# A week label: "36주", "제5주", "’08.1", "2010.1", "‘16.1", "‘18 1 주".
WEEK_TOKEN = re.compile(
    r"^(?:[’‘'`]\s?\d{2}[.\s]\s*|\d{4}\.\s*|제)?(\d{1,2})\s*주?(?:차)?$"
)


# --------------------------------------------------------------------------
# Text extraction
# --------------------------------------------------------------------------


def hwp_to_text(path: Path) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            [str(Path(sys.executable).parent / "hwp5html"), "--output", tmp, str(path)],
            check=True,
            capture_output=True,
        )
        page = (Path(tmp) / "index.xhtml").read_text(encoding="utf-8")
    page = re.sub(r"&#13;|\r", " ", page)
    lines = []
    for block in re.split(r"(?=<table)|(?<=</table>)", page):
        if block.startswith("<table"):
            for row in re.findall(r"<tr.*?</tr>", block, re.S):
                cells = re.findall(r"<td.*?</td>", row, re.S)
                text = [
                    re.sub(
                        r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))
                    ).strip()
                    for c in cells
                ]
                lines.append("   ".join(t for t in text))
        else:
            for para in re.findall(r"<p.*?</p>", block, re.S):
                lines.append(
                    re.sub(
                        r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", para))
                    ).strip()
                )
    return "\n".join(lines)


def to_text(path: Path) -> str:
    cache = TEXT / (path.name + ".txt")
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        result = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"], capture_output=True
        )
        text = result.stdout.decode("utf-8", errors="replace")
    elif suffix in (".hwp",):
        text = hwp_to_text(path)
    else:
        text = ""
    TEXT.mkdir(parents=True, exist_ok=True)
    cache.write_text(text, encoding="utf-8")
    return text


# --------------------------------------------------------------------------
# Report week and week-to-year assignment
# --------------------------------------------------------------------------


def report_week(title: str) -> tuple[int, int] | None:
    year = re.search(r"(20\d{2})\s*년", title)
    week = re.search(r"(?:제\s*)?(\d{1,2})\s*주", title)
    if not year or not week:
        return None
    return int(year.group(1)), int(week.group(1))


def week_year(week: int, report: tuple[int, int]) -> int:
    """Year of a week listed in a bulletin: weeks after the report week are
    from the year before."""
    return report[0] if week <= report[1] else report[0] - 1


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------

AGE_LABEL = re.compile(r"(전체|\d+\s*세?\s*이상|\d+\s*[-~]\s*\d+\s*세?|\d+\s*세|0)")


def norm_age(label: str) -> str:
    label = re.sub(r"\s", "", label).replace("~", "-")
    if label == "전체":
        return "all"
    if "이상" in label:
        return label.replace("세이상", "").replace("이상", "") + "+"
    return label.replace("세", "")


def numbers(text: str) -> list[float]:
    return [
        float(x.replace(",", ""))
        for x in re.findall(r"(?<![\d.])\d[\d,]*(?:\.\d+)?(?![\d.])", text)
    ]


def split_cells(line: str) -> list[str]:
    return [c for c in re.split(r"\s{2,}|\t", line.strip()) if c]


def ili_context(lines: list[str], i: int) -> bool:
    """True if the nearest heading above line i is about influenza ILI."""
    for j in range(i, max(-1, i - 40), -1):
        left = lines[j][:90]
        if re.search(
            r"수족구|결막염|중증급성|SARI|입원|병원체|바이러스\s*(분리|검출)", left
        ):
            return False
        if re.search(r"인플루엔자\s*의사환자|인플루엔자의사환자|ILI", left):
            return True
    return False


def week_header(line: str) -> list[int] | None:
    """Week numbers of a header such as '주(Week) 48 49 ... 5' or
    '구분 48주 49주 ...'."""
    m = re.match(r"\s*(주\s*\(Week\)|구\s*분)\s+(.*)", line)
    if not m:
        return None
    rest = m.group(2)
    if "주" not in rest and "Week" not in m.group(1):
        return None
    tokens = re.findall(
        r"[’‘'`]\s?\d{2}\s*[.\s]\s*\d{1,2}\s*주?|\d{4}\.\s*\d{1,2}|\d{1,2}\s*주|\d{1,2}",
        rest,
    )
    weeks = []
    for t in tokens:
        w = WEEK_TOKEN.match(t.strip())
        if not w:
            return None
        weeks.append(int(w.group(1)))
    return weeks if len(weeks) >= 3 and all(1 <= w <= 53 for w in weeks) else None


def tables_weeks_as_columns(lines: list[str]):
    """Yield (age_group, week, value, line_no) from tables with weeks as columns."""
    for i, line in enumerate(lines):
        weeks = week_header(line)
        if not weeks or not ili_context(lines, i):
            continue
        for k in range(i + 1, min(len(lines), i + 30)):
            row = lines[k].strip()
            if not row:
                continue
            if week_header(row) or row.startswith(("주 ", "*", "※", "<", "그림", "표")):
                if k > i + 2:
                    break
                continue
            labelled = row_label(row)
            if not labelled:
                continue
            label, rest = labelled
            values = numbers(rest)[: len(weeks)]
            if len(values) == len(weeks):
                for w, v in zip(weeks, values):
                    yield label, w, v, i


def row_label(row: str) -> tuple[str, str] | None:
    """(age group, rest of the row) of an ILI table row, or None."""
    m = re.match(
        r"(발생\s*분율|의사환자\s*분율|의사환자분율)[^\d]*?(?:\(/\s*1,000\))?\s+(.*)",
        row,
    )
    if m:
        label, rest = "all", m.group(2)
    else:
        m = re.match(r"(전체|\d+\s*세\s*이상|\d+\s*-\s*\d+\s*세|\d+\s*세)\s+(.*)", row)
        if not m:
            return None
        label, rest = norm_age(m.group(1)), m.group(2)
    # Unit marks such as "(/1,000)" can follow the row label.
    return label, re.sub(r"\(?/\s*1,000\s*\)?|1,000\s*명당", " ", rest)


def tables_weeks_as_rows(lines: list[str]):
    """Yield (age_group, week, value, line_no) from tables with age groups as
    columns and one row per week."""
    for i, line in enumerate(lines):
        m = re.match(r"\s*구\s*분\s+(전체.*)", line)
        if (
            not m
            or "50-64" not in line
            or "65" not in line
            or not ili_context(lines, i)
        ):
            continue
        header = m.group(1)
        header = header[: header.find("65") + 2] + " 이상"
        ages = [norm_age(a) for a in AGE_LABEL.findall(header)]
        ages = [a for a in ages if a]
        for k in range(i + 1, min(len(lines), i + 60)):
            row = lines[k].strip()
            if not row:
                continue
            w = re.match(
                r"(?:[’‘'`]\s?\d{2}[.\s]\s*|\d{4}\.\s*|제)?(\d{1,2})\s*주(?:차)?\s+(.*)",
                row,
            )
            if not w:
                if k > i + 3 and not re.match(r"(누계|합계|계)\b", row):
                    break
                continue
            values = numbers(w.group(2))[: len(ages)]
            if len(values) == len(ages):
                for age, v in zip(ages, values):
                    yield age, int(w.group(1)), v, i


# --------------------------------------------------------------------------
# Sentences
# --------------------------------------------------------------------------

THRESHOLD_SEASON = re.compile(
    r"(\d{4})\s*-\s*(\d{4})\s*절기\s*(?:인플루엔자\s*)?유행\s*기준(.{0,90})"
)
THRESHOLD_OLD = re.compile(
    r"유행(?:판단)?기준\s*[(:]?\s*(?:전국\s*)?(" + NUM + r")\s*/\s*1,000"
)


def thresholds(text: str, report: tuple[int, int]):
    flat = re.sub(r"\s+", " ", text)
    for m in THRESHOLD_SEASON.finditer(flat):
        tail = re.sub(r"1,000\s*명?당?|\(/\s*1,000\)|\d\)", " ", m.group(3))
        value = re.search(r"(" + NUM + r")\s*명", tail)
        if value and int(m.group(2)) == int(m.group(1)) + 1:
            yield f"{m.group(1)}-{m.group(2)}", float(value.group(1))
    for m in THRESHOLD_OLD.finditer(flat):
        season = report[0] if report[1] >= 36 else report[0] - 1
        yield f"{season}-{season + 1}", float(m.group(1))


def hospital(text: str, report: tuple[int, int]):
    """(indicator, week, value) found in sentences about hospital data."""
    flat = re.sub(r"\s+", " ", text)
    for m in re.finditer(
        r"(?:(\d{1,2})\s*주차?\s*)?인플루엔자(?:바이러스)?\s*입원\s*환자는\s*([\d,]+)\s*명",
        flat,
    ):
        yield (
            "hosp_flu_inpatients",
            int(m.group(1) or report[1]),
            int(m.group(2).replace(",", "")),
        )
    # 2026 summary: "병원급 의료기관의 입원환자 수는 115명 ... ※ 최근 4주간
    # 입원환자 추이: (7주) 346명 → ...". The influenza block comes first and
    # holds the ILI sentence just before; the COVID-19 block repeats the form.
    m = re.search(
        r"(?<!상급종합)병원급\s*의료기관의\s*입원환자\s*수는\s*[\d,]+\s*명.{0,80}?※\s*최근\s*\d주간\s*입원환자\s*추이\s*:\s*"
        r"((?:\(\d{1,2}\s*주\)\s*[\d,]+\s*명\s*(?:→\s*)?)+)",
        flat,
    )
    if m and "의사환자" in flat[max(0, m.start() - 400) : m.start()]:
        for week, value in re.findall(
            r"\((\d{1,2})\s*주\)\s*([\d,]+)\s*명", m.group(1)
        ):
            yield "hosp_flu_inpatients", int(week), int(value.replace(",", ""))
    # 2025-2026 layout: "- (인플루엔자) 4주 420명". Section 2.1 is the
    # hospital-level ARI network; section 2.2 repeats the sentence for
    # tertiary hospitals, so only matches under a "2.1" heading count.
    for m in re.finditer(r"\(인플루엔자\)\s*(\d{1,2})\s*주\s*([\d,]+)\s*명", flat):
        sections = re.findall(
            r"(?<![\d.])(\d\.\d(?:\.\d)*)\.?\s+(?:바이러스|입원|급성|병원|세균)",
            flat[: m.start()],
        )
        if sections and sections[-1].startswith("2.1"):
            yield (
                "hosp_flu_inpatients",
                int(m.group(1)),
                int(m.group(2).replace(",", "")),
            )
    yield from sari(flat, report)


def sari(flat: str, report: tuple[int, int]):
    """(indicator, week, value) of the SARI sentinel, from whitespace-flat text."""
    for m in re.finditer(
        r"(?:(\d{1,2})\s*주차?\s*)?중증급성호흡기감염[병증]\s*\(S\s*ARI\)\s*신규\s*환자는\s*([\d,]+)\s*명\s*\(\s*인플루엔자\s*([\d,]+)\s*명",
        flat,
    ):
        week = int(m.group(1) or report[1])
        yield "sari_new_patients", week, int(m.group(2).replace(",", ""))
        yield "sari_flu_positive", week, int(m.group(3).replace(",", ""))
    for m in re.finditer(
        r"(\d{1,2})\s*주\s*신규\s*SARI\s*환자\s*중\s*인플루엔자\s*검사\s*건은\s*([\d,]+)\s*건,?\s*양성은\s*([\d,]+)\s*건",
        flat,
    ):
        yield "sari_flu_positive", int(m.group(1)), int(m.group(3).replace(",", ""))
    # 2022-2023: "3주차 신규 SARI환자는 210명이며, 이 중 인플루엔자 환자는 18명".
    for m in re.finditer(
        r"(\d{1,2})\s*주차?\s*신규\s*SARI\s*환자는\s*([\d,]+)\s*명이며,?\s*"
        r"이\s*중\s*인플루엔자\s*환자는\s*([\d,]+)\s*명",
        flat,
    ):
        week = int(m.group(1))
        yield "sari_new_patients", week, int(m.group(2).replace(",", ""))
        yield "sari_flu_positive", week, int(m.group(3).replace(",", ""))
    # From mid-2023: a 10-week table "구분 1주 2주 ... 신규 SARI 환자 수 390 365 ...".
    # The header can carry a year ("24년 1주"), and from 2025 single characters
    # of a vertical side label fall between the header and the row.
    m = re.search(
        r"구분\s*((?:(?:\d{2}년\s*)?\d{1,2}\s*주\s*)+)(?:[^\d\s]\s+){0,3}"
        r"신규\s*SARI\s*환자\s*수\s*((?:[\d,]+\s*)+)",
        flat,
    )
    if m:
        weeks = [int(w) for w in re.findall(r"(\d{1,2})\s*주", m.group(1))]
        values = [int(v.replace(",", "")) for v in m.group(2).split()]
        if len(weeks) == len(values):
            for week, value in zip(weeks, values):
                yield "sari_new_patients", week, value
    # Same period, sentence form for the report week only.
    m = re.search(
        r"신규\s*중증급성호흡기감염증\s*\(SARI\)\s*입원환자는\s*([\d,]+)\s*명", flat
    )
    if m:
        yield "sari_new_patients", report[1], int(m.group(1).replace(",", ""))


def hospital_table(path: Path, report: tuple[int, int]):
    """(indicator, year, week, value) from the hospital-level ARI table of
    viral inpatients by pathogen (bulletins from about 2023 on). The text
    layout of this table is broken, so pdfplumber reads it from the PDF.

    The table is the first one, on a page about inpatients, with an
    "인플루엔자 바이러스" column. Count rows come before the "누계" row; rows
    without a week label take the week before the next labelled row.
    """
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if "입원환자" not in text or "인플루엔자" not in text:
                continue
            for table in page.extract_tables():
                counts = table_counts(table)
                if counts is None:
                    return  # cells merged by pdfplumber: no reliable value
                if not counts:
                    continue
                labelled = [i for i, (w, _) in enumerate(counts) if w is not None]
                anchor_i = labelled[-1] if labelled else len(counts) - 1
                anchor_w = counts[anchor_i][0] or report[1]
                anchor = epi_week_start(week_year(anchor_w, report), anchor_w)
                for i, (_, value) in enumerate(counts):
                    year, week = epi_week(anchor + timedelta(weeks=i - anchor_i))
                    yield "hosp_flu_inpatients", year, week, value
                return


def table_counts(table: list[list]) -> list[tuple[int | None, int]] | None:
    """(week label, count) of the influenza column; None if cells merged."""
    header = [re.sub(r"\s", "", c or "") for c in table[0]]
    cols = [
        i
        for i, c in enumerate(header)
        if c.startswith("인플루엔자") and "바이러스" in c
    ]
    if not cols:
        return []
    counts = []
    for row in table[1:]:
        label = re.sub(r"\s", "", row[0] or "")
        if label.startswith(("누계", "계", "20", "’", "‘")):
            break
        cell = re.sub(r"[\s,]", "", row[cols[0]] or "")
        if re.fullmatch(r"\d{6,}", cell):
            return None
        if re.fullmatch(r"\d+", cell):
            week = re.fullmatch(r"(?:\d{2}년)?(\d{1,2})주", label)
            counts.append((int(week.group(1)) if week else None, int(cell)))
    return counts


def virus(text: str, report: tuple[int, int]):
    """(indicator, week, value) from sentences on clinic-level virus tests."""
    flat = re.sub(r"\s+", " ", text)
    patterns = [
        # "5주에 의뢰된 286건 중 25건(...)이 확진으로 양성률은 8.7%"
        r"(\d{1,2})\s*주(?:차)?에\s*의뢰된\s*([\d,]+)\s*건\s*중\s*([\d,]+)\s*건",
        # "5주차에 295개의 호흡기 검체에서 양성 146건"
        r"(\d{1,2})\s*주차?에\s*([\d,]+)\s*(?:개의|건의)\s*호흡기\s*검체(?:에서|\s*중)\s*양성\s*([\d,]+)\s*건",
    ]
    for p in patterns:
        for m in re.finditer(p, flat):
            tested = int(m.group(2).replace(",", ""))
            positive = int(m.group(3).replace(",", ""))
            if positive <= tested:
                yield "flu_specimens_tested", int(m.group(1)), tested
                yield "flu_specimens_positive", int(m.group(1)), positive
    for m in re.finditer(
        r"(\d{1,2})\s*주차?에\s*([\d,]+)\s*(?:개의|건의)\s*호흡기\s*검체\s*중\s*양성\s*없음",
        flat,
    ):
        yield "flu_specimens_tested", int(m.group(1)), int(m.group(2).replace(",", ""))
        yield "flu_specimens_positive", int(m.group(1)), 0
    # 2008-2012: "5주에 의뢰된 170건 중 A(신종)형 40주, ... 양성률은 25.9%"
    for m in re.finditer(
        r"(\d{1,2})\s*주(?:차)?에\s*의뢰된\s*([\d,]+)\s*건.{0,150}?양성률은?\s*("
        + NUM
        + r")\s*%",
        flat,
    ):
        yield "flu_specimens_tested", int(m.group(1)), int(m.group(2).replace(",", ""))
        yield "flu_positivity", int(m.group(1)), float(m.group(3))
    trend = re.search(
        r"의원급\s*의료기관[^※]{0,80}인플루엔자\s*바이러스\s*검출률은.{0,120}?※\s*최근\s*\d주간\s*검출률\s*추이\s*:\s*"
        r"((?:\(\d{1,2}\s*주\)\s*" + NUM + r"\s*%\s*(?:→\s*)?)+)",
        flat,
    )
    if trend:
        for week, value in re.findall(
            r"\((\d{1,2})\s*주\)\s*(" + NUM + r")\s*%", trend.group(1)
        ):
            yield "flu_positivity", int(week), float(value)
    else:
        for m in re.finditer(
            r"인플루엔자\s*바이러스\s*(" + NUM + r")\s*%\s*검출", flat
        ):
            yield "flu_positivity", report[1], float(m.group(1))


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------

UNITS = {
    "ili_per_1000": "per_1000",
    "ili_epidemic_threshold": "per_1000",
    "hosp_flu_inpatients": "count",
    "sari_new_patients": "count",
    "sari_flu_positive": "count",
    "flu_specimens_tested": "count",
    "flu_specimens_positive": "count",
    "flu_positivity": "percent",
}


def week_row(indicator, year, week, age, value, report) -> dict:
    start = epi_week_start(year, week)
    season = year if week >= 36 else year - 1
    return {
        "source": SOURCE,
        "indicator": indicator,
        "unit": UNITS[indicator],
        "period_type": "week",
        "date_start": start.isoformat(),
        "date_end": (start + timedelta(days=6)).isoformat(),
        "year": year,
        "week": week,
        "season": f"{season}-{season + 1}",
        "region_code": "00",
        "region_name": REGIONS["00"],
        "age_group": age,
        "sex": "all",
        "category": f"reported_in={report[0]}-{report[1]:02d}",
        "value": value,
    }


def season_row(season, value, report) -> dict:
    first = int(season[:4])
    start = epi_week_start(first, 36)
    end = epi_week_start(first + 1, 36) - timedelta(days=1)
    return {
        "source": SOURCE,
        "indicator": "ili_epidemic_threshold",
        "unit": "per_1000",
        "period_type": "season",
        "date_start": start.isoformat(),
        "date_end": end.isoformat(),
        "year": first,
        "week": None,
        "season": season,
        "region_code": "00",
        "region_name": REGIONS["00"],
        "age_group": "all",
        "sex": "all",
        "category": f"reported_in={report[0]}-{report[1]:02d}",
        "value": value,
    }


def parse(path: Path, title: str) -> list[dict]:
    report = report_week(title)
    if report is None:
        return []
    text = to_text(path)
    lines = text.splitlines()
    rows = []
    seen = set()
    for gen in (tables_weeks_as_columns(lines), tables_weeks_as_rows(lines)):
        for age, week, value, _ in gen:
            year = week_year(week, report)
            key = (age, year, week)
            if key in seen:
                continue
            seen.add(key)
            rows.append(week_row("ili_per_1000", year, week, age, value, report))
    for season, value in thresholds(text, report):
        rows.append(season_row(season, value, report))
    found = [*hospital(text, report), *virus(text, report)]
    for indicator, week, value in found:
        if 1 <= week <= 53 and (indicator, week) not in seen:
            seen.add((indicator, week))
            rows.append(
                week_row(indicator, week_year(week, report), week, "all", value, report)
            )
    if path.suffix.lower() == ".pdf" and not any(
        f[0] == "hosp_flu_inpatients" for f in found
    ):
        for indicator, year, week, value in cached_hospital_table(path, report):
            rows.append(week_row(indicator, year, week, "all", value, report))
    return rows


def cached_hospital_table(path: Path, report: tuple[int, int]) -> list:
    cache = TEXT / (path.name + ".hosp.json")
    if not cache.exists():
        found = list(hospital_table(path, report)) if "입원" in to_text(path) else []
        cache.write_text(json.dumps(found), encoding="utf-8")
    return json.loads(cache.read_text(encoding="utf-8"))


PRINTED_WEEK = re.compile(
    r"(20\d{2})\s*년\s*(?:도\s*)?(?:제\s*)?(\d{1,2})\s*주(?:차)?\s*\(\s*"
    r"(?:(20\d{2})\s*\.\s*)?(\d{1,2})\s*\.\s*(\d{1,2})\s*\.?\s*[~∼～]\s*"
    r"(?:(20\d{2})\s*\.\s*)?(\d{1,2})\s*\.\s*(\d{1,2})"
)


def printed_weeks(text: str):
    """(year, week, first day) of week labels printed with a 7-day date range,
    such as "2025년 5주(2025. 1. 26. ~ 2025. 2. 1.)"."""
    for m in PRINTED_WEEK.finditer(re.sub(r"\s+", " ", text)):
        year, week = int(m[1]), int(m[2])
        start_year = (
            int(m[3]) if m[3] else (year - 1 if int(m[4]) == 12 and week == 1 else year)
        )
        try:
            start = date(start_year, int(m[4]), int(m[5]))
            end = date(int(m[6]) if m[6] else start_year, int(m[7]), int(m[8]))
        except ValueError:
            continue
        if end < start:
            end = date(end.year + 1, end.month, end.day)
        if (end - start).days == 6:
            yield year, week, start


def check_week_rule(texts: list[str]) -> None:
    """Print how many printed week dates follow the KDCA and the MMWR rule."""
    weeks = {(y, w, d) for text in texts for y, w, d in printed_weeks(text) if w <= 53}
    kdca = sum(epi_week_start(y, w) == d for y, w, d in weeks)
    mmwr = sum(mmwr_week_start(y, w) == d for y, w, d in weeks)
    print(f"printed week dates: {len(weeks)}; KDCA rule {kdca}; MMWR rule {mmwr}")
    for y, w, d in sorted(weeks):
        if epi_week_start(y, w) != d:
            print(f"  not KDCA rule: {y}-{w:02d} printed {d}")


def main() -> None:
    with (KS / "manifest.csv").open(encoding="utf-8") as f:
        manifest = [r for r in csv.DictReader(f) if r["file"]]
    rows = []
    for i, entry in enumerate(manifest):
        path = KS / "bulletins" / entry["file"]
        if not path.exists():
            continue
        try:
            rows.extend(parse(path, entry["title"]))
        except subprocess.CalledProcessError as error:
            print(f"cannot read {entry['file']}: {error}", file=sys.stderr)
        if (i + 1) % 100 == 0:
            print(f"{i + 1}/{len(manifest)}", flush=True)
    texts = [to_text(p) for p in sorted((KS / "bulletins").iterdir())]
    check_week_rule(texts)
    df = pd.DataFrame(rows).drop_duplicates()
    print(write_tidy(df, "kdca_sentinel_bulletins"), len(df))


if __name__ == "__main__":
    main()
