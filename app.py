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
import streamlit.components.v1 as components
from branca.element import MacroElement
from folium.plugins import Fullscreen, MarkerCluster
from jinja2 import Template
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
GROUP_SHORT = {
    "국토종주": "국토종주",
    "4대강": "4대강 추가구간",
    "북한강": "북한강",
    "섬진강": "섬진강",
    "동해안": "동해안",
    "제주환상": "제주환상",
    "오천": "오천",
}
COMPACT_CSS = """
<style>
.st-key-route_table [data-testid="stVerticalBlock"] { gap: 0.1rem; }
.st-key-route_table [data-testid="stHorizontalBlock"] { gap: 0; align-items: stretch; }
.st-key-route_table [data-testid="stColumn"], .st-key-route_table [data-testid="column"] {
    padding: 3px 8px; display: flex; align-items: center;
}
.st-key-route_table p { margin: 0; font-size: 0.85rem; line-height: 1.25; }
.st-key-route_table button { min-height: 1.6rem; padding: 0 0.5rem; }
.st-key-route_table button p { font-size: 0.8rem; }
.route-hdr { font-weight: 800; color: #2563eb; }
.group-sep { border-top: 3px solid rgba(37,99,235,.55); margin: 2px 0 0; }
</style>
"""
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


START_BUTTON_HTML = """
<style>
html, body { margin: 0; background: transparent; font-family: sans-serif; }
button { background: #16a34a; color: #fff; border: none; border-radius: 10px; padding: 9px 22px;
         font-size: 16px; font-weight: 800; cursor: pointer; box-shadow: 0 1px 4px rgba(0,0,0,.3); }
button:hover { background: #15803d; }
</style>
<button id="b">▶ Start</button>
<script>
document.getElementById("b").onclick = function () {
  var f = window.parent.frames;
  for (var i = 0; i < f.length; i++) {
    try { f[i].postMessage({type: "dadson-start"}, "*"); } catch (e) {}
  }
  this.textContent = "↻ 다시 Start";
};
</script>
"""


RIDER_JS = """
(function () {
  var tries = 0;
  function boot() {
    if (typeof __MAP__ === "undefined") {   // 지도가 만들어질 때까지 기다린다
      if (tries++ < 400) setTimeout(boot, 50);
      return;
    }
    var map = __MAP__;
    var pts = __PTS__;
    var names = __NAMES__;

    var style = document.createElement("style");
    style.textContent =
      ".dadson{background:none;border:none;}" +
      ".dadson-inner{display:flex;align-items:center;justify-content:center;gap:14px;width:100%;height:100%;" +
      "white-space:nowrap;line-height:1;filter:drop-shadow(0 3px 3px rgba(0,0,0,.35));cursor:pointer;}" +
      ".dadson-rider{position:relative;display:flex;align-items:center;" +
      "animation:dadson-bob .45s ease-in-out infinite alternate;}" +
      ".dadson-rider.son{animation-delay:.2s;}" +
      ".dadson-bubble{position:absolute;bottom:100%;left:50%;transform:translateX(-50%);margin-bottom:9px;" +
      "background:#fffbea;color:#111;border:2px solid #f59e0b;border-radius:12px;padding:1px 8px;" +
      "font:800 12px/1.3 sans-serif;}" +
      ".dadson-bubble:after{content:'';position:absolute;left:50%;bottom:-8px;margin-left:-5px;" +
      "border:5px solid transparent;border-top-color:#f59e0b;border-bottom:0;}" +
      ".dadson-emoji{display:inline-block;font-size:42px;transform:scaleX(-1);}" +   /* 오른쪽이 앞 */
      ".dadson-rider.son .dadson-emoji{font-size:31px;}" +
      ".dadson.faceleft .dadson-emoji{transform:none;}" +                            /* 서쪽으로 갈 때는 왼쪽이 앞 */
      "@keyframes dadson-bob{from{transform:translateY(0);}to{transform:translateY(-4px);}}" +
      ".dadson-tip{font-weight:700;font-size:12px;border-radius:10px;}";
    document.head.appendChild(style);

    var cum = [0];
    for (var i = 1; i < pts.length; i++) {
      cum.push(cum[i - 1] + map.distance(pts[i - 1], pts[i]));
    }
    var total = cum[cum.length - 1];

    // 자전거의 한가운데가 국토종주 라인 위에 오도록 기준점을 아이콘 중앙에 둔다
    var icon = L.divIcon({
      className: "dadson",
      html: '<div class="dadson-inner">' +
            '<div class="dadson-rider dad"><div class="dadson-bubble">Han</div><span class="dadson-emoji">🚴‍♂️</span></div>' +
            '<div class="dadson-rider son"><div class="dadson-bubble">Cool Choi</div><span class="dadson-emoji">🚴</span></div>' +
            '</div>',
      iconSize: [87, 46], iconAnchor: [43, 23]
    });
    var marker = L.marker(pts[0], {icon: icon, zIndexOffset: 1000}).addTo(map);
    var READY = "인천 " + names[0] + " 출발 준비! ▶ Start를 눌러요";
    marker.bindTooltip(READY, {permanent: true, direction: "bottom", offset: [0, 26], className: "dadson-tip"});

    var duration = 22500, startTs = null, req = null, lastText = "", faceLeft = false;
    function segIndex(d) {
      var i = 1;
      while (i < cum.length - 1 && cum[i] < d) i++;
      return i;
    }
    function position(d) {
      var i = segIndex(d);
      var seg = cum[i] - cum[i - 1] || 1;
      var t = Math.min(Math.max((d - cum[i - 1]) / seg, 0), 1);
      return [pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * t,
              pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * t];
    }
    function passed(d) {
      var k = 0;
      for (var i = 0; i < cum.length; i++) { if (cum[i] <= d + 1) k = i; }
      return k;
    }
    function step(ts) {
      if (startTs === null) startTs = ts;
      var p = Math.min((ts - startTs) / duration, 1);
      var d = p * total;
      marker.setLatLng(position(d));
      var i = segIndex(d), west = pts[i][1] < pts[i - 1][1];
      if (west !== faceLeft) {
        faceLeft = west;
        var el = marker.getElement();
        if (el) el.classList.toggle("faceleft", faceLeft);
      }
      var k = passed(d), text;
      if (p >= 1) text = "🎉 " + names[names.length - 1] + " 도착!";
      else if (k === 0) text = "출발! " + names[0];
      else text = "📍 " + names[k] + " 통과";
      if (text !== lastText) { marker.setTooltipContent(text); lastText = text; }
      if (p < 1) req = requestAnimationFrame(step);
    }
    function start() {
      if (req) cancelAnimationFrame(req);
      startTs = null;
      req = requestAnimationFrame(step);
    }

    // 지도 제목 옆의 Start 버튼이 보내는 신호를 받는다 (자전거를 직접 눌러도 출발)
    window.addEventListener("message", function (ev) {
      if (ev.data && ev.data.type === "dadson-start") start();
    });
    marker.on("click", start);
  }
  boot();
})();
"""


