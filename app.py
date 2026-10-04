"""국토종주 자전거길 그랜드슬램 인증센터 지도.

- centers.csv   : 인증센터 목록 (좌표 포함)
- completed.json: 완료한 구간 설정
실행: streamlit run app.py
"""
import json
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from folium.plugins import Fullscreen, MarkerCluster
from streamlit_folium import st_folium

BASE = Path(__file__).parent
DONE_COLOR = "#16a34a"   # 완료: 초록
TODO_COLOR = "#6b7280"   # 미완료: 회색
GROUP_ORDER = ["국토종주", "4대강", "북한강", "섬진강", "동해안", "제주환상", "오천"]


def load_data():
    df = pd.read_csv(BASE / "centers.csv")
    cfg = json.loads((BASE / "completed.json").read_text(encoding="utf-8"))
    df["done"] = (
        df["group"].isin(cfg.get("completed_groups", []))
        | df["route"].isin(cfg.get("completed_routes", []))
        | df["name"].isin(cfg.get("completed_centers", []))
    )
    return df.sort_values(["group", "route", "seq"]).reset_index(drop=True)


def build_map(df: pd.DataFrame, show_lines: bool = True) -> folium.Map:
    m = folium.Map(location=[36.3, 127.8], zoom_start=7, tiles="OpenStreetMap")
    Fullscreen().add_to(m)

    if show_lines:
        for (route, group), g in df.groupby(["route", "group"], sort=False):
            g = g.sort_values("seq")
            if len(g) < 2:
                continue
            folium.PolyLine(
                g[["lat", "lon"]].values.tolist(),
                color=DONE_COLOR if g["done"].all() else TODO_COLOR,
                weight=4 if g["done"].all() else 3,
                opacity=0.7,
                dash_array=None if g["done"].all() else "6",
                tooltip=f"{route} ({group})",
            ).add_to(m)

    cluster = MarkerCluster(disableClusteringAtZoom=10).add_to(m)
    for r in df.itertuples():
        color = "green" if r.done else "gray"
        status = "✅ 완료" if r.done else "⬜ 미완료"
        popup = (
            f"<b>{r.name}</b><br>{r.route}<br>그룹: {r.group}<br>"
            f"{r.kind}인증센터<br>{status}"
            + ("<br><i>좌표 근사치</i>" if r.coord_status == "approx" else "")
        )
        folium.Marker(
            [r.lat, r.lon],
            tooltip=f"{r.name} ({status})",
            popup=folium.Popup(popup, max_width=240),
            icon=folium.Icon(color=color, icon="check" if r.done else "flag", prefix="fa"),
        ).add_to(cluster)

    legend = """
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 9999;
                background: white; padding: 10px 14px; border-radius: 8px;
                box-shadow: 0 1px 6px rgba(0,0,0,.3); font-size: 13px;">
      <b>범례</b><br>
      <span style="color:#16a34a">●</span> 완료한 인증센터/구간<br>
      <span style="color:#6b7280">●</span> 남은 인증센터/구간
    </div>"""
    m.get_root().html.add_child(folium.Element(legend))
    return m


def main():
    st.set_page_config(page_title="그랜드슬램 인증센터 지도", page_icon="🚲", layout="wide")
    st.title("🚲 그랜드슬램 인증센터 지도")

    df = load_data()

    with st.sidebar:
        st.header("필터")
        groups = [g for g in GROUP_ORDER if g in set(df["group"])] + sorted(
            set(df["group"]) - set(GROUP_ORDER)
        )
        picked = st.multiselect("그랜드슬램 구간", groups, default=groups)
        status = st.radio("상태", ["전체", "완료", "미완료"], horizontal=True)
        show_lines = st.checkbox("자전거길 연결선 표시(센터 간 직선)", value=True)

    view = df[df["group"].isin(picked)]
    if status == "완료":
        view = view[view["done"]]
    elif status == "미완료":
        view = view[~view["done"]]

    total, done = len(df), int(df["done"].sum())
    c1, c2, c3 = st.columns(3)
    c1.metric("전체 인증센터", total)
    c2.metric("완료", done)
    c3.metric("진행률", f"{done / total:.0%}")

    summary = (
        df.groupby("group")
        .agg(센터수=("name", "count"), 완료=("done", "sum"))
        .reindex([g for g in GROUP_ORDER if g in set(df["group"])])
        .dropna()
        .astype(int)
    )
    summary["상태"] = summary.apply(lambda r: "✅ 완료" if r["완료"] == r["센터수"] else "진행 전", axis=1)
    st.dataframe(summary, use_container_width=True)

    if view.empty:
        st.info("조건에 맞는 인증센터가 없습니다.")
    else:
        st_folium(build_map(view, show_lines), height=650, use_container_width=True, returned_objects=[])

    st.caption(
        "좌표는 근사치(coord_status=approx)입니다. 정확한 위치는 centers.csv에서 수정하세요. "
        "공식 정보: https://www.bike.go.kr"
    )


if __name__ == "__main__":
    main()
