# keiba-scraper

netkeiba から中央競馬のレース結果（着順・タイム・血統・ラップ）を自動収集し、
ローカルおよび **Streamlit Community Cloud** でインタラクティブに分析できるダッシュボードです。

## 構成

```
keiba-scraper/
├── app.py                        # Streamlit ダッシュボード（本体）
├── requirements.txt
├── src/
│   ├── scraper.py                # netkeiba スクレイパー
│   ├── processor.py              # データ整形
│   ├── writer.py                 # CSV 追記ロジック
│   ├── main.py                   # エントリーポイント
│   └── data/
│       └── master_data.csv       # 蓄積データ（週次自動更新）
├── tests/
│   └── test_processor.py
└── .github/workflows/
    └── keiba_weekly.yml          # 毎週日曜 21:00 JST に自動実行
```

## ローカルでの使い方

```bash
# 依存パッケージのインストール
pip install -r requirements.txt

# スクレイピング（直近の日曜）
cd src
python main.py

# 日付・オプション指定
python main.py --date 20260420
python main.py --date 20260420 --no-pedigree   # 血統取得スキップ（高速化）

# ダッシュボード起動
cd ..
streamlit run app.py
```

## GitHub Actions による週次自動運用

`.github/workflows/keiba_weekly.yml` が **毎週日曜 21:00 JST** に自動実行されます。

- スクレイピング → `src/data/master_data.csv` に追記
- 更新された CSV をリポジトリに自動コミット＆プッシュ
- Streamlit Community Cloud はリポジトリの変更を検知してダッシュボードを自動更新

手動実行は GitHub の **Actions タブ → Run workflow** から可能です。
`date` 入力欄に `YYYYMMDD` を指定すると任意の日付を取得できます。

## データ列構成

| 列 | 内容 |
|----|------|
| 開催日 | YYYY-MM-DD |
| 開催場 | 東京・阪神 など |
| race_id | netkeiba 内部 ID |
| レース名 | |
| 馬場 | 芝 / ダート / 障害 |
| 距離(m) | |
| 天候 | |
| 馬場状態 | 良・稍重・重・不良 |
| 着順〜調教師 | 1頭につき1行 |
| 父・母・母父 | 血統情報 |
| ラップタイム | "12.3/11.5/…" 形式 |

## 注意事項

- スクレイピング間隔はデフォルト **2秒**。サイトへの過度な負荷を避けてください。
- netkeiba の HTML 構造変更でパースが壊れることがあります。その場合は `scraper.py` の CSS セレクターを確認してください。
- 本ツールは個人的な学習・研究目的での利用を想定しています。
