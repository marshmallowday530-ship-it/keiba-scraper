"""
競馬データ ローカル分析ダッシュボード
起動: streamlit run app.py
"""

import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from pathlib import Path

# ── ページ設定 ────────────────────────────────────────────────────────
st.set_page_config(page_title="競馬データ分析", page_icon="🏇", layout="wide")
st.title("🏇 競馬データ分析ダッシュボード")

# ── データ読み込み ────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "src" / "data"
CSV_PATH = DATA_DIR / "master_data.csv"


@st.cache_data(ttl=60)  # 60秒キャッシュ → CSVが更新されると自動リロード
def load_data(path: Path, _mtime: float) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    df["開催日"] = pd.to_datetime(df["開催日"], errors="coerce")
    for col in ["着順", "枠番", "馬番", "人気", "距離(m)"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["斤量"] = pd.to_numeric(df["斤量"], errors="coerce")
    df["単勝オッズ"] = pd.to_numeric(df["単勝オッズ"], errors="coerce")
    # タイムを秒に変換（例: "1:34.5" → 94.5）
    def time_to_sec(t):
        try:
            parts = str(t).split(":")
            return float(parts[0]) * 60 + float(parts[1]) if len(parts) == 2 else float(t)
        except Exception:
            return None
    df["タイム_秒"] = df["タイム"].apply(time_to_sec)
    # 馬体重（数値のみ抽出: "480(-4)" → 480）
    df["馬体重_kg"] = df["馬体重"].str.extract(r"(\d+)").astype(float)
    return df


def sec_to_time(s) -> str:
    """秒数 → 競馬タイム表記（例: 94.5 → '1:34.5'）"""
    try:
        s = float(s)
        m = int(s // 60)
        sec = s - m * 60
        return f"{m}:{sec:04.1f}"
    except Exception:
        return ""


if not CSV_PATH.exists():
    st.error(f"CSVファイルが見つかりません: {CSV_PATH}\n`python src/main.py` を実行してデータを取得してください。")
    st.stop()

# CSV の更新時刻をキャッシュキーに渡す → 更新検知で自動リフレッシュ
_mtime = os.path.getmtime(CSV_PATH)
df_all = load_data(CSV_PATH, _mtime)

# ── 自動リフレッシュ設定 ───────────────────────────────────────────────
with st.sidebar:
    auto_refresh = st.checkbox("自動更新（30秒）", value=False)
if auto_refresh:
    import time as _time
    _time.sleep(0)  # ダミー（st.rerunのトリガー用）
    st.sidebar.caption(f"最終更新: {pd.Timestamp.now().strftime('%H:%M:%S')}")
    st.rerun()

# ── サイドバー フィルター ─────────────────────────────────────────────
st.sidebar.header("🔍 クロスフィルター")
st.sidebar.caption("条件を選ぶと全タブのグラフが連動して更新されます")
st.sidebar.divider()

# ── ① 開催条件 ───────────────────────────────────────────────────────
st.sidebar.markdown("**📅 開催条件**")

dates = sorted(df_all["開催日"].dropna().dt.date.unique())
date_sel = st.sidebar.multiselect("開催日", dates, default=dates)

venues = sorted(df_all["開催場"].dropna().unique())
venue_sel = st.sidebar.multiselect("競馬場", venues, default=venues)

# ── ② レース条件 ─────────────────────────────────────────────────────
st.sidebar.markdown("**🏟 レース条件**")

surfaces = sorted(df_all["馬場"].dropna().unique())
surface_sel = st.sidebar.multiselect("馬場（芝/ダート）", surfaces, default=surfaces)

track_conds = sorted(df_all["馬場状態"].dropna().unique())
cond_sel = st.sidebar.multiselect("馬場状態", track_conds, default=track_conds)

dist_vals = sorted(df_all["距離(m)"].dropna().unique().astype(int).tolist())
dist_sel = st.sidebar.multiselect("距離(m)", dist_vals, default=dist_vals)

# ── ③ 馬・人物 ───────────────────────────────────────────────────────
st.sidebar.markdown("**🐴 馬・人物**")

horse_query = st.sidebar.text_input("馬名（部分一致）")

sires = sorted(df_all["父"].dropna().unique())
sire_sel = st.sidebar.multiselect("父（種牡馬）", sires, placeholder="絞り込まない場合は空欄")

jockeys = sorted(df_all["騎手"].dropna().unique())
jockey_sel = st.sidebar.multiselect("騎手", jockeys, placeholder="絞り込まない場合は空欄")

# ── ④ 成績 ───────────────────────────────────────────────────────────
st.sidebar.markdown("**🏅 成績**")
rank_max = st.sidebar.slider("着順（～位以内）", 1, 18, 18)

# ── フィルター適用（全タブ共通の df を生成） ──────────────────────────
df = df_all[
    (df_all["開催日"].dt.date.isin(date_sel)) &
    (df_all["開催場"].isin(venue_sel)) &
    (df_all["馬場"].isin(surface_sel)) &
    (df_all["馬場状態"].isin(cond_sel) | df_all["馬場状態"].isna()) &
    (df_all["距離(m)"].isin(dist_vals)  # 全選択時はフル通過
        if set(dist_sel) == set(dist_vals)
        else df_all["距離(m)"].isin(dist_sel) | df_all["距離(m)"].isna()) &
    (df_all["着順"].le(rank_max) | df_all["着順"].isna())
]
if horse_query:
    df = df[df["馬名"].str.contains(horse_query, na=False)]
if sire_sel:
    df = df[df["父"].isin(sire_sel)]
if jockey_sel:
    df = df[df["騎手"].isin(jockey_sel)]

# ── フィルター結果サマリー ────────────────────────────────────────────
st.sidebar.divider()
pct = len(df) / len(df_all) * 100 if len(df_all) else 0
st.sidebar.markdown(f"**{len(df):,} 件** / 全 {len(df_all):,} 件（{pct:.0f}%）")
if len(df) == 0:
    st.sidebar.warning("条件に一致するデータがありません。")

# リセットボタン（ページ再読込で全フィルター初期化）
if st.sidebar.button("🔄 フィルターをリセット"):
    st.rerun()

# ── タブ構成 ─────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📋 データ一覧", "🔲 枠順分析", "⏱ 馬場×タイム分析",
    "🧬 血統分析", "🏅 騎手・調教師", "💰 期待値スコアリング",
])

