# Round 1 수정목록

모드: design-based (no reference photos available: refs/ref_*.jpg missing). 총점(가중 평균) **60.0** / 100. 형식: `[ID] [담당] [우선순위] 문제 → 수정 지시 → 기대 효과`. 렌더 시간 대비 효과 큰 순.

| 뷰 | silhouette | detail | material | lighting | composition | environment | 총점 |
|---|---|---|---|---|---|---|---|
| bow34 | 78.0 | 55.0 | 45.0 | 40.0 | 78.8 | 50.0 | 58.9 |
| side | 77.8 | 55.0 | 50.0 | 60.0 | 67.2 | 40.0 | 59.2 |
| stern34 | 84.2 | 58.0 | 52.0 | 62.0 | 79.0 | 45.0 | 63.9 |
| aerial | 82.4 | 45.0 | 40.0 | 50.0 | 79.0 | 50.0 | 58.0 |

IoU(렌더 마스크 vs 설계 투영): bow34 body 0.959/dragon 0.632, side body 0.962/dragon 0.546, stern34 body 0.963/dragon nan, aerial body 0.984/dragon 0.697

## P1

- **[L1] [담당: materials] [P1]** 선체가 전 뷰에서 어둡다([정량] 선체 평균 휘도 36–50/255, aerial 프레임 44/255). bow34는 역광이라 선수판·귀면이 검게 묻힘.  
  → materials/world.py setup_render(): vs.look 'AgX - Medium High Contrast' → 'AgX - Base Contrast'(또는 'Medium Contrast'); setup_world(): auto_exposure 유지하되 기본 exposure_bias 0.0→+0.5(현재 auto 노출식의 −0.45 오프셋 상쇄), sun_angle_deg 0.6→1.5(그림자 경계 부드럽게); aerosol_density 소폭↑ 또는 저대비 노이즈 구름 반구 추가로 단조로운 하늘 해소.  
  → 기대 효과: 선체 휘도 70–100 목표, 귀면·용두 색이 읽힘. 렌더 시간 영향 없음. lighting +15, material +5 예상.
- **[M1] [담당: modeling] [P1]** 포혈 안쪽 막음판이 없어 반대편 하늘이 비쳐 하얀 창문처럼 보임(bow34 원경 포혈).  
  → build_scene.py build_wall(): 각 side/bow/stern 포혈 개구부 뒤 0.25 m 깊이에 어두운 박스(5면, 안쪽 법선) 추가 — 재질 _simple_mat('port_dark', (0.015,0.012,0.01), rough 0.9) 또는 wall_panel 어둡게; 선택적으로 포구(지름 0.12 m 원통 끝) 하나씩.  
  → 기대 효과: 포혈이 깊이 있는 검은 구멍으로 읽혀 사실감 크게 향상. 폴리곤 +~300, 렌더 영향 무시.
- **[D1] [담당: design] [P1]** side 뷰 프레임 아래 37%가 부두 포장(배가 위 1/3 띠에 몰림), bow34/stern34/side 모두 돛대 끝·깃발이 잘림([정량] side frac_rows_below_ship 0.37).  
  → geobukseon_design.json views: side.cam [-21.5,-0.5,2.8]→[-11.5,-0.5,3.4](안벽 끝), lens 24→16, look_at z 2.0→3.6 (또는 cam 유지 + look_at [0,0,4.2]); bow34.look_at z 2.4→3.2, lens 28→24; stern34.look_at z 2.4→3.2. (카메라 shift_y 키를 추가해 모델링이 cd.shift_y로 반영하는 방식도 가능.)  
  → 기대 효과: 배가 화면 중앙 띠를 채우고 돛대·깃발이 프레임 안에 들어옴. composition +20(side), 렌더 시간 무관.
