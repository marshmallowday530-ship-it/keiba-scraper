"""processor.flatten_race の単体テスト"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pandas as pd
from processor import flatten_race, build_sheet_rows, HEADER


def _make_race_data(n_horses: int = 3) -> dict:
    df = pd.DataFrame(
        [
            {
                "着順": str(i + 1),
                "枠番": str(i + 1),
                "馬番": str(i + 1),
                "馬名": f"テスト馬{i+1}",
                "horse_id": f"horse{i+1:06d}",
                "性齢": "牡3",
                "斤量": "57",
                "騎手": "テスト騎手",
                "タイム": "1:35.0",
                "着差": "クビ",
                "人気": str(i + 1),
                "単勝オッズ": "5.0",
                "馬体重": "480",
                "調教師": "テスト調教師",
                "父": "ディープインパクト",
                "母": "テスト母",
                "母父": "キングカメハメハ",
            }
            for i in range(n_horses)
        ]
    )
    return {
        "info": {
            "race_id": "202405050511",
            "race_name": "テストレース",
            "race_date": "2024-05-05",
            "venue": "東京",
            "surface": "芝",
            "distance": 1600,
            "weather": "晴",
            "track_condition": "良",
        },
        "results": df,
        "laps": [12.3, 11.5, 11.2, 11.8, 12.0],
    }


def test_flatten_race_row_count():
    data = _make_race_data(5)
    rows = flatten_race(data)
    assert len(rows) == 5


def test_flatten_race_columns():
    data = _make_race_data(1)
    rows = flatten_race(data)
    assert len(rows[0]) == len(HEADER)


def test_lap_string():
    data = _make_race_data(1)
    rows = flatten_race(data)
    assert rows[0][-1] == "12.3/11.5/11.2/11.8/12.0"


def test_build_sheet_rows_with_header():
    data = _make_race_data(2)
    rows = build_sheet_rows([data], include_header=True)
    assert rows[0] == HEADER
    assert len(rows) == 3  # ヘッダー + 2頭
