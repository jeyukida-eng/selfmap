# Round 2 수정목록

모드: reference photos (indoor museum replica: background/lighting excluded). 총점(가중 평균) **63.4** / 100 (Δ +3.4 vs round1). 형식: `[ID] [담당] [우선순위] 문제 → 수정 지시 → 기대 효과`. 렌더 시간 대비 효과 큰 순.

| 뷰 | silhouette | detail | material | lighting | composition | environment | 총점 | Δ총점 |
|---|---|---|---|---|---|---|---|---|
| bow34 | 69.5 (-8.5) | 71.0 (+16.0) | 63.0 (+18.0) | 45.0 (+5.0) | 70.8 (-8.0) | 62.0 (+12.0) | 65.1 | +6.2 |
| side | 67.9 (-9.9) | 62.8 (+7.8) | 31.2 (-18.8) | 38.0 (-22.0) | 59.6 (-7.6) | 58.0 (+18.0) | 54.2 | -5.0 |
| stern34 | 72.2 (-12.0) | 82.2 (+24.2) | 57.5 (+5.5) | 62.0 (+0.0) | 62.4 (-16.6) | 60.0 (+15.0) | 67.4 | +3.5 |
| aerial | 78.2 (-4.2) | 67.2 (+22.2) | 61.1 (+21.1) | 50.0 (+0.0) | 70.2 (-8.8) | 65.0 (+15.0) | 67.0 | +9.0 |

정량: bow34 refIoU 0.570 / designIoU 0.932 / edge 1.25 / ΔE albedo 9.6 display 21.5; side refIoU 0.610 / designIoU 0.897 / edge 1.481 / ΔE albedo 31.8 display 45.5; stern34 refIoU 0.693 / designIoU 0.959 / edge 1.006 / ΔE albedo 18.8 display 11.4; aerial refIoU 0.772 / designIoU 0.970 / edge 1.379 / ΔE albedo 14.3 display 28.2

> round1 은 참고 사진 없이 설계 투영만으로 채점, 카메라도 설계 v1(안벽 구도). round2 은 사진 기준·카메라 v2 — Δ 는 같은 축 정의의 점수 차이일 뿐 같은 화면 비교가 아님.

- 고유색 [정량]: 렌더 알베도(DiffCol)와 사진 추정 알베도(흰 벽 WB, 0.8 가정)의 ΔE 는 bow34 7–14(목재), side/aerial 목재 16–29(채도 C* −13 ~ −26), 돛 L* −6 ~ −40, 개판 L* −12 ~ −27(사진은 차가운 회청 슬레이트). → 목재 채도·돛/개판 명도가 낮음.
- 보이는 색 [정량]: 렌더 beauty 의 배 영역 색은 WB 사진 대비 ΔE 21–47, ΔL* −7 ~ −48, ΔC* −13 ~ −41 (stern34 순광면만 ΔE 11). 관찰대로 '어두운 저채도 갈색' 확인 — 원인의 대부분은 알베도보다 조명(보이는 면이 그늘: sun 200°/35° 에서 bow34 좌현·선수, side 우현, aerial 선수면이 음영)과 노출.
- 실루엣 [정량]: 사진 다각형 IoU 0.57/0.61/0.69/0.77 (bow34/side/stern34/aerial; 수중 선체·돛·삭구 제외), 설계 투영 IoU 0.90–0.97. 사진 IoU 한계의 큰 부분은 실내 거치(수면 없음, 저판까지 보임)와 카메라 근사(bow34 눈높이 대체).
- 엣지 밀도(배 영역, 자기 정규화) 렌더/사진 = 1.25/1.48/1.01/1.38 — 렌더가 오히려 엣지가 많음(철첨·육각 홈). 사진의 촘촘한 목재 이음·나무못 같은 '작은 저대비 디테일'은 부족하고, 고대비 큰 디테일은 과함.

## P1