# ════════════════════════════════════════════════════════════
# TAB 1: データ一覧
# ════════════════════════════════════════════════════════════
with tab1:
    st.subheader("レース結果一覧")

    show_cols = ["開催日", "開催場", "レース名", "馬場", "距離(m)", "着順", "枠番",
                 "馬番", "馬名", "性齢", "斤量", "騎手", "タイム", "人気", "単勝オッズ",
                 "馬体重", "父", "母父"]
    st.dataframe(
        df[show_cols].sort_values(["開催日", "レース名", "着順"]).reset_index(drop=True),
        use_container_width=True,
        height=500,
    )

    # サマリー指標
    st.divider()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("レース数", f"{df['race_id'].nunique():,}")
    col2.metric("頭数（延べ）", f"{len(df):,}")
    col3.metric("対象期間", f"{df['開催日'].min().strftime('%Y/%m/%d') if not df.empty else '-'} ～ {df['開催日'].max().strftime('%Y/%m/%d') if not df.empty else '-'}")
    col4.metric("競馬場数", f"{df['開催場'].nunique()}")

# ════════════════════════════════════════════════════════════
# TAB 2: 枠順分析
# ════════════════════════════════════════════════════════════
with tab2:
    st.subheader("枠順・馬番ごとの傾向")

    df_valid = df.dropna(subset=["枠番", "着順"])

    col_l, col_r = st.columns(2)

    with col_l:
        # 枠番別 勝率・連対率・複勝率
        def win_rate(g, n): return (g["着順"] <= n).mean() * 100

        frame_stats = (
            df_valid.groupby("枠番")
            .apply(lambda g: pd.Series({
                "出走数": len(g),
                "勝率(%)": round(win_rate(g, 1), 1),
                "連対率(%)": round(win_rate(g, 2), 1),
                "複勝率(%)": round(win_rate(g, 3), 1),
            }))
            .reset_index()
        )
        fig = px.bar(
            frame_stats.melt(id_vars="枠番", value_vars=["勝率(%)", "連対率(%)", "複勝率(%)"]),
            x="枠番", y="value", color="variable", barmode="group",
            title="枠番別 勝率・連対率・複勝率",
            labels={"value": "率 (%)", "variable": "指標"},
            color_discrete_sequence=["#ef4444", "#f97316", "#22c55e"],
        )
        fig.update_layout(xaxis=dict(tickmode="linear", dtick=1))
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        # 人気別 平均着順
        pop_stats = (
            df_valid.dropna(subset=["人気"])
            .groupby("人気")["着順"]
            .agg(["mean", "count"])
            .rename(columns={"mean": "平均着順", "count": "出走数"})
            .reset_index()
        )
        fig2 = px.scatter(
            pop_stats[pop_stats["人気"] <= 18],
            x="人気", y="平均着順", size="出走数",
            title="人気別 平均着順",
            labels={"人気": "単勝人気", "平均着順": "平均着順"},
            color="平均着順",
            color_continuous_scale="RdYlGn_r",
        )
        fig2.update_layout(xaxis=dict(tickmode="linear", dtick=1))
        st.plotly_chart(fig2, use_container_width=True)

    # 距離×馬場 ヒートマップ（平均着順）
    st.subheader("距離 × 馬場状態 ヒートマップ（平均着順）")
    pivot = (
        df_valid.dropna(subset=["距離(m)", "馬場状態"])
        .assign(**{"距離(m)": lambda d: d["距離(m)"].astype(int)})
        .groupby(["距離(m)", "馬場状態"])["着順"]
        .mean()
        .round(1)
        .unstack("馬場状態")
        .sort_index()
    )
    if not pivot.empty:
        fig3 = px.imshow(
            pivot, text_auto=True, aspect="auto",
            title="距離 × 馬場状態 平均着順（小さいほど好成績）",
            color_continuous_scale="RdYlGn_r",
        )
        st.plotly_chart(fig3, use_container_width=True)

