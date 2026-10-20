# materials/ — 절차적 재질·하늘·렌더 설정 (Blender 5.2)

- `matlib.py` — `build_all(hex_cell=0.9, hex_line_w=0.035, roof_arc_attr="roof_s", rebuild=True, dragon_style="wood", ghost_style="black", wall_style="natural") -> dict`
- `world.py` — `setup_world(scene, sun_azimuth_deg, sun_elevation_deg, strength=1.0, dust=1.6, auto_exposure=True, exposure_bias=0.8, sun_angle_deg=1.5, clouds=0.35)`, `setup_render(scene, engine, quality, res=(1920,1080))`
- `preview_matlib.py` — 견본 렌더 `/opt/bvenv/bin/python materials/preview_matlib.py` → `matlib_preview.png`(Cycles), `matlib_preview_eevee.png`

이미지 텍스처와 UV는 쓰지 않는다. 패턴 좌표는 Object 좌표(m 단위, **오브젝트 스케일이 1로 적용된 상태를 가정**)나 Generated 좌표(바운딩박스 0..1)를 쓴다. 물때·먼지는 월드 Position.z(수선 z=0)와 월드 Normal을 기준으로 한다.
고유색은 `refs/ref_*.jpg`(전쟁기념관 실내 복원선) 사진에서 샘플링했다. `matlib.REF` 표와 아래 "사진 대비 고유색" 표를 참고.

| 재질 | 용도 | 좌표/입력 | 주요 파라미터·특징 |
|---|---|---|---|
| `hull_wood` | 선체 외판 | Object: 결=Y, 판재는 Z 방향으로 적층 | 적갈~꿀색 소나무(REF hull), 판폭 0.32m, 엇갈린 이음 7.5m, 판재별 톤 차이, 결 강하게(grain_k 0.75), 약한 풍화, 니스 Coat 0.25, 수선 근처 물때 |
| `hull_waterline` | 흘수선 띠/하부 | Object + 월드 z | 젖은 짙은 판재, 녹조, 따개비, 염분 띠 |
| `roof_shell` | 개판(거북등) | 길이=Object Y, 가로=속성 `roof_s`(없으면 x·θ/sinθ 근사) | 수학으로 만든 육각 격자 `hex_cell`, 홈선 3.5cm(거의 흑색), **회흑 판**(REF roof), 셀별 명도 ±15%, 셀 중앙 마모, 대형 오염은 R1 대비 50% |
| `iron_spike` | 철첨 | Object | 흑철, 녹 0.25, 거칠기 0.5 |
| `iron_fitting` | **신규**: 방패판 꺾쇠·띠·장식 | Object | 흑색 단조철, 반광(거칠기 0.38, Metallic 0.75), 녹 0.15(홈 안쪽 AO) |
| `dragon_head` | 용두 | Object/Generated | 기본 `wood`: 흑갈 목조각, 결, 비늘선, 조각 골 AO, 돌출부 마모, Coat. `dancheong`: 구역별 단청 채색(옵션) |
| `ghost_face` | 귀면 | Generated X·Z, 메시는 **로컬 XZ 평면(법선 ±Y)** | 기본 `black`: 흑색 바탕, 흰 눈자위, 흰 이빨·송곳니, 붉은 입속. `dancheong`: 주토 바탕, 녹청 갈기, 주홍 눈테 |
| `wall_panel` | 방패판 | Object(가로=x+y), 속성 `wall_v`(0 하단 → 1 상단, 없으면 Generated Z) | 기본 `natural`: 꿀색 원목 판재 0.28m + 패판 경계 흑선(0.9m). `painted`: 흑 테·단청 띠(옵션) |
| `oar_wood` / `mast_wood` | 노 / 돛대 | 결=**로컬 Z** | 소나무, 옹이 |
| `bamboo` | **신규**: 돛살(batten) | 길이=**로컬 Z** | 황갈 대나무(REF bamboo), 마디 0.32m 간격, 세로 섬유, 반광 |
| `sail_cloth` | 돛 | Object | 황갈 마포(REF sail), 폭 솔기 0.55m, 얼룩, 빛 투과 22% |
| `rope` | 밧줄 | Object | 갈색 마 |
| `flag_cloth` | 깃발 | 색 속성 `flag_color`가 있으면 그 색, 없으면 `ob.color` | 바랜 염료 |
| `water` | 바다 | 월드 XY, 속성 `hull_dist` | Cycles 출력: 투과 IOR 1.333 + 볼륨 흡수(0.25,0.45,0.42, 밀도 0.6) + 20% 청록 확산. EEVEE 출력: 불투명 반사(출력 노드 타깃 분리). `hull_dist` 0~0.6m에 거품 띠(속성 없으면 거품 없음). 법선: 도메인 왜곡 + 비정수 배율 노이즈 |
| `stone` | 부두 | Object 박스 투영 | 화강암 마름돌 |
| `ground` | 해안·원경 산 | 월드 | 흙/모래/풀/자갈, z>3m이면 숲(수관 Voronoi, 능선 암석). 대기원근: `1-exp(-d/1800m)`, 최대 0.75, 노드 `AERIAL_HAZE` |