- **[A1] [담당: materials] [P1]** 고유색이 사진보다 어둡고 저채도: 목재 알베도 sRGB≈(90,60,40) vs 사진 추정 (117,42,19)~(149,73,32) (C* −13~−26, side/aerial); 돛 (152,130,100) vs (191,138,88)~(208,166,127) (L* −6~−40); 개판 (57,54,49) vs (85,82,88)~(115,118,125) (L* −12~−27, 사진은 차가운 회청).  
  → matlib.py: hull_wood·wall_panel 기본색을 sRGB (140,68,30)(선형 ≈0.26,0.058,0.012) 중심 ±15% 결 변이로, 물때·오염 mix 비율 30%↓; sail_cloth 기본색 sRGB (205,165,115)(선형 ≈0.61,0.38,0.17) + Translucent 0.2 mix(역광 시 빛 투과); roof_shell 판 색 sRGB (95,95,102) 회청, 홈은 현행 유지.  
  → 기대 효과: 알베도 ΔE 평균 15–30 → <10 목표, 보이는 색도 동반 상승. 렌더 시간 무관.
- **[L1] [담당: materials] [P1]** 보이는 색 ΔL* −7~−48 / ΔC* −13~−41: 그늘면이 하늘빛만 받아 회색으로 죽음(배가 하늘 앞 실루엣).  
  → world.py: setup_world exposure_bias +0.6, sky(Background) strength 1.0→1.6(그늘면 보조광) 또는 약한 반구 fill(Sun 반대 방향, 0.15×, 그림자 없음); setup_render look 'AgX - Base Contrast'. 렌더 후 stern34 순광면 휘도가 클리핑되지 않는지 확인.  
  → 기대 효과: 그늘면 ΔL* 절반 이하, lighting·material 축 +10. 렌더 시간 무관.
- **[D1] [담당: design] [P1]** sun 200°/35° 에서 4뷰 중 3뷰(bow34 좌현·선수, side 우현, aerial 선수면)의 보이는 면이 음영 — 사진(실내 확산광)과 가장 큰 차이.  
  → geobukseon_design.json views[*] 에 뷰별 'sun': {azimuth_deg, elevation_deg} 추가(카메라 방위 기준 해가 카메라 뒤 30–50° 옆): bow34 {300,40}, side {110,40}, stern34 {160,40}, aerial {20,50}; 전역 sun 은 flythrough 용으로 유지. render_views.py 는 다음 라운드에서 view['sun'] 이 있으면 world.setup_world 를 뷰마다 재호출하도록 지원(검증 측 작업). final/render_still.py 도 동일 키 사용.  
  → 기대 효과: 모든 스틸에서 주제면 측광·순광 → 보이는 색 ΔE 대폭 감소, lighting +15. 렌더 시간 무관.
- **[M1] [담당: modeling] [P1]** 용두 목이 고리 띠 두른 파이프, 머리가 작고 회색 도마뱀형(사진 용두 IoU 0.34/0.55). 사진은 굵고 조각된 검은 목·크게 벌린 입·흰 송곳니·뿔.  
  → build_scene.py build_dragon(): 목을 원통+링 대신 단면 반경 0.38(밑)→0.26(위) 테이퍼 + 앞으로 S자(neck_lean_deg 분포) 휘는 tube, 등 쪽 지느러미 돌기 7–9개(높이 0.08–0.15), 비늘 띠는 링 대신 변위(noise) 0.02 m; 머리 단면 폭을 JSON width 0.8 에 맞추고 입 벌림 mouth_open 0.3 실제 반영, 송곳니 4개(길이 0.15, 흰색) 앞으로. 재질은 dragon_head 를 흑칠+적색 입안·흰 이빨로(materials 협조).  
  → 기대 효과: bow34·aerial 주인공 요소가 사진처럼 읽힘, 용두 IoU 0.6+ 기대. 폴리 증가 소.