# ════════════════════════════════════════════════════════════
# TAB 3: 馬場×タイム分析
# ════════════════════════════════════════════════════════════
with tab3:
    st.subheader("馬場状態 × タイム 分析")

    df_tm = df.dropna(subset=["タイム_秒", "距離(m)", "馬場状態"]).copy()

    if df_tm.empty:
        st.info("タイムデータが不足しています。")
    else:
        dist_options = sorted(df_tm["距離(m)"].dropna().unique().astype(int).tolist())

        def _time_ticks(series: pd.Series):
            """秒数シリーズからY軸用 tickvals/ticktext を生成（5秒刻み）"""
            lo = int(series.min()) // 5 * 5
            hi = int(series.max()) + 6
            vals = list(range(lo, hi, 5))
            return vals, [sec_to_time(v) for v in vals]

        # ── ① ヒートマップ：距離 × 馬場状態 平均勝ちタイム ──────────────
        st.subheader("距離 × 馬場状態 平均勝ちタイム")
        df_win = df_tm[df_tm["着順"] == 1]
        pivot_time = (
            df_win.groupby(["距離(m)", "馬場状態"])["タイム_秒"]
            .mean()
            .unstack("馬場状態")
            .sort_index()
        )
        if not pivot_time.empty:
            # 表示テキストをタイム形式に変換
            text_matrix = pivot_time.map(
                lambda x: sec_to_time(x) if pd.notna(x) else ""
            )
            fig_t1 = px.imshow(
                pivot_time, text_auto=False, aspect="auto",
                title="距離 × 馬場状態 平均勝ちタイム（小さいほど速い）",
                color_continuous_scale="RdYlGn",
                height=max(300, 60 * len(pivot_time)),
            )
            fig_t1.update_traces(text=text_matrix.values, texttemplate="%{text}")
            st.plotly_chart(fig_t1, use_container_width=True)

        st.divider()

        # ── ② バイオリン：タイム分布 ──────────────────────────────────
        st.subheader("タイム分布（馬場状態別）")
        sel_dist = st.selectbox("距離を選択", dist_options, index=0, key="dist_violin")
        df_vio = df_tm[df_tm["距離(m)"] == sel_dist]
        if not df_vio.empty:
            tvals, ttexts = _time_ticks(df_vio["タイム_秒"])
            fig_v = px.violin(
                df_vio, x="馬場状態", y="タイム_秒",
                box=True, points="outliers",
                title=f"{sel_dist}m タイム分布（馬場状態別）",
                color="馬場状態",
                labels={"タイム_秒": "タイム"},
                height=500,
            )
            fig_v.update_layout(yaxis=dict(tickvals=tvals, ticktext=ttexts))
            st.plotly_chart(fig_v, use_container_width=True)

        st.divider()

        # ── ③ 散布図：着順 vs タイム ──────────────────────────────────
        st.subheader("着順 vs タイム（馬場状態別）")
        col_surf, col_dist = st.columns(2)
        with col_surf:
            surf_sel = st.selectbox("馬場（芝/ダート）", sorted(df_tm["馬場"].dropna().unique()), key="surf_scatter")
        with col_dist:
            dist_sel2 = st.selectbox("距離", dist_options, key="dist_scatter")

        df_sc = df_tm[(df_tm["馬場"] == surf_sel) & (df_tm["距離(m)"] == dist_sel2)]
        if not df_sc.empty:
            tvals2, ttexts2 = _time_ticks(df_sc["タイム_秒"])
            df_sc = df_sc.copy()
            df_sc["タイム_表示"] = df_sc["タイム_秒"].apply(sec_to_time)
            fig_sc = px.scatter(
                df_sc, x="着順", y="タイム_秒",
                color="馬場状態", symbol="馬場状態",
                hover_data={"馬名": True, "騎手": True, "開催日": True,
                            "開催場": True, "タイム_表示": True, "タイム_秒": False},
                title=f"{surf_sel} {dist_sel2}m — 着順 vs タイム（馬場状態別）",
                labels={"着順": "着順", "タイム_秒": "タイム"},
                height=500,
            )
            fig_sc.update_layout(
                xaxis=dict(tickmode="linear", dtick=1),
                yaxis=dict(tickvals=tvals2, ticktext=ttexts2),
            )
            st.plotly_chart(fig_sc, use_container_width=True)
        else:
            st.info("該当データなし。")

        # ── ④ 統計テーブル ────────────────────────────────────────────
        st.divider()
        st.subheader("馬場状態別 タイム統計（距離ごと）")
        _agg = (
            df_tm.groupby(["馬場", "距離(m)", "馬場状態"])["タイム_秒"]
            .agg(出走数="count", 平均秒="mean", 最速秒="min", 最遅秒="max")
            .reset_index()
            .sort_values(["馬場", "距離(m)", "馬場状態"])
        )
        _agg["平均タイム"] = _agg["平均秒"].apply(sec_to_time)
        _agg["最速"] = _agg["最速秒"].apply(sec_to_time)
        _agg["最遅"] = _agg["最遅秒"].apply(sec_to_time)
        st.dataframe(
            _agg[["馬場", "距離(m)", "馬場状態", "出走数", "平均タイム", "最速", "最遅"]],
            use_container_width=True,
        )


