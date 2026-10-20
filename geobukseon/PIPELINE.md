# 거북선 포토리얼 파이프라인 — 재현 가이드

설계 JSON 하나에서 도면, 씬, 검증, 스틸, 플라이스루, 환경음, MP4까지 전부 코드로 다시 만든다(헤드리스, 재실행 가능, 시드 고정).
계약(좌표계·키·폴더·역할)은 [`SPEC.md`](SPEC.md)에 있다.

## 0. 환경 (1회)
```bash
python3.13 -m venv /opt/bvenv
/opt/bvenv/bin/pip install bpy==5.2.2 numpy pillow scipy matplotlib   # Blender 5.2.2 LTS를 파이썬 모듈로 설치
apt-get install -y libegl1 libegl-mesa0 ffmpeg                         # EEVEE 헤드리스(llvmpipe) + 인코딩
export EGL_PLATFORM=surfaceless                                         # EEVEE 렌더 시 필요
```

## 1. 전체 재현 (순서대로)
| # | 단계 | 명령 | 산출물 | 소요[실측, 4코어 CPU] |
|---|---|---|---|---|
| 1 | 설계 도면·충돌검사 | `/opt/bvenv/bin/python design/gen_drawings.py` | `design/{plan,elevation,views_check}.png` → `out/` | ~10 s |
| 2 | 참고 사진 | `/opt/bvenv/bin/python refs/fetch_refs_yfcc.py` (재검색은 `--scan`) | `refs/ref_*.jpg` (MD5 검증) | ~5 s (재검색 ~15 min) |
| 3 | 재질 견본 | `/opt/bvenv/bin/python materials/preview_matlib.py` | `materials/matlib_preview*.png` | ~4 min |
| 4 | 씬 조립 | `/opt/bvenv/bin/python modeling/build_scene.py --quality final` | `modeling/geobukseon.blend` | ~11 s |
| 5 | 검증 렌더 | `/opt/bvenv/bin/python validation/render_views.py --round round2_final` | `validation/<round>/render_*.png, mask_*` | ~9 min |
| 6 | 검증 비교·채점 | `/opt/bvenv/bin/python validation/compare.py --round round2_final` | `compare_*.png, contact_sheet.png, scores.json, residual.md` | ~20 s |
| 7 | 마무리 일괄 | `bash final/run_final.sh` | 아래 §2 | 스틸 ~40 min + 플라이스루 ~2 h [추정] |

7단계 내부(개별 실행 가능):
- `/opt/bvenv/bin/python final/render_still.py --long 1600 --samples 96`: Cycles 스틸 4장. 뷰별 태양과 `ref_aspect` 비율 적용.
- `EGL_PLATFORM=surfaceless /opt/bvenv/bin/python final/flythrough.py --res 960x540 --samples 12`: EEVEE 576프레임. 이미 렌더된 프레임은 건너뛰므로 중단 후 이어서 실행할 수 있다.
- `/opt/bvenv/bin/python final/audio_synth.py`: 24초 환경음(바람·파도·새·풍경·범종). 녹음 소스 없이 numpy로 합성한다.
- `bash final/make_mp4.sh`: H.264 CRF18 영상과 AAC 192k 음성을 합쳐 `out/geobukseon_flythrough.mp4`를 만든다.

## 2. 결과물 (`out/`)
| 파일 | 내용 |
|---|---|
| `still_{bow34,side,stern34,aerial}.png` | Cycles 스틸(참고 사진과 같은 구도) |
| `geobukseon_flythrough.mp4` | 24 s · 24 fps · 960×540 EEVEE 플라이스루 + 환경음 |
| `ambience.wav` | 48 kHz 스테레오 환경음 원본 |
| `plan.png`, `elevation.png`, `views_check.png` | 배치도, 입면·단면도, 참고 사진 대 설계 카메라 비교 |
| `contact_sheet_final.png` | 최종 검증: 참고 사진과 렌더 나란히 |
| `logs/` | 렌더 로그(프레임별 시간) |