- **[M2] [담당: modeling] [P1]** 세운 돛에 아딧줄(sheet)·버팀줄이 생략 — 사진의 돛 뒤 부채꼴 줄 다발이 없어 돛이 판자처럼 보임.  
  → build_rigging(): 각 batten 뒤끝에서 2–3개씩 묶어 한 점(선미 쪽 갑판 y−4~−8, 활대 수만큼)으로 모이는 sheet 다발(rope_curve, 반지름 0.012, 처짐 sag 0.05), 돛대 꼭대기→선수/선미 앞뒤 stay 각 1, 돛대 좌우 shroud 2쌍 복원(라운드1에 있던 것). parrel 은 유지.  
  → 기대 효과: 돛·삭구 실루엣이 사진과 일치, detail +5. 곡선 수십 개 → 렌더 영향 미미.
- **[M3] [담당: modeling] [P1]** 원형 방패 문양 안 포혈의 사각 상자 테가 크고 투박(bow34·side 근경에서 가장 눈에 띄는 오차). 사진은 원판 중앙의 작은 둥근 구멍.  
  → build_wall(): 원형 문양(WallRoundels) 안 포혈을 지름 0.18–0.22 m 원형 개구 + 두께 0.03 m 얇은 철테(WallIronFittings 재질)로 교체, 사각 PortFrames 는 원형 문양 없는 위치에만 두께 0.04 m 로 축소; 뒤쪽 어두운 공동(PortCavities) 유지.  
  → 기대 효과: 방패판이 사진의 원형 문양 패턴처럼 정돈됨. 폴리 변화 소.

## P2

- **[T1] [담당: materials] [P2]** Cycles 경고 'Maximum number of closures exceeded: 68 > 64' (매 렌더) — 일부 재질의 BSDF 가 잘려 음영이 틀릴 수 있음.  
  → matlib.py: Mix Shader 체인이 긴 재질(roof_shell·hull_wood·water 후보)을 Principled 하나 + 색/거칠기 Mix(값 수준 혼합)로 재구성, 재질당 BSDF ≤ 8. preview_matlib.py 로 경고 사라짐 확인.  
  → 기대 효과: 음영 오류 제거·셰이딩 속도 소폭 향상.
- **[T2] [담당: materials] [P2]** 사진의 작은 저대비 디테일 부족: 선체 판재 나무못 점열, 방패판 원형 문양 사이 검은 나비형 모서리 철물, 판재 이음.  
  → hull_wood: Object 좌표 기반 Voronoi(scale 1/0.3 m, 판 폭 간격) 점 마스크로 지름 3 cm 진한 나무못, 판 이음 선(plank_width 0.3) 홈; wall_panel: 원형 문양 사이(panel_width 0.9 m 주기) 마름모/나비형 흑색 패치(크기 0.35 m) — 또는 modeling 이 얇은 판으로.  
  → 기대 효과: 근경 사실감 상승, detail +5. 렌더 무관.
- **[T3] [담당: materials] [P2]** 돛 면에 타원형 누빔(베개) 음영이 활대 칸마다 반복돼 인공적(stern34).  
  → sail_cloth: 칸별 타원 bump 제거, 대신 마포 직조 노이즈(scale 400/m, bump 0.05) + 활대 사이 완만한 처짐 음영(Object z 주기 = 활대 간격, 진폭 작게) + 얼룩 10%.  
  → 기대 효과: 돛이 천처럼 보임. 렌더 무관.
- **[D2] [담당: design] [P2]** stern34: 사진은 배가 좌하단을 크게 채우는데 렌더는 작고 하단 35% 빈 물. side: 선미 꼬리재가 왼쪽 프레임에 잘림(bbox x=0).  
  → views.stern34: lens 43→50, look_at z 0.74→0.2(배를 아래로); views.side: lens 26→24 또는 cam 을 +Y 쪽으로 1 m.  
  → 기대 효과: composition +10(stern34), 꼬리재 프레임 안. 렌더 무관.

## P3

- **[M4] [담당: modeling] [P3]** 용두 아래 선수 귀면이 그늘·작아서 4뷰 모두 거의 안 보임(사진에서는 선수 상장 아래 귀면 안내판 영역).  
  → D1 의 뷰별 해로 해결되는지 우선 확인. 그래도 약하면 GhostFace 부조 깊이 ×1.5, 크기 JSON 그대로.  
  → 기대 효과: 선수 디테일 회복(소).

