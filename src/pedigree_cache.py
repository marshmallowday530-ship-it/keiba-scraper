"""
血統キャッシュ — horse_id ごとに父・母・母父を永続化し、再取得を防ぐ
"""

import csv
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CACHE_PATH = Path(__file__).parent / "data" / "pedigree_cache.csv"
CACHE_COLS = ["horse_id", "父", "母", "母父"]


def load_cache() -> dict:
    """CSV から {horse_id: {"父": ..., "母": ..., "母父": ...}} を返す"""
    if not CACHE_PATH.exists():
        return {}
    cache = {}
    with CACHE_PATH.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            cache[row["horse_id"]] = {"父": row["父"], "母": row["母"], "母父": row["母父"]}
    logger.debug(f"血統キャッシュ読み込み: {len(cache)} 頭")
    return cache


def save_cache(cache: dict) -> None:
    """辞書を CSV に上書き保存する"""
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CACHE_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CACHE_COLS)
        writer.writeheader()
        for horse_id, ped in cache.items():
            writer.writerow({"horse_id": horse_id, **ped})
    logger.debug(f"血統キャッシュ保存: {len(cache)} 頭")


def build_from_master_csv(master_csv: Path) -> int:
    """既存の master_data.csv から pedigree_cache.csv を構築する。戻り値は追加頭数。"""
    existing = load_cache()
    added = 0
    with master_csv.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            hid = row.get("horse_id", "")
            father = row.get("父", "")
            if hid and father and hid not in existing:
                existing[hid] = {"父": father, "母": row.get("母", ""), "母父": row.get("母父", "")}
                added += 1
    if added:
        save_cache(existing)
    logger.info(f"master_data.csv からキャッシュ構築: +{added} 頭 (合計 {len(existing)} 頭)")
    return added