# ════════════════════════════════════════════════════════════
# TAB 4: 血統分析
# ════════════════════════════════════════════════════════════
with tab4:
    st.subheader("血統（父・母父）分析")

    df_ped = df.dropna(subset=["父", "着順"])
    min_count = st.slider("最低出走数（父）", 1, 20, 3)

    col_l, col_r = st.columns(2)

    with col_l:
        sire_stats = (
            df_ped.groupby("父")
            .apply(lambda g: pd.Series({
                "出走数": len(g),
                "勝率(%)": round((g["着順"] == 1).mean() * 100, 1),
                "複勝率(%)": round((g["着順"] <= 3).mean() * 100, 1),
                "平均着順": round(g["着順"].mean(), 2),
            }))
            .reset_index()
        )
        sire_stats = sire_stats[sire_stats["出走数"] >= min_count].sort_values("勝率(%)", ascending=False).head(20)
        _h4 = max(400, 28 * len(sire_stats))
        fig4 = px.bar(
            sire_stats, x="勝率(%)", y="父", orientation="h",
            color="複勝率(%)", color_continuous_scale="Blues",
            title=f"父別 勝率 TOP20（出走{min_count}回以上）",
            text="出走数", height=_h4,
        )
        fig4.update_layout(yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig4, use_container_width=True)

    with col_r:
        bms_stats = (
            df.dropna(subset=["母父", "着順"])
            .groupby("母父")
            .apply(lambda g: pd.Series({
                "出走数": len(g),
                "勝率(%)": round((g["着順"] == 1).mean() * 100, 1),
                "複勝率(%)": round((g["着順"] <= 3).mean() * 100, 1),
            }))
            .reset_index()
        )
        bms_stats = bms_stats[bms_stats["出走数"] >= min_count].sort_values("複勝率(%)", ascending=False).head(20)
        _h5 = max(400, 28 * len(bms_stats))
        fig5 = px.bar(
            bms_stats, x="複勝率(%)", y="母父", orientation="h",
            color="勝率(%)", color_continuous_scale="Greens",
            title=f"母父別 複勝率 TOP20（出走{min_count}回以上）",
            text="出走数", height=_h5,
        )
        fig5.update_layout(yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig5, use_container_width=True)

    # 父 × 馬場 複勝率テーブル
    st.subheader("父 × 馬場 複勝率")
    top_sires = sire_stats["父"].head(15).tolist()
    sire_surface = (
        df_ped[df_ped["父"].isin(top_sires)]
        .groupby(["父", "馬場"])
        .apply(lambda g: round((g["着順"] <= 3).mean() * 100, 1))
        .unstack("馬場")
    )
    st.dataframe(sire_surface, use_container_width=True)

