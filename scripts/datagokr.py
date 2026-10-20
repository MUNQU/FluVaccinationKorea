"""Download the file of a dataset on the Public Data Portal (data.go.kr)."""

import re
from pathlib import Path
from urllib.parse import unquote

import requests

PORTAL = "https://www.data.go.kr"


def download(dataset: str, raw_dir: Path, prefix: str) -> Path:
    """Download the current release as `<prefix>_<cut-off date><ext>`.

    The cut-off date is the suffix of the dataset name ("..._20251231"). If
    the file already exists, the function does not download it again.
    """
    page = requests.get(f"{PORTAL}/data/{dataset}/fileData.do", timeout=60).text
    detail_pk = page.split('name="publicDataDetailPk" value="')[1].split('"')[0]
    info = requests.post(
        f"{PORTAL}/tcs/dss/selectFileDataDownload.do",
        data={
            "publicDataDetailPk": detail_pk,
            "publicDataPk": dataset,
            "atchFileId": "",
            "fileDetailSn": "1",
            "publicDataTyCode": "PR0051",
        },
        timeout=60,
    ).json()
    cutoff = info["dataSetFileDetailInfo"]["dataNm"].rsplit("_", 1)[1]
    existing = sorted(raw_dir.glob(f"{prefix}_{cutoff}.*"))
    if existing:
        return existing[0]
    response = requests.get(
        f"{PORTAL}/cmm/cmm/fileDownload.do",
        params={"atchFileId": info["atchFileId"], "fileDetailSn": info["fileDetailSn"]},
        timeout=600,
    )
    response.raise_for_status()
    # The header holds the original file name, UTF-8 bytes sent as Latin-1.
    disposition = response.headers["Content-Disposition"].encode("latin-1")
    name = unquote(disposition.decode("utf-8", errors="replace"))
    ext = re.search(r"(\.\w+)\"?;?\s*$", name).group(1).lower()
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{prefix}_{cutoff}{ext}"
    path.write_bytes(response.content)
    return path
