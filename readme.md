# 🚲 Korea Cross-Country Bicycle Road

국토종주 자전거길 그랜드슬램 인증센터를 지도에 표시하고, 완료한 구간을 초록색으로 보여주는 Streamlit 앱입니다.

- 🟢 완료한 구간: 국토종주, 4대강, 북한강
- ⚪ 남은 구간: 섬진강, 동해안, 제주환상, 오천

## 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 파일 구성

| 파일 | 설명 |
| --- | --- |
| `app.py` | Streamlit + folium 지도 앱 |
| `centers.csv` | 인증센터 목록 (`route, group, seq, name, kind, lat, lon, coord_status`) |
| `completed.json` | 완료한 구간 설정 |
| `requirements.txt` | 필요한 파이썬 패키지 |

## 완료 구간 바꾸기

`completed.json`의 `completed_groups`에 구간 이름을 추가하세요.
(국토종주, 4대강, 북한강, 섬진강, 동해안, 제주환상, 오천)

개별 자전거길은 `completed_routes`, 인증센터 하나만 표시하려면 `completed_centers`를 사용합니다.

## 데이터 정확도

`centers.csv`의 좌표는 초안(근사치)입니다. 공식 목록
([자전거 행복나눔](https://www.bike.go.kr))과 비교해 `lat`, `lon`을 고치고
`coord_status`를 `verified`로 바꿔 주세요.

## 웹으로 배포하기

[Streamlit Community Cloud](https://share.streamlit.io)에서 이 저장소를 연결하고
Main file path를 `app.py`로 지정하면 무료로 배포할 수 있습니다.