## 사진 대비 고유색 (선형 RGB)
샘플 방식: 각 사진에서 흰 벽·바닥 영역의 중앙값으로 정규화(흰색=0.8)해 조명색을 상쇄한 뒤 영역 중앙값을 냈다. 그림자 쪽 샘플은 밝기를 보정했다.

| 대상 | 사진 샘플 (사진, 영역) | 사진 추정 albedo | 재질값 REF |
|---|---|---|---|
| 선체 판재 | bow34 하부(200-400,300-340) / side 선수 목재 | (0.07,0.021,0.013)(그늘) / (0.36,0.18,0.09) | hull 0.080,0.034,0.015 ~ 0.215,0.098,0.040 |
| 방패판 판재 | bow34(150-190,215-240) | (0.11,0.034,0.020)(그늘) | board 0.115,0.044,0.018 ~ 0.245,0.098,0.036 |
| 원형 문양판 | bow34 / side | (0.115,0.037,0.019) / (0.46,0.20,0.05) | (형상·재질은 모델러: hull_wood 사용 권장) |
| 개판 | stern34(90-200,190-240) / aerial(110-220,300-360) | (0.16,0.125,0.10) / (0.095,0.073,0.068) | roof 0.040,0.037,0.035 ~ 0.068,0.062,0.057 |
| 용두 | bow34(55-110,150-200) / aerial | (0.028,0.024,0.025) / (0.057,0.026,0.027) | dragon_wood 0.034,0.026,0.023 |
| 돛 | bow34(220-300,60-140) / aerial | (0.67,0.49,0.32) / (0.50,0.24,0.08) | sail 0.42,0.29,0.16 |
| 철물·철첨 | 시각 판정(흑색) | — | iron 0.020,0.019,0.018 |

## world.py
- 하늘: `MULTIPLE_SCATTERING`('NISHITA'를 대체). `sun_rotation`에는 방위각을 그대로 넣는다(북 0°, 동 90°).
- 태양 원반은 카메라 광선에만 보이고, 직사광은 `SUN_Key` 라이트가 맡는다(각도 1.5°). 태양 세기·색은 고도별 실측표에서 보간한다.
- 절차적 구름: `clouds` 0..1, 2D 층 투영 노이즈로 만들어 비용이 거의 없다.
- 아래 반구: 카메라 광선에는 연무색, 그 밖의 광선(투과·간접)에는 깊은 바다 산란색을 쓴다(Cycles 투과 물이 우윳빛이 되는 것을 막음).
- 노출: 흰 수평면 기준으로 자동 계산 + `exposure_bias`(기본 0.8). 룩은 `AgX - Base Contrast`.
- `setup_world`는 재질 안의 `AERIAL_HAZE` RGB 노드에 연무 휘도를 써 넣는다. 그래서 반드시 `build_all()` **다음에** 호출해야 한다.
- EEVEE: Screen 레이트레이싱(해상도 1/2), Fast GI = GLOBAL_ILLUMINATION(거리 무제한, ray 4, step 8), 월드 프로브 1024, 그림자 ray 1/2, TAA 24/64.
- Cycles: 64/512spp, 적응형 샘플링, OIDN.

## 모델러 주의
- 오브젝트 스케일을 apply 해야 한다.
- 노·돛대·대나무살은 Z축 원기둥으로 만든 뒤 회전한다.
- 귀면 메시는 로컬 XZ 평면에 둔다.
- 메시 속성:
  - `roof_s`: 지붕 호길이(m)
  - `hull_dist`: 물 메시의 point float, 선체까지 수평거리(m)
  - `wall_v`: 방패판 0..1, 권장. 없으면 테두리 띠가 sheer를 따라가지 않는다(`painted` 스타일에서만 영향).
  - `flag_color`: 깃발 색
- 용두의 흰 이빨·흰 눈 테·붉은 입속은 별도 메시 보조 재질로 만든다(matlib 기본 `wood` 스타일에는 그려 넣지 않음).
- 물은 Cycles에서 투과 재질이라 렌더 시간이 늘어난다(견본 씬 61→97~134 s).
