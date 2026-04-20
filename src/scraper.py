"""
netkeiba スクレイパー
直近の開催日レース結果（着順・タイム・血統・ラップ）を取得する
"""

import time
import random
import re
import logging
from datetime import datetime, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
BASE_URL = "https://db.netkeiba.com"


def _get(url: str, delay: float = 2.0) -> BeautifulSoup:
    """GETリクエスト＋待機。delay〜delay+1秒のランダムスリープでサイト負荷を軽減。"""
    wait = random.uniform(delay, delay + 1.0)
    logger.debug(f"sleep {wait:.2f}s before {url}")
    time.sleep(wait)
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding
    return BeautifulSoup(resp.text, "lxml")


# ── 開催日・レースID取得 ────────────────────────────────────────────

def get_latest_race_ids(target_date: Optional[str] = None, delay: float = 2.0) -> list[str]:
    """
    直近（または指定）開催日の全レースIDを返す。
    target_date: 'YYYYMMDD' 形式。None の場合は直近の日曜を探す。
    """
    if target_date is None:
        # 直近の日曜（今日が日曜なら今日）
        today = datetime.today()
        days_since_sunday = today.weekday() + 1 if today.weekday() != 6 else 0
        target = today - timedelta(days=days_since_sunday)
        target_date = target.strftime("%Y%m%d")

    logger.info(f"対象日: {target_date}")
    url = f"https://race.netkeiba.com/top/race_list_sub.html?kaisai_date={target_date}"
    soup = _get(url, delay)

    race_ids = []
    for a in soup.select("a[href*='/race/result.html?race_id=']"):
        match = re.search(r"race_id=(\d+)", a["href"])
        if match:
            rid = match.group(1)
            if rid not in race_ids:
                race_ids.append(rid)

    logger.info(f"取得レース数: {len(race_ids)}")
    return race_ids


# ── レース基本情報 ──────────────────────────────────────────────────

def _parse_race_info(soup: BeautifulSoup, race_id: str, race_date: Optional[str] = None) -> dict:
    """レース名・場所・距離・馬場状態などを解析する。"""
    info: dict = {"race_id": race_id}

    # レース名: .RaceName h1
    title_tag = soup.select_one("h1.RaceName")
    info["race_name"] = title_tag.get_text(strip=True) if title_tag else ""

    # 距離・天候・馬場状態: .RaceData01
    race_data1 = soup.select_one(".RaceData01")
    raw1 = race_data1.get_text(" ", strip=True) if race_data1 else ""

    m = re.search(r"([芝ダ障])(\d+)m", raw1)
    if m:
        info["surface"] = "芝" if m.group(1) == "芝" else "ダート" if m.group(1) == "ダ" else "障害"
        info["distance"] = int(m.group(2))
    else:
        info["surface"] = ""
        info["distance"] = ""

    m_weather = re.search(r"天候\s*[:：]\s*(\S+)", raw1)
    info["weather"] = m_weather.group(1) if m_weather else ""

    m_cond = re.search(r"馬場\s*[:：]\s*(\S+)", raw1)
    info["track_condition"] = m_cond.group(1) if m_cond else ""

    # 開催場所（レースIDの5〜6桁目が場コード）
    venue_code = race_id[4:6]
    venue_map = {
        "01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
        "05": "東京", "06": "中山", "07": "中京", "08": "京都",
        "09": "阪神", "10": "小倉",
    }
    info["venue"] = venue_map.get(venue_code, venue_code)
    # race_date は呼び出し元から渡された kaisai_date を使う（race_id 内の桁は月日ではない）
    if race_date:
        d = race_date.replace("-", "")
        info["race_date"] = f"{d[0:4]}-{d[4:6]}-{d[6:8]}"
    else:
        info["race_date"] = ""

    return info


# ── 着順結果 ───────────────────────────────────────────────────────

def _parse_results(soup: BeautifulSoup) -> pd.DataFrame:
    """着順テーブルを DataFrame に変換する。"""
    # 現行の netkeiba は RaceTable01 クラスを使用
    table = soup.select_one("table.RaceTable01")
    if table is None:
        return pd.DataFrame()

    rows = []
    for tr in table.select("tr")[1:]:  # ヘッダー行をスキップ
        cells = [td.get_text(strip=True) for td in tr.select("td")]
        if len(cells) < 10:
            continue
        horse_link = tr.select_one("td a[href*='/horse/']")
        horse_id = ""
        if horse_link:
            m = re.search(r"/horse/(\w+)", horse_link["href"])
            horse_id = m.group(1) if m else ""

        # 列順: 着順,枠,馬番,馬名,性齢,斤量,騎手,タイム,着差,人気,単勝オッズ,後3F,コーナー通過順,厩舎,馬体重(増減)
        rows.append({
            "着順": cells[0],
            "枠番": cells[1],
            "馬番": cells[2],
            "馬名": cells[3],
            "horse_id": horse_id,
            "性齢": cells[4],
            "斤量": cells[5],
            "騎手": cells[6],
            "タイム": cells[7],
            "着差": cells[8],
            "人気": cells[9],
            "単勝オッズ": cells[10] if len(cells) > 10 else "",
            "馬体重": cells[14] if len(cells) > 14 else "",
            "調教師": cells[13] if len(cells) > 13 else "",
        })

    return pd.DataFrame(rows)


