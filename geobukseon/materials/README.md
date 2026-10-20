# materials/ — 절차적 재질·하늘·렌더 설정 (Blender 5.2)

- `matlib.py` — `build_all(hex_cell=0.9, hex_line_w=0.075, roof_arc_attr="roof_s", rebuild=True) -> dict`
- `world.py` — `setup_world(scene, sun_azimuth_deg, sun_elevation_deg, strength=1.0, dust=1.6, auto_exposure=True, exposure_bias=0.0)`, `setup_render(scene, engine, quality, res=(1920,1080))`
- `preview_matlib.py` — 견본 렌더 `/opt/bvenv/bin/python materials/preview_matlib.py` → `matlib_preview.png`(Cycles), `matlib_preview_eevee.png`

이미지 텍스처·UV는 쓰지 않음. 패턴 좌표는 Object(m, **오브젝트 스케일 1 적용 상태 가정**) / Generated(바운딩박스 0..1), 물때·먼지는 월드 Position.z(수선 z=0)·월드 Normal 기준.

| 재질 | 용도 | 좌표/입력 | 주요 파라미터·특징 |
|---|---|---|---|
| `hull_wood` | 선체 외판(소나무) | Object: 결=Y, 판재 Z방향 적층 | 판폭 0.32m, 맞대기 이음 7.5m(행마다 엇갈림), 판재별 톤(White Noise), Wave+Noise 결, 회색 풍화, AO 때, 수선 위 0.45m 젖은 띠·흘러내린 물때·녹조, Bump 0.25 |
| `hull_waterline` | 흘수선 띠/수면 아래 선체 | Object + 월드 z | 더 어두운 젖은 판재, 녹조, 따개비 반점(Voronoi), 흰 염분 띠, 낮은 거칠기 |
| `roof_shell` | 거북등 지붕(개판) | 길이=Object Y, 가로=attr `roof_s`(용마루로부터 호길이 m) 없으면 x·θ/sinθ 근사 | **수학 육각 격자** flat-to-flat=`hex_cell`(0.9m), 선폭 `hex_line_w`(7.5cm) 흑색, 판은 흑갈~적갈 셀별 변이, 도장 얼룩·빗물 줄·벗겨짐(선 근처 많음)·윗면 먼지 |
| `iron_spike` | 철첨 | Object | 회흑 금속(Metallic 0.85) ↔ 갈색 녹(비금속, 거칠기 0.9) 노이즈 마스크 |
| `dragon_head` | 용두 단청 | Generated Y(뒤→주둥이) 띠, Z 아래=적색 | 뇌록·백·석간주·군청·황 띠(9회), Voronoi 비늘선, 바램 0.85, 벗겨짐, AO 때 |
| `ghost_face` | 귀면 | Generated X(가로)·Z(세로), 얼굴 = **메시 로컬 XZ 평면(법선 ±Y)** | 붉은 바탕, 흰 눈자위+검은 눈동자, 녹색 눈썹, 흰 이빨·송곳니, 어두운 입/코 |
| `wall_panel` | 방패판(상장 벽) | Object(가로=x+y, 결=Z 세로판 0.28m) + Generated Z | 검붉은 도장, 상단 흰 띠·청 띠, 하단 청 띠(닳은 흔적), 벗겨진 목재, 물때 |
| `oar_wood` | 노 | Object, 결=**로컬 Z** | 밝은 회갈 소나무, 옹이(Voronoi), 젖은 하단 |
| `mast_wood` | 돛대 | Object, 결=**로컬 Z** | 어두운 소나무, 옹이 |
| `sail_cloth` | 마포 돛 | Object (폭 이음 방향 = x+y, 0.55m) | 미색 회갈, 폭 솔기, 얼룩/줄, 직조 Wave, Sheen, Translucent 22% |
| `rope` | 밧줄 | Object | 갈색 마, 꼬임 Wave(대각), Sheen |
| `flag_cloth` | 깃발 | **색 attribute `flag_color`(색 속성) 우선, 없으면 Object Color(`ob.color`)** | 바랜 염료, 얼룩, 직조, Translucent 30% |
| `water` | 바다 | 월드 XY | 불투명 유전체 IOR 1.333, 짙은 청록, 다중 스케일 Noise+Wave 범프(먼 거리 감쇠), 바람결 거칠기 패치 0.025~0.11 |
| `stone` | 부두 석축 | Object 박스 투영 Brick | 화강암 마름돌 1.3×0.5m, 반점, 얼룩·지의류, 수선 녹조 |
| `ground` | 해안 지면 | 월드 | 흙/모래(물가)/풀(평탄·고지)/자갈/경사면 암반 |

## world.py
- Sky: `MULTIPLE_SCATTERING` (5.x에서 'NISHITA' 대체). `sun_rotation` = 방위각(북 0°, 동 90°, 시계) — 그림자 방향으로 실측 확인.
- 하늘 태양 원반은 **카메라 광선에만** 보이고 직사광은 `SUN_Key` 라이트가 담당(이중 조명 없음, EEVEE `world.sun_threshold=0`).
- Sun 라이트 세기·색은 고도별 실측표(물리 단위, 정오 ≈160 W/m²)로 보간 → 저고도에선 자동으로 붉고 약해짐.
- 수평선 아래는 연무색으로 채움(물리 하늘은 검정 + Sky 노드 Vector 입력 비활성).
- `auto_exposure=True`: `view_settings.exposure`를 자동(약 −4~−6). 다른 조명을 추가하면 물리 단위로(예: 등불 수백 W) 넣을 것.
- `setup_render`: AgX + "AgX - Medium High Contrast"; Cycles 64/512spp, 적응형, OIDN(albedo+normal); EEVEE 16/64 TAA, Screen 레이트레이싱, 그림자 ray 1/2, Fast GI.

## 모델러 주의
- 오브젝트 스케일은 apply(1.0) 해야 패턴 크기가 m 기준으로 맞음.
- 지붕 육각을 정확히 하려면 메시에 float attribute `roof_s`(용마루에서 측면을 따라 잰 호길이 m, 좌현 음수)를 넣는 것을 권장. 없으면 원호 근사.
- 노·돛대는 Z축 원기둥으로 만든 뒤 회전(결=로컬 Z). 귀면은 메시를 로컬 XZ 평면에 두고 회전.
- `hull_waterline`은 흘수선 −1.0~+0.4m 띠/하부 선체에, `hull_wood`도 자체적으로 수선 근처 물때를 가짐(월드 z 기준이므로 선체를 z로 옮기면 물때도 따라 바뀜).
- `water`는 불투명 → 수면 아래 선체는 보이지 않음(렌더 시간 절약). Ocean modifier 사용 시 범프와 함께 동작.