class Rider(MacroElement):
    """아빠와 아들 자전거 애니메이션. 지도의 자식 요소(MacroElement)여야 st_folium이 스크립트를 실행한다."""

    _template = Template(
        "{% macro script(this, kwargs) %}"
        + RIDER_JS.replace("__MAP__", "{{ this._parent.get_name() }}")
        .replace("__PTS__", "{{ this.pts }}")
        .replace("__NAMES__", "{{ this.names }}")
        + "{% endmacro %}"
    )

    def __init__(self, pts, names):
        super().__init__()
        self._name = "Rider"
        self.pts = json.dumps(pts)
        self.names = json.dumps(names, ensure_ascii=False)


def add_rider(m: folium.Map, df: pd.DataFrame, shown: set):
    """인천 아라서해갑문 → 부산 낙동강하굿둑까지 아빠와 아들이 자전거로 달리는 애니메이션(Start 버튼)."""
    main = next((sub for label, sub in build_paths(df) if label == MAIN_LABEL), None)
    if main is None or not set(main["name"]) <= shown:
        return
    m.add_child(Rider(main[["lat", "lon"]].values.tolist(), main["name"].tolist()))


def km_totals(df: pd.DataFrame):
    """(전체 km, 완료 누적 km). 국토종주는 공식 총거리(633km) 기준으로 맞춘다."""
    total_km = done_km = 0.0
    for group, g in df.groupby("group"):
        r = g.groupby("route", sort=False).agg(km=("km", "first"), n=("name", "count"), d=("done", "sum"))
        base = r["km"].sum()
        factor = GROUP_KM[group] / base if group in GROUP_KM and base else 1.0
        total_km += base * factor
        done_km += (r["km"] * r["d"] / r["n"]).sum() * factor
    return total_km, done_km


def stat_cards(total: int, done: int, total_km: float, done_km: float) -> str:
    items = [
        ("전체 인증센터", f"{total}", f"전체 {total_km:,.0f}km", "#2563eb", "37,99,235"),
        ("완료", f"{done}", f"누적 {done_km:,.0f}km", "#dc2626", "220,38,38"),
        ("진행률", f"{done / total:.0%}", "", "#16a34a", "22,163,74"),
    ]
    cards = "".join(
        f'<div style="flex:1; min-width:150px; border-left:6px solid {c}; background:rgba({rgb},.12);'
        f' border-radius:10px; padding:10px 18px;">'
        f'<div style="font-size:14px; opacity:.85;">{label}</div>'
        f'<div style="font-size:34px; font-weight:800; color:{c}; line-height:1.2;">{value}'
        f'<span style="font-size:16px; font-weight:700; margin-left:10px;">{sub}</span></div></div>'
        for label, value, sub, c, rgb in items
    )
    return f'<div style="display:flex; gap:14px; flex-wrap:wrap; margin:6px 0 18px;">{cards}</div>'


