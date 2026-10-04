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
DONE_COLOR = "#dc2626"   # 완주/완료: 붉은색
TODO_COLOR = "#6b7280"   # 남은 구간: 회색

GROUP_ORDER = ["국토종주", "4대강", "북한강", "섬진강", "동해안", "제주환상", "오천"]
GROUP_LABEL = {
    "국토종주": "국토종주 (인천→부산)",
    "4대강": "4대강 종주 추가 구간 (금강·영산강)",
    "북한강": "북한강",
    "섬진강": "섬진강",
    "동해안": "동해안",
    "제주환상": "제주환상",
    "오천": "오천",
}

# 하나의 길로 이어서 그릴 구간 (순서대로 연결)
MAIN_LABEL = "국토종주 (인천→부산)"
CHAINS = {
    MAIN_LABEL: [
        "아라자전거길",
        "한강종주자전거길(서울구간)",
        "남한강자전거길",
        "새재자전거길",
        "낙동강자전거길",
    ],
    "동해안자전거길": ["동해안자전거길(강원)", "동해안자전거길(경북)"],
}
# 본선에서 빠지는 지선: 안동댐은 낙동강 시작점이지만 국토종주 본선(새재→상풍교)에는 포함되지 않음
OFF_CHAIN = {"안동댐"}
SPURS = [("안동댐", "상풍교", "낙동강 지선 (안동댐→상풍교)")]


def load_data() -> pd.DataFrame:
    df = pd.read_csv(BASE / "centers.csv")
    cfg = json.loads((BASE / "completed.json").read_text(encoding="utf-8"))
    df["done"] = (
        df["group"].isin(cfg.get("completed_groups", []))
        | df["route"].isin(cfg.get("completed_routes", []))
        | df["name"].isin(cfg.get("completed_centers", []))
    )
    df["route_ord"] = pd.factorize(df["route"])[0]  # CSV에 적힌 순서 유지
    df["group_ord"] = df["group"].map({g: i for i, g in enumerate(GROUP_ORDER)}).fillna(99)
    return df.sort_values(["group_ord", "route_ord", "seq"]).reset_index(drop=True)


def build_paths(df: pd.DataFrame):
    """(이름, 순서대로 정렬된 센터 목록) 형태의 연결선 목록을 만든다."""
    paths, used = [], set()
    for label, routes in CHAINS.items():
        sub = pd.concat([df[df["route"] == r].sort_values("seq") for r in routes])
        sub = sub[~sub["name"].isin(OFF_CHAIN)]
        paths.append((label, sub))
        used.update(routes)
    for route, g in df.groupby("route", sort=False):
        if route not in used:
            paths.append((route, g.sort_values("seq")))
    for a, b, label in SPURS:
        if {a, b} <= set(df["name"]):
            sub = df.set_index("name").loc[[a, b]].reset_index()
            paths.append((label, sub))
    return paths


