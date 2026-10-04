"""쿨초이와 함께하는 자전거 여행 - 그랜드슬램 인증센터 지도.

- centers.csv   : 인증센터 목록 (좌표 포함)
- routes.csv    : 자전거길별 길이(km)
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
DONE_COLOR = "#dc2626"   # 완료: 붉은색 실선
TODO_COLOR = "#2563eb"   # 전체(남은) 구간: 푸른색 점선

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
GROUP_KM = {"국토종주": 633}  # 국토종주 전체 거리(km)

# 인증 완료 박스: (제목, 필요한 그랜드슬램 구간, 설명)
CERTS = [
    ("국토종주 인증 완료", ["국토종주"], "인천 아라서해갑문 → 부산 낙동강하굿둑"),
    ("4대강 인증 완료", ["국토종주", "4대강"], "국토종주 + 금강 + 영산강"),
]

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
LOOPS = {"제주환상자전거길"}  # 마지막 센터에서 처음 센터로 되돌아와 한 바퀴를 닫는 길
# 안동댐은 낙동강 시작점이지만 국토종주 본선(새재→상주상풍교)에는 포함되지 않는 지선
OFF_CHAIN = {"안동댐"}
SPURS = [("안동댐", "상주상풍교", "낙동강 지선 (안동댐→상풍교)")]


def load_data() -> pd.DataFrame:
    df = pd.read_csv(BASE / "centers.csv")
    routes = pd.read_csv(BASE / "routes.csv")
    cfg = json.loads((BASE / "completed.json").read_text(encoding="utf-8"))

    df["done"] = (
        df["group"].isin(cfg.get("completed_groups", []))
        | df["route"].isin(cfg.get("completed_routes", []))
        | df["name"].isin(cfg.get("completed_centers", []))
    )
    df["km"] = df["route"].map(routes.set_index("route")["km"])
    df["route_n"] = df.groupby("route")["name"].transform("count")
    df["route_ord"] = df["route"].map({r: i for i, r in enumerate(routes["route"])}).fillna(99)
    df["group_ord"] = df["group"].map({g: i for i, g in enumerate(GROUP_ORDER)}).fillna(99)
    return df.sort_values(["group_ord", "route_ord", "seq"]).reset_index(drop=True)


def build_paths(df: pd.DataFrame):
    """(이름, 순서대로 정렬된 센터 목록) 형태의 연결선 목록을 만든다."""
    paths, used = [], set()
    for label, routes in CHAINS.items():
        sub = pd.concat([df[df["route"] == r].sort_values("seq") for r in routes])
        paths.append((label, sub[~sub["name"].isin(OFF_CHAIN)]))
        used.update(routes)
    for route, g in df.groupby("route", sort=False):
        if route in used:
            continue
        sub = g.sort_values("seq")
        if route in LOOPS:
            sub = pd.concat([sub, sub.iloc[[0]]])
        paths.append((route, sub))
    for a, b, label in SPURS:
        if {a, b} <= set(df["name"]):
            paths.append((label, df.set_index("name").loc[[a, b]].reset_index()))
    return paths


def km_text(km) -> str:
    return "" if pd.isna(km) else f"{km:g}km"


def build_map(df: pd.DataFrame, view: pd.DataFrame, show_lines: bool = True) -> folium.Map:
    """df: 전체 데이터(연결선 계산용), view: 화면에 표시할 센터."""
    m = folium.Map(location=[36.3, 127.8], zoom_start=7, tiles="OpenStreetMap")
    Fullscreen().add_to(m)
    shown = set(view["name"])

    if show_lines:
        segments = []
        for label, sub in build_paths(df):
            rows = sub.to_dict("records")
            for p, q in zip(rows, rows[1:]):
                if p["name"] in shown and q["name"] in shown:
                    segments.append((p, q, bool(p["done"] and q["done"])))

        def tip(p, q, done):
            return (
                f"<b>{q['route']}</b>{' (완료)' if done else ''}<br>"
                f"구간 길이 {km_text(q['km'])} · 인증센터 {int(q['route_n'])}개<br>"
                f"{p['name']} → {q['name']}"
            )

        # 1) 전체 구간: 푸른색 점선
        for p, q, done in segments:
            folium.PolyLine(
                [[p["lat"], p["lon"]], [q["lat"], q["lon"]]],
                color=TODO_COLOR, weight=3, opacity=0.8,
                dash_array="2 8", line_cap="round",
                tooltip=tip(p, q, done),
            ).add_to(m)
        # 2) 완료 구간: 붉은색 실선을 위에 덧그림
        for p, q, done in segments:
            if done:
                folium.PolyLine(
                    [[p["lat"], p["lon"]], [q["lat"], q["lon"]]],
                    color=DONE_COLOR, weight=5, opacity=0.9,
                    tooltip=tip(p, q, done),
                ).add_to(m)

    cluster = MarkerCluster(disableClusteringAtZoom=10).add_to(m)
    for r in view.itertuples():
        status = "✅ 완료" if r.done else "⬜ 미완료"
        popup = (
            f"<b>{r.name}</b><br>{r.route} ({km_text(r.km)})<br>"
            f"{GROUP_LABEL.get(r.group, r.group)}<br>{r.kind}인증센터<br>{status}"
            + ("<br><i>좌표 근사치</i>" if r.coord_status == "approx" else "")
        )
        folium.Marker(
            [r.lat, r.lon],
            tooltip=f"{r.name} · {r.route} ({status})",
            popup=folium.Popup(popup, max_width=260),
            icon=folium.Icon(color="red" if r.done else "blue", icon="check" if r.done else "flag", prefix="fa"),
        ).add_to(cluster)

    legend = f"""
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 9999;
                background: white; padding: 10px 14px; border-radius: 8px;
                box-shadow: 0 1px 6px rgba(0,0,0,.3); font-size: 13px;">
      <b>범례</b><br>
      <span style="color:{DONE_COLOR}; font-weight:bold">━━</span> 완료한 구간 / 인증센터<br>
      <span style="color:{TODO_COLOR}; font-weight:bold">· · ·</span> 전체 구간(점선) / 남은 인증센터
    </div>"""
    m.get_root().html.add_child(folium.Element(legend))
    return m


def cert_boxes(df: pd.DataFrame) -> str:
    boxes = []
    for title, groups, desc in CERTS:
        sub = df[df["group"].isin(groups)]
        got, total = int(sub["done"].sum()), len(sub)
        if got == total:
            style = (
                "border:2px solid #dc2626; background:rgba(220,38,38,.12); color:#dc2626;"
            )
            head, tail = f"🏅 {title}", desc
        else:
            style = (
                "border:2px dashed #9ca3af; background:rgba(156,163,175,.12); color:#6b7280;"
            )
            head, tail = f"{title.replace(' 완료', '')} 진행 중 ({got}/{total})", desc
        boxes.append(
            f'<div style="{style} border-radius:12px; padding:12px 20px; min-width:260px;">'
            f'<div style="font-size:20px; font-weight:800;">{head}</div>'
            f'<div style="font-size:13px; opacity:.85; margin-top:2px;">{tail}</div></div>'
        )
    return '<div style="display:flex; gap:14px; flex-wrap:wrap; margin:8px 0 18px;">' + "".join(boxes) + "</div>"


def route_status(r: pd.DataFrame) -> str:
    n, d = len(r), int(r["done"].sum())
    return "✅ 완주" if d == n else ("🔶 진행 중" if d else "⬜ 진행 전")


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    from math import asin, cos, radians, sin, sqrt

    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * 6371 * asin(sqrt(a))


def segment_km(r: pd.DataFrame, route: str) -> list:
    """이전 센터까지의 구간 길이(추정). 센터 간 직선거리 비율로 공식 총거리(km)를 나눈다."""
    r = r.sort_values("seq")
    pts = list(zip(r["lat"], r["lon"]))
    gaps = [haversine_km(*a, *b) for a, b in zip(pts, pts[1:])]
    total = sum(gaps) + (haversine_km(*pts[-1], *pts[0]) if route in LOOPS else 0)
    km = r["km"].iloc[0]
    if not total or pd.isna(km):
        return [None] * len(r)
    return [None] + [g * km / total for g in gaps]


def toggle_detail(route: str):
    st.session_state["detail"] = None if st.session_state.get("detail") == route else route


def main():
    st.set_page_config(page_title="그랜드슬램 인증센터 지도", page_icon="🚲", layout="wide")
    st.title("🚲 그랜드슬램 인증센터 지도")
    st.subheader("쿨초이와 함께하는 자전거 여행")

    df = load_data()
    st.markdown(cert_boxes(df), unsafe_allow_html=True)

    with st.sidebar:
        st.header("필터")
        group_opts = [g for g in GROUP_ORDER if g in set(df["group"])]
        picked_groups = st.multiselect(
            "그랜드슬램 구간", group_opts, default=group_opts, format_func=lambda g: GROUP_LABEL.get(g, g)
        )
        route_opts = df[df["group"].isin(picked_groups)].drop_duplicates("route")["route"].tolist()
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

    # ---- 구간별 현황 표 (상세루트 버튼을 누르면 해당 구간의 인증센터가 나옴) ----
    st.markdown("#### 그랜드슬램 구간별 현황")
    st.caption("'상세루트' 버튼을 누르면 해당 구간의 인증센터가 나오고, 다시 누르면 닫힙니다.")
    widths = [2.6, 3.0, 0.9, 1.1, 1.2, 1.3]
    for col, title in zip(st.columns(widths), ["그랜드슬램", "자전거길(구간)", "센터수", "길이", "상태", "상세"]):
        col.markdown(f"**{title}**")
    st.divider()

    for group in group_opts:
        g = df[df["group"] == group]
        first = True
        for route, r in g.groupby("route", sort=False):
            cols = st.columns(widths, vertical_alignment="center")
            if first:
                label = GROUP_LABEL.get(group, group)
                if group in GROUP_KM:
                    label += f" · 총 {GROUP_KM[group]}km"
                cols[0].markdown(f"**{label}**")
                first = False
            cols[1].write(route)
            cols[2].write(f"{len(r)}개")
            cols[3].write(km_text(r["km"].iloc[0]))
            cols[4].write(route_status(r))
            is_open = st.session_state.get("detail") == route
            cols[5].button(
                "닫기" if is_open else "상세루트",
                key=f"detail_{route}",
                on_click=toggle_detail,
                args=(route,),
            )
            if is_open:
                r = r.sort_values("seq")
                seg = segment_km(r, route)
                st.dataframe(
                    pd.DataFrame(
                        {
                            "순서": r["seq"].values,
                            "인증센터": r["name"].values,
                            "유형": r["kind"].values,
                            "이전 센터까지(약 km)": ["출발" if v is None else f"{v:.1f}" for v in seg],
                            "상태": ["✅ 완료" if d else "⬜ 미완료" for d in r["done"]],
                        }
                    ),
                    width="stretch",
                    hide_index=True,
                )
                st.caption(f"{route} · 센터 {len(r)}개 · 총 {km_text(r['km'].iloc[0])} (센터 간 거리는 직선거리 비율로 나눈 추정값)")
        st.divider()

    st.markdown("#### 지도")
    if view.empty:
        st.info("조건에 맞는 인증센터가 없습니다.")
    else:
        st_folium(build_map(df, view, show_lines), height=650, use_container_width=True, returned_objects=[])

    st.caption(
        "인증센터 이름·길이는 자전거 행복나눔(https://www.bike.go.kr) 안내를 따랐고, "
        "좌표는 근사치(coord_status=approx)입니다. 정확한 위치는 centers.csv에서 수정하세요."
    )


if __name__ == "__main__":
    main()