def km_text(km) -> str:
    return "" if pd.isna(km) else f"{km:g}km"


def build_map(df: pd.DataFrame, view: pd.DataFrame, show_lines: bool = True, animate: bool = True) -> folium.Map:
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
            ).add_to(m)
        # 2) 완료 구간: 붉은색 실선을 위에 덧그림
        for p, q, done in segments:
            if done:
                folium.PolyLine(
                    [[p["lat"], p["lon"]], [q["lat"], q["lon"]]],
                    color=DONE_COLOR, weight=5, opacity=0.9,
                ).add_to(m)
        # 3) 눈에 보이지 않는 넓은 반응 영역: 선 근처에 마우스를 가져가면 설명 박스 표시
        for p, q, done in segments:
            folium.PolyLine(
                [[p["lat"], p["lon"]], [q["lat"], q["lon"]]],
                color="#000000", weight=26, opacity=0.01,
                tooltip=folium.Tooltip(tip(p, q, done), sticky=True),
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
    if animate:
        add_rider(m, df, shown)
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
        animate = st.checkbox("🚴 아빠와 아들 자전거 애니메이션", value=True)

    view = df[df["route"].isin(picked_routes)]
    if status == "완료":
        view = view[view["done"]]
    elif status == "미완료":
        view = view[~view["done"]]

    total, done = len(df), int(df["done"].sum())
    total_km, done_km = km_totals(df)
    st.markdown(stat_cards(total, done, total_km, done_km), unsafe_allow_html=True)

    title_col, start_col = st.columns([1.8, 8.2], vertical_alignment="center")
    title_col.markdown("#### 🗺️ 국토종주 지도")
    with start_col:
        if animate:
            if hasattr(st, "iframe"):  # 최신 Streamlit
                st.iframe(START_BUTTON_HTML.strip(), height=48)
            else:  # 이전 버전 호환
                components.html(START_BUTTON_HTML, height=48)
    if view.empty:
        st.info("조건에 맞는 인증센터가 없습니다.")
    else:
        st_folium(build_map(df, view, show_lines, animate), height=650, use_container_width=True, returned_objects=[])


    # ---- 구간별 현황 표 (왼쪽) + 상세루트 (오른쪽) : 한 화면에 보이도록 촘촘하게 ----
    st.markdown(COMPACT_CSS, unsafe_allow_html=True)
    st.markdown(
        '#### 그랜드슬램 구간별 현황 '
        f'<span style="font-size:1rem; font-weight:700; color:{DONE_COLOR}; margin-left:12px;">완료 누적 {done_km:,.0f}km</span>'
        f'<span style="font-size:1rem; font-weight:600; color:{TODO_COLOR}; margin-left:8px;">/ 전체 {total_km:,.0f}km</span>',
        unsafe_allow_html=True,
    )
    left, right = st.columns([3.3, 2], gap="medium")

    with left:
        widths = [1.7, 3.0, 0.8, 0.9, 1.1, 1.0]
        with st.container(key="route_table", border=True):
            for col, title in zip(st.columns(widths), ["그랜드슬램", "자전거길(구간)", "센터", "길이", "상태", "상세"]):
                col.markdown(f'<div class="route-hdr">{title}</div>', unsafe_allow_html=True)
            for group in group_opts:
                g = df[df["group"] == group]
                first = True
                st.markdown('<div class="group-sep"></div>', unsafe_allow_html=True)
                for route, r in g.groupby("route", sort=False):
                    cols = st.columns(widths, vertical_alignment="center")
                    if first:
                        label = GROUP_SHORT.get(group, group)
                        if group in GROUP_KM:
                            label += f" {GROUP_KM[group]}km"
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

    with right:
        detail = st.session_state.get("detail")
        if detail and (df["route"] == detail).any():
            r = df[df["route"] == detail].sort_values("seq")
            seg = segment_km(r, detail)
            st.markdown(f"**{detail}** · 센터 {len(r)}개 · {km_text(r['km'].iloc[0])}")
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
                height=min(38 + 35 * len(r), 470),
            )
            st.caption("센터 간 거리는 직선거리 비율로 나눈 추정값입니다.")
        else:
            st.info("왼쪽 표의 '상세루트' 버튼을 누르면 해당 구간의 인증센터가 여기에 나옵니다.")

    st.caption(
        "인증센터 이름·길이는 자전거 행복나눔(https://www.bike.go.kr) 안내를 따랐고, "
        "누적·전체 km는 국토종주 공식 633km와 각 자전거길 길이 합계 기준입니다. "
        "좌표는 근사치(coord_status=approx)입니다. 정확한 위치는 centers.csv에서 수정하세요."
    )


if __name__ == "__main__":
    main()