## 3. 역할 분담 (오케스트레이터 + 서브에이전트)
| 역할 | 소유 폴더 | 핵심 파일 |
|---|---|---|
| 오케스트레이터 | `SPEC.md`, `final/`, `refs/fetch_refs_yfcc.py` | 계약·통합·참고 사진 수집·마무리 |
| 설계 | `design/` | `geobukseon_design.json`(v2), `sources.md`(S1–S8, R1–R4), `gen_drawings.py` |
| 텍스처·라이팅 | `materials/` | `matlib.py`(절차적 재질 17종 + 보조), `world.py`(물리 하늘·태양·렌더 설정) |
| 모델링 | `modeling/` | `build_scene.py`(JSON에서 씬 조립), `quick_check.py` |
| 검증 | `validation/` | `render_views.py`, `compare.py`, `ref_masks/`, `round1/`, `round2/`, `round2_final/` |

## 4. 검증 이력 (가중 총점 /100)
| 라운드 | 비교 기준 | 총점 | 주요 수정 → 담당 |
|---|---|---|---|
| round1 | 설계 투영(실사 없음) | 60.0 | 노출, 물 투과·거품, 육각 무늬 → 재질 / 포혈 막음판, 용두 치수 → 모델링 / 철첨, 귀면, 태양 → 설계 |
| (실사 확보) | YFCC100M 사진 4장 | — | 카메라를 사진에 맞춤, 세운 대살 돛, 목 위 용두, 방패판 원형 문양 → 설계 v2·모델링 v2·재질 |
| round2 | 실사 사진 | 63.4 | 알베도·보조광 → 재질 / 용두 목, 삭구, 원형 포혈, 귀면 → 모델링 / 뷰별 태양 → 설계 |
| round2_final | 실사 사진(같은 지표) | **66.2** | 남은 과제는 `validation/round2_final/residual.md` |

- 점수 축: 실루엣, 디테일, 재질, 조명, 구도, 환경. [정량] 지표(IoU, ΔE, 엣지 밀도)와 [주관] 평가를 섞어 매긴다. 근거는 `assessment.json`에 있다.
- round1과 그 이후 라운드는 비교 기준이 달라서, 점수 차이(Δ)를 같은 조건의 개선폭으로 볼 수 없다.

## 5. 근거·한계 (확정/추정/가정)
- **기준 제원 [확정]:** 2011 경남 '이순신 프로젝트' 복원선 25.6 × 8.67 × 6.06 m(S1).
  - 흘수 1.4 m, 돛대 높이, 상장 높이는 [가정] 또는 [추정]이다.
  - 출처는 모두 검색 스니펫 기준이며 원문은 확인하지 못했다(`design/sources.md`).
- **참고 사진:** Wikimedia가 이 환경에서 차단되어 YFCC100M(Flickr CC)의 AWS 미러로 대체했다(`refs/README.md`).
  - 피사체는 전쟁기념관 실내 전시선이라 배경과 조명은 비교에서 뺐다.
  - BY-NC-ND 3장은 크기 조정만 해서 비상업적으로 나란히 비교하는 데만 썼다.
- **뷰별 태양:** 스틸은 컷마다 촬영 시각이 다르다고 가정하고 `views[*].sun`을 쓴다. 플라이스루는 전역 태양 200°/35°를 쓴다.
- **EEVEE:** GPU가 없어 소프트웨어 GL(llvmpipe)로 돌렸다. 그래서 960×540, TAA 12로 타협했고, 프레임당 약 10–15 s 걸린다.
- **남은 약점 상위 5개** (`residual.md`):
  - 목재 채도가 과하다.
  - 개판이 너무 깨끗하다.
  - 용두가 가늘다.
  - stern34에서 배가 작게 잡힌다.
  - 원형 문양 테가 끊겨 보인다.
