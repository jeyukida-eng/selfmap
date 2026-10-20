# 거북선 포토리얼 파이프라인 — 공통 인터페이스 명세 (오케스트레이터 작성)

모든 역할 에이전트는 이 문서를 계약으로 따른다. 변경이 필요하면 오케스트레이터에게 보고하고 임의로 바꾸지 않는다.

## 0. 실행 환경
- Blender = PyPI `bpy==5.2.2` (Python 3.13 모듈), venv: `/opt/bvenv` → 실행은 `/opt/bvenv/bin/python script.py`
  (`blender -b -P`가 아님. 스크립트 안에서 `import bpy`. 씬 초기화는 `bpy.ops.wm.read_factory_settings(use_empty=True)`)
- EEVEE는 llvmpipe 소프트웨어 GL: `EGL_PLATFORM=surfaceless` 환경변수 필요. 느림(첫 프레임 셰이더 컴파일 ~40s).
- Cycles는 CPU 4코어. 렌더 경로는 반드시 **절대경로**.
- 네트워크: PyPI·GitHub만 허용. Wikimedia/정부 사이트 차단(WebSearch 스니펫은 사용 가능).
- 루트: `/home/user/selfmap/geobukseon` (이하 `ROOT`). 스크립트는 `ROOT` 기준 상대경로를 `__file__`로 계산.

## 1. 좌표계·단위
- 단위 m. **+X 동, +Y 북, +Z 위**. 원점 = 선체 중앙(길이 방향 중점) · 중심선 · **수선(waterline) z=0**.
- 선수(뱃머리, 용두)는 **+Y(북)** 방향. 좌현 = −X(서), 우현 = +X(동).

## 2. 폴더 구조와 소유 역할
| 경로 | 소유 | 산출물 |
|---|---|---|
| `design/` | 설계 에이전트 | `sources.md`, `geobukseon_design.json`, `gen_drawings.py`, `plan.png`, `elevation.png`(측면+정면+단면) |
| `refs/` | 설계 에이전트(스크립트)/오케스트레이터 | `fetch_refs.py`, `refs_manifest.json`, `ref_<view>.jpg` |
| `materials/` | 텍스처 에이전트 | `matlib.py`, `world.py`, `preview_matlib.py`, `matlib_preview.png` |
| `modeling/` | 모델링 에이전트 | `build_scene.py`, `geobukseon.blend`(생성물) |
| `validation/` | 검증 에이전트 | `render_views.py`, `compare.py`, `round<N>/`(렌더·비교·`scores.json`·`fixlist.md`) |
| `final/` | 마무리 | `render_still.py`, `flythrough.py`, `audio_synth.py`, `make_mp4.sh` |
| `out/` | 전원 | 최종 결과물(스틸 PNG, MP4, WAV, 도면, 비교판) |

## 3. 설계 JSON (`design/geobukseon_design.json`) 필수 키
```jsonc
{
  "meta": {"units":"m","axes":{"+X":"east","+Y":"north","+Z":"up"},
           "origin":"midship, centerline, waterline", "version":1,
           "evidence_tags":"각 수치에 [확정]/[추정]/[가정] 태그를 *_tag 필드로"},
  "principal": {"loa":..,"beam":..,"height_keel_to_roof":..,"draft":..,
                "*_tag":"...", "source_ids":["S1",...]},
  "hull": {   // 평저선(판옥선 계열) 선체. 스테이션 = 선수→선미 단면 표
     "stations":[{"y":..,"bottom_half":..,"sheer_half":..,"keel_z":..,"sheer_z":..}, ...],
     "plank_width":..,"bow_transom":{...},"stern_transom":{...}},
  "superstructure": { // 상장(上粧: 방패판 벽) + 개판(거북등 지붕)
     "wall":{"stations":[{"y":..,"half":..,"top_z":..}],"thickness":..},
     "roof":{"stations":[{"y":..,"half":..,"eave_z":..,"ridge_z":..}],
             "spikes":{"spacing":..,"height":..,"exclude_ridge_lane":..},
             "hex_cell":..,"cross_walkway_width":..}},
  "dragon_head":{"base":[x,y,z],"length":..,"height":..,"pitch_deg":..,"mouth_open":..},
  "ghost_face":{"center":[x,y,z],"width":..,"height":..},
  "oars":{"per_side":..,"y":[...],"port_z":..,"length":..,"angle_deg":..},
  "gun_ports":{"side":[{"y":..,"z":..}],"bow":[...],"stern":[...],"size":..},
  "masts":[{"y":..,"height":..,"lowered":false,"sail":{"w":..,"h":..}}],
  "rudder":{"y":..,"depth":..,"width":..},
  "flags":[{"pos":[x,y,z],"size":[w,h],"color":"..."}],
  "site":{"water_z":0,"water_size":..,"pier":null|{...},"shore":null|{...}},
  "sun":{"azimuth_deg":..,"elevation_deg":..},   // 방위각: 북=0, 동=90 (시계)
  "views":[ // 참고 이미지 4장과 1:1. 검증 렌더 카메라
     {"id":"bow34","name":"...","cam":[x,y,z],"look_at":[x,y,z],"lens_mm":..,"ref":"refs/ref_bow34.jpg"},
     {"id":"side", ...},{"id":"stern34", ...},{"id":"aerial", ...}],
  "flythrough":{"fps":24,"seconds":24,"keys":[{"t":0,"cam":[..],"look_at":[..],"lens_mm":..},...]}
}
```
모든 수치에 근거 태그: **[확정]**(공개 실측/공식 발표), **[추정]**(문헌·사진에서 계산), **[가정]**(근거 없음, 설계 판단).

