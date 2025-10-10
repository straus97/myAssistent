"""
Роутер для создания бэкапов (snapshot)
"""
from __future__ import annotations
import os
import zipfile
from pathlib import Path
from fastapi import APIRouter, Depends

from src.dependencies import require_api_key, ok
from src.utils import _now_utc


router = APIRouter(prefix="/backup", tags=["Backup"])


@router.post("/snapshot")
def backup_snapshot(_=Depends(require_api_key)):
    """Создать snapshot бэкап (БД + артефакты)"""
    ts = _now_utc().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("artifacts") / "backups"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_zip = out_dir / f"snapshot_{ts}.zip"

    # Файлы для включения
    include_files = []
    for name in ["README.md", "JOURNAL.md"]:
        p = Path(name)
        if p.exists():
            include_files.append(p)

    for p in [
        Path("artifacts") / "journal.csv",
        Path("artifacts") / "journal.xlsx",
        Path("artifacts") / "paper_state.json",
        Path("artifacts") / "reports" / "latest.html",
    ]:
        if p.exists():
            include_files.append(p)

    # Директории для включения
    include_dirs = [
        Path("artifacts") / "config",
        Path("artifacts") / "reports",
        Path("artifacts") / "models",
    ]

    # Создание ZIP-архива
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in include_files:
            z.write(p, p.as_posix())
        for d in include_dirs:
            if d.exists():
                for root, dirs, files in os.walk(d):
                    for f in files:
                        full = Path(root) / f
                        z.write(full, full.as_posix())

    rel_url = f"/artifacts/backups/{out_zip.name}"
    return ok(path=str(out_zip.resolve()), url=rel_url)
