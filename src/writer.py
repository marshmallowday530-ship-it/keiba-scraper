"""
CSV 書き込みモジュール
master_data.csv にレース結果を追記する
"""

import csv
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MASTER_FILENAME = "master_data.csv"


def write_csv(rows: list[list], output_dir: str = "data") -> Path:
    """
    rows を master_data.csv に追記する。
    - ファイルが存在しない場合: ヘッダー付きで新規作成
    - ファイルが存在する場合: 重複 race_id をスキップしてデータ行のみ追記
    戻り値: 書き込んだ CSV ファイルの Path
    """
    from processor import HEADER

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / MASTER_FILENAME

    # 既存の race_id を収集（重複書き込み防止）
    existing_race_ids: set[str] = set()
    race_id_col = HEADER.index("race_id")
    if csv_path.exists():
        with csv_path.open(encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            next(reader, None)  # ヘッダーをスキップ
            for row in reader:
                if len(row) > race_id_col:
                    existing_race_ids.add(row[race_id_col])

    # 重複レースをスキップ
    new_rows = [r for r in rows if len(r) <= race_id_col or r[race_id_col] not in existing_race_ids]
    if not new_rows:
        logger.info("追記する新規データがありません（全レース既存）")
        return csv_path

    # 新規ファイルはヘッダーを書く、既存ファイルはデータ行のみ追記
    mode = "a" if csv_path.exists() else "w"
    with csv_path.open(mode, encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        if mode == "w":
            writer.writerow(HEADER)
        writer.writerows([[str(cell) if cell is not None else "" for cell in row] for row in new_rows])

    logger.info(f"{len(new_rows)} 行を {csv_path} に追記しました")
    return csv_path