- **[M2] [담당: modeling] [P1]** 용두가 설계보다 작고 납작함([정량] 폭 0.58 m vs JSON 0.75 m, 용두 IoU 0.55–0.70). 수염 커브가 얼굴(눈·코) 위를 가로지름.  
  → build_scene.py build_dragon(): 단면 반폭/높이를 dragon_head.width/height에 맞게 스케일(현재 폭 ~77%) — superring 폭 계수에 width/0.58 보정; 주둥이 끝을 더 위로(+pitch 5°) 들고 뿔 2개(길이 0.35 m, 뒤로 휘게) 추가. DragonWhisker_L/R: 시작점을 윗입술 옆 표면점(+법선 0.04 m)으로 옮기고 경로를 뒤-바깥(±X)-아래로, 얼굴 앞을 지나지 않게.  
  → 기대 효과: bow34 주인공 요소 존재감 회복, 용두 IoU 0.8+ 기대. 폴리 증가 미미.
- **[W1] [담당: materials] [P1]** 물이 불투명한 검푸른 판처럼 보이고 선체·노·키·부두 주변 거품/접촉선이 없음. aerial에서 물결 법선이 규칙적 반복으로 보임.  
  → matlib.py water: Principled Transmission 1.0, IOR 1.333, Roughness 0.02–0.05 유지 + 볼륨 흡수(Volume Absorption 색 (0.25,0.45,0.42), density 0.25)로 얕은 곳 녹청색; 거품 = Attribute 'hull_dist'(M3에서 생성) map range 0–0.6 m → 노이즈(scale 8, detail 6) 임계값 마스크로 흰색 확산 mix; 법선 노이즈 4개 중 큰 스케일 하나의 scale을 비정수 비(×1.37)로 바꿔 반복감 제거.  
  → 기대 효과: 물/환경 +15, 배가 물에 '떠 있는' 접촉감. Cycles 투과로 렌더 +10–20%.
- **[R1] [담당: materials] [P1]** 개판 육각 무늬가 원경/조감에서 사라지고 큰 스케일 오염 노이즈 때문에 흙때처럼 보임(aerial). 근경에서는 셀이 균일한 비늘.  
  → matlib.py roof_shell: 육각 홈 선 폭 hex_cell(0.5 m)의 7–8%(≈3.5 cm)로 굵히고 홈 색 거의 흑(0.02), 홈 bump 강도 0.3; 셀별 랜덤(셀 ID 해시)로 명도 ±15%·색상 적갈↔흑갈 변이; 대형 오염 노이즈 mix factor 50% 감소, 셀 중앙은 약간 밝게(마모) 처리.  
  → 기대 효과: 조감·원경에서 거북등 육각 무늬가 대표 시각 요소로 읽힘. material/detail +10(aerial). 렌더 시간 무관.

## P2

- **[D2] [담당: design] [P2]** 철첨이 원경 잔털([정량] 지름 0.7–1.1 px, 높이 2.3–3.6 px at 960 px 폭). 0.35 m 격자라 육각 무늬와 무관하게 배치됨.  
  → geobukseon_design.json roof.spikes: base_radius 0.018→0.035, height 0.12→0.15, 배치 규칙 'hex_vertex'(hex_cell 꼭짓점) 키 추가; 모델링은 spike_nodegroup()에서 원뿔(반지름 0.035→0) + 하단 0.05 m 사각 받침판으로.  
  → 기대 효과: 철첨이 굵은 원뿔 점열로 읽혀 무늬와 같이 패턴 형성. 인스턴스 수 비슷 → 렌더 시간 무관.
- **[D3] [담당: design] [P2]** 귀면 JSON 불일치: center y 11.75는 이물비우 면(그 높이에서 y=11.83) 안쪽 0.08 m. normal_tilt_deg=+38(위로)인데 실제 이물비우 바깥 법선은 아래로 40.0°(면 경사 50.0°, 상단이 앞으로 나온 경사면).  
  → geobukseon_design.json ghost_face: center [0, 11.83, 1.3], normal_tilt_deg → -40.0 (부호 규약: +위/-아래, note에 명시) 또는 'on_surface':'bow_transom'로 바꾸고 모델링은 H.transom_normal() 사용.  
  → 기대 효과: 설계-모델 일치(현재 모델은 y 11.84로 임의 보정 중). 시각 변화 소, 계약 일관성 확보.