## 4. 재질 라이브러리 계약 (`materials/matlib.py`)
- `build_all() -> dict[str, bpy.types.Material]` : 아래 이름 전부 생성(이미 있으면 재사용). 이미지 텍스처 금지(전부 절차적 노드).
- 필수 키: `hull_wood`(소나무 판재, 결·이음·물때), `hull_waterline`(흘수선 오염/이끼), `roof_shell`(거북등 육각 무늬, 적갈·흑 도장 풍화), `iron_spike`(철첨, 녹), `dragon_head`(채색 목조각), `ghost_face`(귀면 채색), `wall_panel`(방패판, 단청 흔적), `oar_wood`, `mast_wood`, `sail_cloth`(마포), `rope`, `flag_cloth`(색은 object color 또는 attribute로), `water`(바다: 굴절·파도 법선), `stone`(부두), `ground`.
- UV 의존 금지 → Object/Generated 좌표 사용(박스 투영 or `Object` 좌표). 스케일은 m 기준.
- `materials/world.py`: `setup_world(scene, sun_azimuth_deg, sun_elevation_deg, strength=1.0)` → Nishita 하늘 + Sun 라이트(방향 일치) 생성, Cycles/EEVEE 둘 다 동작.

## 5. 모델링 계약 (`modeling/build_scene.py`)
- CLI: `/opt/bvenv/bin/python modeling/build_scene.py [--design PATH] [--save PATH] [--quality preview|final]`
- 함수 `build(design_path, quality) -> bpy.types.Scene` (다른 스크립트가 import해 씬을 조립). 멱등·재실행 가능.
- `import matlib, world` (sys.path에 `ROOT/materials` 추가). 하드코딩 치수 금지 — 전부 JSON에서.
- 컬렉션: `Hull`, `Superstructure`, `Details`, `Rigging`, `Site`, `Cameras`. 카메라는 views id 이름(`CAM_bow34` 등).
- 기본 저장: `modeling/geobukseon.blend`.

## 6. 검증 계약
- `validation/render_views.py --round N [--engine CYCLES] [--samples 64] [--res 960x540]` → `validation/roundN/render_<id>.png`
- `validation/compare.py --round N` → `roundN/compare_<id>.png`(참고|렌더 나란히, 참고 없으면 설계 입면도 실루엣과 겹쳐보기), `roundN/scores.json`, `roundN/fixlist.md`
- 점수 축(각 0–100): 실루엣/비례, 디테일 밀도, 재질 사실감, 조명/하늘, 구도 일치, 물/환경. 수정목록 항목마다 담당(`design|modeling|materials`)·우선순위 표기.

## 7. 공통 규칙
- 각 스크립트는 단독 실행·재실행 가능, 랜덤 시드 고정.
- 파일 상단 docstring에 용도·실행 명령 1줄.
- 렌더 확인은 반드시 실제 렌더 PNG를 Read로 눈으로 보고 판단.