# ════════════════════════════════════════════════════════════
# TAB 5: 騎手・調教師
# ════════════════════════════════════════════════════════════
with tab5:
    st.subheader("騎手・調教師 成績")

    df_r = df.dropna(subset=["着順"])
    top_n = st.slider("表示人数", 5, 30, 15)

    col_l, col_r = st.columns(2)

    with col_l:
        jockey_stats = (
            df_r.groupby("騎手")
            .apply(lambda g: pd.Series({
                "騎乗数": len(g),
                "勝利数": (g["着順"] == 1).sum(),
                "勝率(%)": round((g["着順"] == 1).mean() * 100, 1),
                "連対率(%)": round((g["着順"] <= 2).mean() * 100, 1),
                "複勝率(%)": round((g["着順"] <= 3).mean() * 100, 1),
            }))
            .reset_index()
            .sort_values("勝利数", ascending=False)
            .head(top_n)
        )
        _h6 = max(400, 28 * len(jockey_stats))
        fig6 = px.bar(
            jockey_stats, x="勝利数", y="騎手", orientation="h",
            color="勝率(%)", color_continuous_scale="Oranges",
            title=f"騎手 勝利数 TOP{top_n}",
            text="勝率(%)", height=_h6,
        )
        fig6.update_layout(yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig6, use_container_width=True)
        st.dataframe(jockey_stats.reset_index(drop=True), use_container_width=True)

    with col_r:
        trainer_stats = (
            df_r.groupby("調教師")
            .apply(lambda g: pd.Series({
                "管理数": len(g),
                "勝利数": (g["着順"] == 1).sum(),
                "勝率(%)": round((g["着順"] == 1).mean() * 100, 1),
                "複勝率(%)": round((g["着順"] <= 3).mean() * 100, 1),
            }))
            .reset_index()
            .sort_values("勝利数", ascending=False)
            .head(top_n)
        )
        _h7 = max(400, 28 * len(trainer_stats))
        fig7 = px.bar(
            trainer_stats, x="勝利数", y="調教師", orientation="h",
            color="勝率(%)", color_continuous_scale="Purples",
            title=f"調教師 勝利数 TOP{top_n}",
            text="勝率(%)", height=_h7,
        )
        fig7.update_layout(yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig7, use_container_width=True)
        st.dataframe(trainer_stats.reset_index(drop=True), use_container_width=True)