- **[T1] [담당: materials] [P2]** 용두 단청이 녹색 바탕+분홍 사선 띠 반복이라 사탕 줄무늬 같고, 귀면은 만화 스티커처럼 평면적·작아 보임.  
  → matlib.py dragon_head: 주기 띠 대신 Object 좌표 y(머리→목)로 구역 분할 — 주둥이·입술 주홍(0.55,0.08,0.04), 머리 녹청(0.10,0.35,0.30), 비늘 노이즈 마스크, 눈 주변·이빨 흰색, 구역 경계에 흑선 1 cm, 전체 채도 −20%·때 오염 20%. ghost_face: 바탕 흑청, 눈 흰자+주홍 테, 송곳니 백색, 눈썹·갈기 녹·청 단청, AO(Pointiness/AO 노드)로 부조 골에 어둡게.  
  → 기대 효과: 주인공 디테일의 사실감 상승(material +10 bow34). 렌더 시간 무관.
- **[M3] [담당: modeling] [P2]** 물 셰이더가 거품을 그릴 근거(물체까지 거리)가 없음.  
  → build_scene.py build_water(): Water 메시에 Geometry Nodes(Geometry Proximity: Hull·노·키·QuayFaceStones 합친 지오메트리 → Distance)로 float point attribute 'hull_dist' 저장(Store Named Attribute). ocean_res 14→18(preview)로 선체 주변 해상도 확보.  
  → 기대 효과: W1의 접촉 거품 가능. 빌드 +1–2 s.
- **[E1] [담당: materials] [P2]** 배경 산이 매끈한 모래 언덕(사막 느낌) — 통영 앞바다의 숲 덮인 섬과 다름.  
  → BackgroundHills 재질(ground 계열): 짙은 녹색(0.05,0.09,0.04) 숲 노이즈(scale 0.02/m) + 능선 암석 회색; Camera Data 거리 기반으로 하늘 색(0.55,0.65,0.78)과 mix 40–60%(대기원근); 모델링은 hill 높이 노이즈 진폭 ×1.5로 능선 불규칙.  
  → 기대 효과: side/stern34 환경 +10. 렌더 시간 무관.
- **[M4] [담당: modeling] [P2]** 부두 포장석이 같은 크기 격자 반복·석축 면이 단순해 CG 느낌(side 전경 다수).  
  → build_scene.py build_site(): 포장석 크기 0.6–1.2 m 랜덤(시드 고정), 행마다 오프셋, 각 석 높이 ±1.5 cm·기울기 ±0.5°, 줄눈 1–2 cm; QuayFaceStones 블록 크기 ±20%·전면 돌출 ±3 cm·모서리 bevel 1 cm. materials stone은 석별 Object/Attribute 랜덤 명도 ±10%.  
  → 기대 효과: 전경 사실감 상승. 폴리 증가 수만 이하.
- **[D4] [담당: design] [P2]** 주인공 뷰 bow34가 해를 마주 보는 역광(sun 방위 230°, 카메라 시선 ~146°)이라 선수판·귀면이 그림자.  
  → geobukseon_design.json sun: azimuth_deg 230→260, elevation_deg 25→32 (좌현·선수 모두 측광). stern34 순광은 다소 줄지만 측광으로 입체감 유지.  
  → 기대 효과: bow34 lighting +15. 렌더 시간 무관.

## P3

- **[M5] [담당: modeling] [P3]** 키 블레이드가 선미 뒤 수면 위로 0.59 m 떠오른 상자처럼 보이고, 선수 좌측 닻 걸이가 공중에 뜬 브래킷처럼 보임.  
  → build_rudder_props(): RudderBlade top_z를 수면 아래(−0.1)까지만 노출되게 하거나 stock과 철띠 2개로 연결, 블레이드 두께 0.15 반영; Anchor를 이물 측면 닻줄과 이어 현측에 기대게 위치(x −2.5, z 1.0).  
  → 기대 효과: stern34/aerial 이물감 제거. 소.
- **[T2] [담당: materials] [P3]** 방패판이 단색 적갈색 — 복원선의 방패판 테두리/단청 흔적·검은 띠가 없음.  
  → matlib.py wall_panel: Object z 기준 상하 테두리 흑색 띠(각 8 cm), 패널 경계(panel_width 0.9 m, Object y) 세로 흑선 3 cm, 상단 띠에 단청 녹·주홍 반복(주기 0.45 m), 풍화 노이즈 15%.  
  → 기대 효과: 중경 디테일 밀도 +5. 렌더 시간 무관.

