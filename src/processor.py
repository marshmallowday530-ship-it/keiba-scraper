"""
スクレイピング結果を Google Sheets 書き込み用フラット行リストに変換する
"""

import pandas as pd


def flatten_race(race_data: dict) -> list[list]:
    """
    scraper.scrape_race() の戻り値を 2D リスト（行のリスト）に変換する。
    各行 = 1頭分のデータ（レース情報 + 馬情報 + ラップ）
    """
    info = race_data["info"]
    df: pd.DataFrame = race_data["results"]
    laps: list[float] = race_data["laps"]

    lap_str = "/".join(str(l) for l in laps)

    rows = []
    for _, horse in df.iterrows():
        row = [
            info.get("race_date", ""),
            info.get("venue", ""),
            info.get("race_id", ""),
            info.get("race_name", ""),
            info.get("surface", ""),
            info.get("distance", ""),
            info.get("weather", ""),
            info.get("track_condition", ""),
            horse.get("着順", ""),
            horse.get("枠番", ""),
            horse.get("馬番", ""),
            horse.get("馬名", ""),
            horse.get("horse_id", ""),
            horse.get("性齢", ""),
            horse.get("斤量", ""),
            horse.get("騎手", ""),
            horse.get("タイム", ""),
            horse.get("着差", ""),
            horse.get("人気", ""),
            horse.get("単勝オッズ", ""),
            horse.get("馬体重", ""),
            horse.get("調教師", ""),
            horse.get("父", ""),
            horse.get("母", ""),
            horse.get("母父", ""),
            lap_str,
        ]
        rows.append(row)
    return rows


HEADER = [
    "開催日", "開催場", "race_id", "レース名", "馬場", "距離(m)",
    "天候", "馬場状態",
    "着順", "枠番", "馬番", "馬名", "horse_id", "性齢", "斤量",
    "騎手", "タイム", "着差", "人気", "単勝オッズ", "馬体重", "調教師",
    "父", "母", "母父",
    "ラップタイム",
]


def build_sheet_rows(all_races: list[dict], include_header: bool = False) -> list[list]:
    """全レースのデータをシート書き込み用リストにまとめる。"""
    rows = []
    if include_header:
        rows.append(HEADER)
    for race in all_races:
        rows.extend(flatten_race(race))
    return rows