# ════════════════════════════════════════════════════════════
# TAB 6: 期待値スコアリング
# ════════════════════════════════════════════════════════════
with tab6:
    st.subheader("💰 期待値スコアリング")
    st.caption(
        "過去データから条件ごとの **単勝回収率** と **期待値スコア** を算出します。"
        "　単勝回収率 100% 超 = 過去データ上は利益が出た条件です。"
    )

    # ── 計算ロジック ────────────────────────────────────────────────────
    # 単勝回収率(%) = Σ(着順1位のとき 単勝オッズ×100) / (出走数×100) × 100
    #              = Σ(着順1位のとき 単勝オッズ) / 出走数 × 100
    # 期待値スコア  = 勝率 × 平均単勝オッズ  (1.0超で理論上プラス)

    AXIS_OPTIONS = {
        "騎手":             ["騎手"],
        "父（種牡馬）":      ["父"],
        "枠番":             ["枠番"],
        "競馬場":           ["開催場"],
        "馬場（芝/ダート）": ["馬場"],
        "馬場状態":         ["馬場状態"],
        "距離(m)":          ["距離(m)"],
        "人気":             ["人気"],
        "競馬場 × 馬場状態": ["開催場", "馬場状態"],
        "競馬場 × 距離":    ["開催場", "距離(m)"],
        "馬場 × 距離":      ["馬場", "距離(m)"],
        "馬場 × 馬場状態":  ["馬場", "馬場状態"],
    }

    @st.cache_data(show_spinner=False)
    def calc_ev(df_json: str, group_cols: tuple) -> pd.DataFrame:
        """グループ別の回収率・期待値を計算する（JSON経由でキャッシュ）"""
        from io import StringIO
        src = pd.read_json(StringIO(df_json), orient="split")
        # 数値列を復元
        for c in ["着順", "単勝オッズ", "人気", "枠番", "距離(m)"]:
            if c in src.columns:
                src[c] = pd.to_numeric(src[c], errors="coerce")

        required = list(group_cols) + ["着順"]
        base = src.dropna(subset=required)

        rows = []
        for key, g in base.groupby(list(group_cols)):
            keys = key if isinstance(key, tuple) else (key,)
            n = len(g)
            wins = int((g["着順"] == 1).sum())
            top3 = int((g["着順"] <= 3).sum())

            # オッズがある行だけで回収率を計算
            g_o = g.dropna(subset=["単勝オッズ"])
            n_o = len(g_o)
            won_odds_sum = float(g_o.loc[g_o["着順"] == 1, "単勝オッズ"].sum())
            roi = round(won_odds_sum / n_o * 100, 1) if n_o > 0 else None
            avg_odds = round(float(g_o["単勝オッズ"].mean()), 1) if n_o > 0 else None
            ev = round((wins / n) * avg_odds, 3) if avg_odds else None

            row = dict(zip(group_cols, keys))
            row.update({
                "出走数":        n,
                "勝率(%)":       round(wins / n * 100, 1),
                "複勝率(%)":     round(top3 / n * 100, 1),
                "平均単勝オッズ": avg_odds,
                "単勝回収率(%)": roi,
                "期待値スコア":  ev,
            })
            rows.append(row)

        return pd.DataFrame(rows)

    # ── コントロール ────────────────────────────────────────────────────
    col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([2, 1, 1])
    with col_ctrl1:
        axis_label = st.selectbox("分析軸", list(AXIS_OPTIONS.keys()), key="ev_axis")
    with col_ctrl2:
        min_starts = st.number_input("最低出走数", min_value=1, max_value=50, value=5, key="ev_min")
    with col_ctrl3:
        sort_col = st.selectbox("並び順", ["単勝回収率(%)", "期待値スコア", "勝率(%)", "出走数"], key="ev_sort")

    group_cols = tuple(AXIS_OPTIONS[axis_label])

    df_ev_src = df.dropna(subset=["着順"])
    if df_ev_src.empty:
        st.info("フィルター後のデータがありません。")
    else:
        # DataFrameをJSONシリアライズしてキャッシュキーに使う
        import json
        df_json = df_ev_src.to_json(orient="split")
        ev_stats = calc_ev(df_json, group_cols)
        ev_stats = (
            ev_stats[ev_stats["出走数"] >= min_starts]
            .sort_values(sort_col, ascending=False)
            .reset_index(drop=True)
        )

        if ev_stats.empty:
            st.info(f"出走数 {min_starts} 回以上のデータがありません。")
        else:
            # ── ① KPI サマリー ──────────────────────────────────────
            st.divider()
            k1, k2, k3, k4 = st.columns(4)
            best_roi_row = ev_stats.dropna(subset=["単勝回収率(%)"]).nlargest(1, "単勝回収率(%)")
            best_ev_row  = ev_stats.dropna(subset=["期待値スコア"]).nlargest(1, "期待値スコア")
            top_label    = " / ".join(str(best_roi_row.iloc[0][c]) for c in group_cols)
            ev_label     = " / ".join(str(best_ev_row.iloc[0][c]) for c in group_cols)
            k1.metric("分析グループ数", f"{len(ev_stats)}")
            k2.metric("最高 単勝回収率", f"{best_roi_row['単勝回収率(%)'].iloc[0]:.1f}%", top_label)
            k3.metric("最高 期待値スコア", f"{best_ev_row['期待値スコア'].iloc[0]:.3f}", ev_label)
            k4.metric("全体平均 回収率",
                      f"{ev_stats['単勝回収率(%)'].mean():.1f}%" if ev_stats['単勝回収率(%)'].notna().any() else "-")

            # ── ② スコアリングテーブル ───────────────────────────────
            st.divider()
            st.subheader(f"条件別スコアリングテーブル（{axis_label}）")

            def _highlight(val, col):
                if col == "単勝回収率(%)" and pd.notna(val):
                    if val >= 120:   return "background-color:#16a34a;color:white"
                    if val >= 100:   return "background-color:#86efac"
                    if val < 70:     return "background-color:#fca5a5"
                if col == "期待値スコア" and pd.notna(val):
                    if val >= 1.2:   return "background-color:#16a34a;color:white"
                    if val >= 1.0:   return "background-color:#86efac"
                    if val < 0.7:    return "background-color:#fca5a5"
                return ""

            fmt = {
                "勝率(%)":       "{:.1f}",
                "複勝率(%)":     "{:.1f}",
                "単勝回収率(%)": "{:.1f}",
                "平均単勝オッズ": "{:.1f}",
                "期待値スコア":  "{:.3f}",
            }
            styled = (
                ev_stats.style
                .format(fmt, na_rep="-")
                .apply(lambda col: [_highlight(v, col.name) for v in col], axis=0)
            )
            st.dataframe(styled, use_container_width=True, height=420)

            # ── ③ 散布図：勝率 vs 期待値スコア ──────────────────────
            st.divider()
            st.subheader("勝率 vs 期待値スコア（バブルサイズ = 出走数）")
            df_plot = ev_stats.dropna(subset=["期待値スコア", "勝率(%)"])
            label_col = " × ".join(group_cols) if len(group_cols) > 1 else group_cols[0]
            df_plot = df_plot.copy()
            df_plot["ラベル"] = df_plot[list(group_cols)].astype(str).agg(" / ".join, axis=1)

            fig_ev1 = px.scatter(
                df_plot,
                x="勝率(%)", y="期待値スコア",
                size="出走数", color="単勝回収率(%)",
                text="ラベル",
                hover_data={"出走数": True, "複勝率(%)": True,
                            "平均単勝オッズ": True, "ラベル": False},
                color_continuous_scale="RdYlGn",
                range_color=[50, 150],
                title=f"{axis_label} — 勝率 vs 期待値スコア",
                labels={"勝率(%)": "勝率 (%)", "期待値スコア": "期待値スコア"},
                height=520,
            )
            # 損益ラインを追加（期待値スコア = 1.0）
            fig_ev1.add_hline(y=1.0, line_dash="dash", line_color="gray",
                              annotation_text="期待値スコア 1.0（損益分岐）",
                              annotation_position="top right")
            fig_ev1.update_traces(textposition="top center", textfont_size=10)
            fig_ev1.update_layout(coloraxis_colorbar_title="回収率(%)")
            st.plotly_chart(fig_ev1, use_container_width=True)

            # ── ④ バーチャート：単勝回収率 TOP / BOTTOM ─────────────
            st.divider()
            col_top, col_bot = st.columns(2)
            top_n_ev = st.slider("表示件数（TOP / BOTTOM）", 5, 30, 15, key="ev_topn")

            df_bar = ev_stats.dropna(subset=["単勝回収率(%)"])
            df_top = df_bar.nlargest(top_n_ev, "単勝回収率(%)")
            df_bot = df_bar.nsmallest(top_n_ev, "単勝回収率(%)")

            for df_b, col_b, title_b, scale in [
                (df_top, col_top, f"単勝回収率 TOP{top_n_ev}", "Greens"),
                (df_bot, col_bot, f"単勝回収率 BOTTOM{top_n_ev}", "Reds_r"),
            ]:
                df_b = df_b.copy()
                df_b["ラベル"] = df_b[list(group_cols)].astype(str).agg(" / ".join, axis=1)
                _hb = max(380, 28 * len(df_b))
                fig_b = px.bar(
                    df_b, x="単勝回収率(%)", y="ラベル", orientation="h",
                    color="勝率(%)", color_continuous_scale=scale,
                    text="出走数", height=_hb,
                    title=title_b,
                )
                fig_b.add_vline(x=100, line_dash="dash", line_color="gray")
                fig_b.update_layout(yaxis=dict(autorange="reversed"))
                col_b.plotly_chart(fig_b, use_container_width=True)
