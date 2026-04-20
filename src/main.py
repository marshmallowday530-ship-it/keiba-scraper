"""
エントリーポイント: スクレイピング → 整形 → CSV 書き込みを一括実行する
"""

import argparse
import os
import logging
from datetime import datetime, timedelta

from dotenv import load_dotenv

from scraper import scrape_day
from processor import build_sheet_rows
from writer import write_csv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="競馬レース結果をスクレイピングして CSV に書き込む")
    parser.add_argument("--date", default=None, help="対象日 YYYYMMDD（省略時は直近の日曜）")
    parser.add_argument("--no-pedigree", action="store_true", help="血統情報の取得をスキップする")
    parser.add_argument("--delay", type=float, default=None, help="リクエスト間隔（秒）")
    parser.add_argument("--output-dir", default=None, help="CSV 出力ディレクトリ（デフォルト: data）")
    args = parser.parse_args()

    delay = args.delay or float(os.environ.get("SCRAPE_DELAY_SECONDS", "2"))
    output_dir = args.output_dir or os.environ.get("OUTPUT_DIR", "data")

    target_date = args.date or os.environ.get("TARGET_DATE") or None

    # date_str を確定（ファイル名に使う）
    if target_date:
        date_str = target_date
    else:
        today = datetime.today()
        days_since_sunday = today.weekday() + 1 if today.weekday() != 6 else 0
        date_str = (today - timedelta(days=days_since_sunday)).strftime("%Y%m%d")

    # 1. スクレイピング
    logger.info("スクレイピング開始")
    all_races = scrape_day(
        target_date=target_date,
        fetch_pedigree=not args.no_pedigree,
        delay=delay,
    )
    logger.info(f"取得レース数: {len(all_races)}")

    # 2. 整形
    rows = build_sheet_rows(all_races, include_header=False)
    logger.info(f"書き込み対象行数: {len(rows)}")

    # 3. CSV 書き込み
    csv_path = write_csv(rows, output_dir)
    logger.info(f"完了: {csv_path}")


if __name__ == "__main__":
    main()
