"""Download KDCA sentinel surveillance data.

Two parts:
1. The influenza bulletins of the dportal board 1010 (PDF/HWP attachments).
2. The weekly ILI table behind dportal's statistics page (`influListAjax.do`).

Files go to `data/raw/kdca_sentinel/`. Existing files are not downloaded again.

Usage: .venv/bin/python -I scripts/kdca_sentinel_download.py [bulletins|db|all]
"""

import csv
import html
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import unquote

import requests

BASE = "https://dportal.kdca.go.kr"
RAW = Path(__file__).resolve().parent.parent / "data" / "raw" / "kdca_sentinel"
BULLETINS = RAW / "bulletins"
DB = RAW / "db"
DELAY = 0.5
# First season with ILI data on dportal (2003-2004 is partial).
FIRST_SEASON = 2003

# Board posts that hold influenza data. Scrub typhus, malaria, SFTS, AIDS,
# dengue, COVID-19 and STI bulletins of the same board are left out.
FLU_TITLE = re.compile(r"표본감시|인플루엔자")

session = requests.Session()
session.headers["User-Agent"] = "FluVaccinationKorea data collection (research)"
TIMEOUT = (15, 60)


def get(url: str, **kwargs) -> requests.Response:
    """GET with three tries: the server sometimes stalls a connection."""
    for attempt in range(3):
        try:
            response = session.get(url, timeout=TIMEOUT, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException:
            if attempt == 2:
                raise
            # A stale session cookie makes the server answer 500 to a
            # redirect; a new session works.
            session.cookies.clear()
            time.sleep(10)


def list_posts() -> list[dict]:
    url = f"{BASE}/pot/bbs/BD_selectBbsList.do"
    params = {"q_bbsSn": 1010, "q_clsfNo": 2, "q_currPage": 1, "q_rowPerPage": 5000}
    page = get(url, params=params).text
    posts = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        link = re.search(r'q_bbsDocNo=(\d+)&q_clsfNo=2">([^<]*)</a>', row)
        if not link:
            continue
        cells = [
            re.sub(r"<[^>]+>|\s+", " ", c).strip()
            for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        ]
        dates = [c for c in cells if re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", c)]
        title = html.unescape(link.group(2)).strip()
        posts.append(
            {
                "doc_no": link.group(1),
                "title": title,
                "posted": dates[0] if dates else "",
            }
        )
    return posts


def attachments(doc_no: str) -> list[tuple[str, str]]:
    url = f"{BASE}/pot/bbs/BD_selectBbs.do"
    page = get(url, params={"q_bbsSn": 1010, "q_bbsDocNo": doc_no, "q_clsfNo": 2}).text
    found = re.findall(
        r'href="(/pot/component/file/ND_fileDownload\.do\?[^"]+)"[^>]*>([^<]+)</a>',
        page,
    )
    # Some links are escaped twice ("&amp;amp;").
    return [
        (html.unescape(html.unescape(href)), html.unescape(name).strip())
        for href, name in found
    ]


def safe_name(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s]+', "_", name)


def download_bulletins() -> None:
    BULLETINS.mkdir(parents=True, exist_ok=True)
    posts = [p for p in list_posts() if FLU_TITLE.search(p["title"])]
    manifest_path = RAW / "manifest.csv"
    done = {}
    if manifest_path.exists():
        with manifest_path.open(encoding="utf-8") as f:
            done = {r["doc_no"]: r for r in csv.DictReader(f) if r["file"]}
    fields = ["doc_no", "title", "posted", "file", "bytes"]
    rows = []
    for i, post in enumerate(posts):
        if (
            post["doc_no"] in done
            and (BULLETINS / done[post["doc_no"]]["file"]).exists()
        ):
            rows.append(done[post["doc_no"]])
            continue
        time.sleep(DELAY)
        try:
            files = attachments(post["doc_no"])
            if not files:
                rows.append({**post, "file": "", "bytes": 0})
            for href, name in files:
                target = BULLETINS / f"{post['doc_no']}_{safe_name(name)}"
                if not target.exists():
                    time.sleep(DELAY)
                    response = get(BASE + href)
                    disposition = unquote(
                        response.headers.get("Content-Disposition", "")
                    )
                    if "attachment" not in disposition:
                        print(f"not a file: {post['title']} {href}", file=sys.stderr)
                        continue
                    target.write_bytes(response.content)
                rows.append(
                    {**post, "file": target.name, "bytes": target.stat().st_size}
                )
        except requests.RequestException as error:
            print(f"failed: {post['title']}: {error}", file=sys.stderr)
        print(f"{i + 1}/{len(posts)} {post['title']}", flush=True)
        if (i + 1) % 20 == 0:
            write_manifest(manifest_path, fields, rows)
    write_manifest(manifest_path, fields, rows)


def write_manifest(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def query_db(start: int, by_age: bool = False, sido: str = "", end: int = 0) -> dict:
    end = end or start + 1
    data = {
        "icdNm": "influ",
        "startYear": start,
        "endYear": end,
        "yearGap": end - start,
        "age": "",
        "sido": sido,
        "ageText": "전체",
    }
    if by_age:
        data["intoDivi"] = "1"
    response = session.post(
        f"{BASE}/pot/is/st/influListAjax.do", data=data, timeout=TIMEOUT
    )
    return response.json()["value"]


# Province codes of the dportal form ("05" Gwangju and "13" Jeonnam are no
# longer used; "18" is the merged Jeonnam-Gwangju).
DB_SIDO = [
    "01",
    "02",
    "03",
    "04",
    "05",
    "06",
    "07",
    "17",
    "08",
    "09",
    "10",
    "11",
    "12",
    "18",
    "13",
    "14",
    "15",
    "16",
]


def download_db() -> None:
    DB.mkdir(parents=True, exist_ok=True)
    last = time.localtime().tm_year
    # National series of all seasons in one query. The one-season query
    # returns 0.0 for some January-February weeks before 2013 (for example
    # 2008 weeks 4-9); the all-season query does not.
    all_seasons = query_db(FIRST_SEASON, end=last + 1)
    (DB / "influ_all_total.json").write_text(
        json.dumps(all_seasons, ensure_ascii=False), encoding="utf-8"
    )
    for start in range(2005, last + 1):
        for by_age in (False, True):
            name = f"influ_{start}_{start + 1}_{'age' if by_age else 'total'}.json"
            time.sleep(DELAY)
            (DB / name).write_text(
                json.dumps(query_db(start, by_age), ensure_ascii=False),
                encoding="utf-8",
            )
        for sido in DB_SIDO:
            name = f"influ_{start}_{start + 1}_sido{sido}.json"
            time.sleep(DELAY)
            value = query_db(start, sido=sido)
            if any(
                v not in ("", "`")
                for row in value["data"]
                for v in row["VALUE"].split("`")
            ):
                (DB / name).write_text(
                    json.dumps(value, ensure_ascii=False), encoding="utf-8"
                )
        print(f"db season {start}-{start + 1}", flush=True)


if __name__ == "__main__":
    part = sys.argv[1] if len(sys.argv) > 1 else "all"
    if part in ("db", "all"):
        download_db()
    if part in ("bulletins", "all"):
        download_bulletins()