# ── ラップタイム ────────────────────────────────────────────────────

def _parse_lap(soup: BeautifulSoup) -> list[float]:
    """ラップタイムリストを返す（秒単位）。"""
    # Race_HaronTime テーブルの3行目（index=2）が区間ラップ
    table = soup.select_one("table.Race_HaronTime")
    if table is None:
        return []
    rows = table.select("tr")
    if len(rows) < 3:
        return []
    laps = []
    for td in rows[2].select("td"):
        txt = td.get_text(strip=True)
        try:
            laps.append(float(txt))
        except ValueError:
            pass
    return laps


# ── 血統情報 ───────────────────────────────────────────────────────

def get_pedigree(horse_id: str, delay: float = 2.0) -> dict:
    """horse_id から父・母・母父を取得する。"""
    url = f"{BASE_URL}/horse/ped/{horse_id}/"
    try:
        soup = _get(url, delay)
        table = soup.select_one("table.blood_table")
        if table is None:
            return {}
        rows = table.find_all("tr")
        if len(rows) < 17:
            return {}

        def _name(td) -> str:
            # "キングカメハメハ2001 鹿毛[血統]..." → "キングカメハメハ"
            return re.sub(r"\s*\d{4}.*", "", td.get_text(strip=True)).strip()

        sire_tds  = rows[0].find_all("td")   # row0: 父, 父父, 父父父 ...
        dam_tds   = rows[16].find_all("td")  # row16: 母, 母父, 母父父 ...

        return {
            "父":  _name(sire_tds[0]) if sire_tds else "",
            "母":  _name(dam_tds[0])  if dam_tds  else "",
            "母父": _name(dam_tds[1]) if len(dam_tds) > 1 else "",
        }
    except Exception as e:
        logger.warning(f"血統取得失敗 horse_id={horse_id}: {e}")
        return {}


# ── メイン：1レース分のデータ取得 ─────────────────────────────────

def scrape_race(race_id: str, fetch_pedigree: bool = True, delay: float = 2.0, race_date: Optional[str] = None) -> dict:
    """
    1レース分の結果・ラップ・血統をまとめて返す。
    戻り値:
      {
        "info":    {race_id, race_name, venue, ...},
        "results": DataFrame,
        "laps":    [float, ...],
      }
    """
    url = f"https://race.netkeiba.com/race/result.html?race_id={race_id}"
    logger.info(f"スクレイピング: {url}")
    soup = _get(url, delay)

    info = _parse_race_info(soup, race_id, race_date=race_date)
    results_df = _parse_results(soup)
    laps = _parse_lap(soup)

    if fetch_pedigree and not results_df.empty:
        sire_list, dam_list, broodmare_sire_list = [], [], []
        for _, row in results_df.iterrows():
            if row["horse_id"]:
                ped = get_pedigree(row["horse_id"], delay)
                sire_list.append(ped.get("父", ""))
                dam_list.append(ped.get("母", ""))
                broodmare_sire_list.append(ped.get("母父", ""))
            else:
                sire_list.append("")
                dam_list.append("")
                broodmare_sire_list.append("")
        results_df["父"] = sire_list
        results_df["母"] = dam_list
        results_df["母父"] = broodmare_sire_list

    return {"info": info, "results": results_df, "laps": laps}


# ── 日次まとめ：全レース取得 ───────────────────────────────────────

def scrape_day(target_date: Optional[str] = None, fetch_pedigree: bool = True, delay: float = 2.0) -> list[dict]:
    """指定日の全レースデータをリストで返す。"""
    race_ids = get_latest_race_ids(target_date, delay)
    results = []
    for rid in race_ids:
        try:
            data = scrape_race(rid, fetch_pedigree=fetch_pedigree, delay=delay, race_date=target_date)
            results.append(data)
        except Exception as e:
            logger.error(f"レース {rid} の取得失敗: {e}")
    return results