def build_map(df: pd.DataFrame, view: pd.DataFrame, show_lines: bool = True) -> folium.Map:
    """df: 전체 데이터(연결선 계산용), view: 화면에 표시할 센터."""
    m = folium.Map(location=[36.3, 127.8], zoom_start=7, tiles="OpenStreetMap")
    Fullscreen().add_to(m)
    shown = set(view["name"])

    if show_lines:
        for label, sub in build_paths(df):
            rows = sub.to_dict("records")
            for p, q in zip(rows, rows[1:]):
                if p["name"] not in shown or q["name"] not in shown:
                    continue
                done = bool(p["done"] and q["done"])
                folium.PolyLine(
                    [[p["lat"], p["lon"]], [q["lat"], q["lon"]]],
                    color=DONE_COLOR if done else TODO_COLOR,
                    weight=5 if done else 3,
                    opacity=0.9 if done else 0.6,
                    dash_array=None if done else "6",
                    tooltip=f"{label}: {p['name']} → {q['name']}",
                ).add_to(m)

    cluster = MarkerCluster(disableClusteringAtZoom=10).add_to(m)
    for r in view.itertuples():
        status = "✅ 완료" if r.done else "⬜ 미완료"
        popup = (
            f"<b>{r.name}</b><br>{GROUP_LABEL.get(r.group, r.group)}<br>{r.route}<br>"
            f"{r.kind}인증센터<br>{status}"
            + ("<br><i>좌표 근사치</i>" if r.coord_status == "approx" else "")
        )
        folium.Marker(
            [r.lat, r.lon],
            tooltip=f"{r.name} ({status})",
            popup=folium.Popup(popup, max_width=260),
            icon=folium.Icon(color="red" if r.done else "gray", icon="check" if r.done else "flag", prefix="fa"),
        ).add_to(cluster)

    legend = f"""
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 9999;
                background: white; padding: 10px 14px; border-radius: 8px;
                box-shadow: 0 1px 6px rgba(0,0,0,.3); font-size: 13px;">
      <b>범례</b><br>
      <span style="color:{DONE_COLOR}; font-weight:bold">━</span> 완주한 구간 / 인증센터<br>
      <span style="color:{TODO_COLOR}">┅</span> 남은 구간 / 인증센터
    </div>"""
    m.get_root().html.add_child(folium.Element(legend))
    return m


def main():
    st.set_page_config(page_title="그랜드슬램 인증센터 지도", page_icon="🚲", layout="wide")
    st.title("🚲 그랜드슬램 인증센터 지도")

    df = load_data()

    with st.sidebar:
        st.header("필터")
        group_opts = [g for g in GROUP_ORDER if g in set(df["group"])]
        picked_groups = st.multiselect(
            "그랜드슬램 구간", group_opts, default=group_opts, format_func=lambda g: GROUP_LABEL.get(g, g)
        )
        route_opts = (
            df[df["group"].isin(picked_groups)].drop_duplicates("route")["route"].tolist()
        )
        picked_routes = st.multiselect("세부 자전거길(구간별)", route_opts, default=route_opts)
        status = st.radio("상태", ["전체", "완료", "미완료"], horizontal=True)
        show_lines = st.checkbox("자전거길 연결선 표시(센터 간 직선)", value=True)

    view = df[df["route"].isin(picked_routes)]
    if status == "완료":
        view = view[view["done"]]
    elif status == "미완료":
        view = view[~view["done"]]

    total, done = len(df), int(df["done"].sum())
    c1, c2, c3 = st.columns(3)
    c1.metric("전체 인증센터", total)
    c2.metric("완료", done)
    c3.metric("진행률", f"{done / total:.0%}")

    main_routes = df[df["route"].isin(CHAINS[MAIN_LABEL])]
    if main_routes["done"].all():
        st.success("🎉 국토종주 완주! 인천 아라서해갑문 → 부산 낙동강하굿둑")

    summary = (
        df.groupby(["group", "route"], sort=False)
        .agg(센터수=("name", "count"), 완료=("done", "sum"))
        .reset_index()
    )
    summary["그랜드슬램"] = summary["group"].map(lambda g: GROUP_LABEL.get(g, g))
    summary["상태"] = summary.apply(
        lambda r: "✅ 완주" if r["완료"] == r["센터수"] else ("진행 중" if r["완료"] else "진행 전"), axis=1
    )
    summary = summary.rename(columns={"route": "자전거길(구간)"})
    st.dataframe(
        summary[["그랜드슬램", "자전거길(구간)", "센터수", "완료", "상태"]],
        use_container_width=True,
        hide_index=True,
    )

    if view.empty:
        st.info("조건에 맞는 인증센터가 없습니다.")
    else:
        st_folium(build_map(df, view, show_lines), height=650, use_container_width=True, returned_objects=[])

    st.caption(
        "좌표는 근사치(coord_status=approx)입니다. 정확한 위치는 centers.csv에서 수정하세요. "
        "공식 정보: https://www.bike.go.kr"
    )


if __name__ == "__main__":
    main()
