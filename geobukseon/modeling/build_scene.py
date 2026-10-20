"""거북선 씬 절차 모델링 (SPEC §5). 모든 치수는 design/geobukseon_design.json 에서 읽는다.

실행: /opt/bvenv/bin/python modeling/build_scene.py [--design PATH] [--save PATH] [--quality preview|final]
다른 스크립트에서:  sys.path.insert(0, ROOT/modeling); import build_scene; scene = build_scene.build(path, "preview")

JSON 해석 규칙은 design/gen_drawings.py 와 같다(스테이션 y 보간, 지붕 초타원 단면, 상장 = 현측 높이에서 수평 돌출 후 수직).
보간: 단조 3차(PCHIP) — 스테이션을 정확히 지나며 오버슈트 없음. 단 선체 keel_z·bottom_half 는 호판(transom) 구간
(bow_transom.y_bottom 앞, stern_transom.y_bottom 뒤)에서 선형(평판 호판 유지), 그 꺾임(knuckle)은 날카롭게 보존.
"""
import argparse
import colorsys  # noqa: F401  (hex 변환 보조용으로 남겨둠)
import json
import math
import os
import random
import sys
import time

import bpy  # noqa: I001  (bpy 를 먼저 import 해야 bmesh/mathutils 사용 가능)
import bmesh
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_DESIGN = os.path.join(ROOT, "design", "geobukseon_design.json")
DEFAULT_SAVE = os.path.join(HERE, "geobukseon.blend")

# =====================================================================================================
# 형상 디테일 상수 (JSON 에 없는 '모양 비율'·미세 디테일. 치수 자체는 전부 JSON)
# =====================================================================================================
SEED = 1597                      # 모든 랜덤(석재 지터, 철첨 크기 등) 고정 시드
SMOOTH_ANGLE_DEG = 35.0          # 이보다 꺾인 모서리는 sharp 로 표시(그 외 부드러운 셰이딩)

# 선체
HULL_SIDE_BULGE = 0.025          # 현측 볼록량 = 현측 길이 × 이 비율 (conventions: '직선/약한 볼록')
PLANK_GROOVE_W = 0.022           # 외판 판재 이음 홈 폭(m)
PLANK_GROOVE_D = 0.014           # 외판 이음 홈 깊이(m)
DECK_THICK_RATIO = 1.5           # 갑판(가룡 돌출 갑판) 두께 = plank_thickness × 비율
BEAM_END_SPACING = 1.45          # 갑판 밑 가룡(橫梁) 머리 간격(m) — 돌출 갑판 하부 디테일
BEAM_END_SIZE = 0.16             # 가룡 머리 단면(m)

# 상장(방패판 벽)
WALL_VSEG = 4                    # 벽 세로 분할 수
PANEL_GROOVE_W = 0.03            # 방패판 세로 줄눈 폭
PANEL_GROOVE_D = 0.02            # 줄눈 깊이
WALL_RAIL_H = 0.14               # 벽 하단·상단 띠장(rail) 높이
WALL_RAIL_OUT = 0.05             # 띠장 돌출
PORT_FRAME_RATIO = 0.18          # 포혈 테 폭 = 포혈 크기 × 비율
PORT_FRAME_DEPTH = 0.05          # 포혈 테 돌출
OAR_PORT_R = 0.09                # 노 구멍 반지름 (gen_drawings.py 표기와 동일)

# 개판(지붕)
WALKWAY_RAISE = 0.025            # 통로 판재가 지붕면 위로 뜨는 높이
WALKWAY_THICK = 0.05             # 통로 판재 두께
WALKWAY_BOARD = 0.20             # 통로 판재 1장 폭(이음 홈 간격)
SPIKE_EDGE_MARGIN = 0.5          # 철첨 배치: 처마/양끝에서 spacing × 이 비율만큼 비움
SPIKE_SIDES = 6                  # 철첨 원뿔 측면 수
SPIKE_SCALE_JITTER = 0.12        # 철첨 크기 랜덤 ±
HATCH_H = 0.22                   # 지붕 출입 해치 높이

# 용두
DRAGON_SECTIONS_PREVIEW = 22
DRAGON_SECTIONS_FINAL = 40
DRAGON_RING = 20                 # 단면 링 버텍스 수

# 귀면
GHOST_RELIEF = 0.10              # 귀면 부조 최대 돌출(m)
GHOST_BACKING = 0.06             # 귀면 판 두께

# 노
OAR_AFT_SWEEP = 0.6              # 노 끝의 선미 방향 후퇴량(m) — gen_drawings.py 평면/측면도와 동일
OAR_SHAFT_R = 0.055              # 노 자루 반지름
OAR_BLADE_T = 0.045              # 노 날 두께
OAR_HANDLE_LEN = 0.45            # 노손(손잡이 가로대) 길이

# 돛대·돛
MAST_TOP_TAPER = 0.6             # 돛대 끝 지름 / 밑 지름
MAST_LOWERED_TILT_DEG = 84.0     # lowered=true 일 때 수직에서 선미 쪽으로 기울이는 각
YARD_DROP = 0.85                 # 활대 높이 = 돛대 끝 - 이 값 (gen_drawings: 접은 돛 top-1.2 ~ top-0.85)
YARD_OVER = 1.08                 # 활대 길이 = sail.w × 비율
YARD_R_RATIO = 0.42              # 활대 반지름 = 돛대 반지름 × 비율
FURL_DIAM = 0.35                 # 접은 돛 말린 지름 (gen_drawings 0.35)
FURL_TIES = 7                    # 묶음 끈 수
ROPE_R = 0.018                   # 삭구 반지름
MOOR_R = 0.032                   # 계류줄 반지름
ROPE_SAG = 0.035                 # 처짐 = 스팬 × 비율

# 키
RUDDER_BLADE_FRAC = 0.45         # 키 날개 높이 = depth × 비율 (gen_drawings 와 동일)
RUDDER_STOCK_EXT = 0.6           # 키 자루 상단 돌출
RUDDER_TILLER = 1.6              # 키손(가로대) 길이
RUDDER_BOARDS = 5

# 깃발
FLAG_WAVE_AMP = 0.07             # 펄럭임 진폭 = w × 비율
FLAG_WAVE_LEN = 0.65             # 파장 = w × 비율
FLAG_DROOP = 0.10                # 끝단 처짐 = h × 비율
FLAG_POLE_R = 0.035
FLAG_POLE_TOP = 0.25

# 부두·지형
STONE_JITTER_SIZE = 0.05         # 석재 크기 랜덤 ±비율
STONE_JITTER_ROT_DEG = 1.5
STONE_JITTER_OUT = 0.025         # 석재 면 앞뒤 들쭉날쭉(m)
STONE_GAP = 0.018                # 석재 사이 틈
STONE_BEVEL = 0.035
CAP_LEN_RATIO = 1.5              # 갓돌 길이 = block_size[0] × 비율
CAP_OVERHANG = 0.06
BOLLARD_R = 0.22
BOLLARD_H = 0.55
SHORE_BANK = 4.0                 # 해안 끝 경사 둑 수평 길이
SHORE_BANK_BOTTOM = -2.5
HILL_LEN_RATIO = 5.0             # 원경 섬 반길이 = height × 비율
HILL_WID_RATIO = 1.6

# 수면
OCEAN_EXTENT_RATIO = 0.25        # 근경 Ocean 크기 = site.water_size × 비율 (나머지는 평면)
OCEAN_WIND = 4.2                 # m/s — 잔잔한 항구 (작은 파고)
OCEAN_WAVE_SCALE = 0.25        # 파고 약 ±0.25 m (std ~0.07 m)
OCEAN_CHOP = 0.9
OCEAN_SEED = 7
HORIZON_FAR = 25000.0            # 원경 평면 반경(수평선까지)

QUALITY = {
    "preview": dict(y_step=0.22, side_sub=2, roof_n=56, subdiv=1, ocean_res=14, ghost=(56, 44),
                    wall_step=0.30, dragon_sec=DRAGON_SECTIONS_PREVIEW, cyl=16, hill=(48, 20)),
    "final":   dict(y_step=0.08, side_sub=4, roof_n=120, subdiv=2, ocean_res=24, ghost=(110, 84),
                    wall_step=0.12, dragon_sec=DRAGON_SECTIONS_FINAL, cyl=32, hill=(128, 48)),
}


# =====================================================================================================
# 보간
# =====================================================================================================
def _pchip_slopes(x, y):
    h = np.diff(x)
    d = np.diff(y) / h
    n = len(x)
    m = np.zeros(n)
    if n == 2:
        m[:] = d[0]
        return m
    for k in range(1, n - 1):
        if d[k - 1] * d[k] <= 0:
            m[k] = 0.0
        else:
            w1 = 2 * h[k] + h[k - 1]
            w2 = h[k] + 2 * h[k - 1]
            m[k] = (w1 + w2) / (w1 / d[k - 1] + w2 / d[k])
    m[0] = d[0]
    m[-1] = d[-1]
    return m


class Curve1D:
    """y → value, PCHIP (스테이션 통과, 단조). 범위 밖은 끝값 고정."""

    def __init__(self, xs, vs, linear=False):
        o = np.argsort(xs)
        self.x = np.asarray(xs, float)[o]
        self.v = np.asarray(vs, float)[o]
        self.linear = linear or len(self.x) < 3
        self.m = _pchip_slopes(self.x, self.v) if not self.linear else None

    def __call__(self, t):
        x, v = self.x, self.v
        if t <= x[0]:
            return float(v[0])
        if t >= x[-1]:
            return float(v[-1])
        i = int(np.searchsorted(x, t) - 1)
        i = max(0, min(i, len(x) - 2))
        if self.linear:
            return float(np.interp(t, x, v))
        h = x[i + 1] - x[i]
        s = (t - x[i]) / h
        h00 = 2 * s ** 3 - 3 * s ** 2 + 1
        h10 = s ** 3 - 2 * s ** 2 + s
        h01 = -2 * s ** 3 + 3 * s ** 2
        h11 = s ** 3 - s ** 2
        return float(h00 * v[i] + h10 * h * self.m[i] + h01 * v[i + 1] + h11 * h * self.m[i + 1])

    def deriv(self, t, eps=1e-3):
        return (self(t + eps) - self(t - eps)) / (2 * eps)


class Piecewise:
    """선체 keel_z/bottom_half: 호판 구간은 선형, 본체 구간은 PCHIP."""

    def __init__(self, stations, key, y_lo, y_hi):
        ys = [s["y"] for s in stations]
        vs = [s[key] for s in stations]
        body = [(y, v) for y, v in zip(ys, vs) if y_lo - 1e-6 <= y <= y_hi + 1e-6]
        self.body = Curve1D([a for a, _ in body], [b for _, b in body])
        self.lin = Curve1D(ys, vs, linear=True)
        self.lo, self.hi = y_lo, y_hi

    def __call__(self, t):
        if self.lo <= t <= self.hi:
            return self.body(t)
        return self.lin(t)

    def deriv(self, t, eps=1e-3):
        return (self(t + eps) - self(t - eps)) / (2 * eps)


def station_curves(stations, keys):
    ys = [s["y"] for s in stations]
    return {k: Curve1D(ys, [s[k] for s in stations]) for k in keys}


# =====================================================================================================
# 공통 헬퍼
# =====================================================================================================
def hex_to_linear(hx):
    hx = hx.lstrip("#")
    c = [int(hx[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(((v / 12.92) if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4) for v in c) + (1.0,)


def auto_smooth(bm, angle_deg=SMOOTH_ANGLE_DEG):
    lim = math.radians(angle_deg)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if len(e.link_faces) == 2:
            e.smooth = e.calc_face_angle(0.0) < lim
        else:
            e.smooth = True


def mesh_object(name, bm, coll, mats=None, smooth=True, angle=SMOOTH_ANGLE_DEG):
    if smooth:
        auto_smooth(bm, angle)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    for m in (mats or []):
        me.materials.append(m)
    return ob


def loft_grid(bm, rings, closed=False, cap_start=False, cap_end=False):
    """rings: list[list[Vector]] (같은 개수). 링 사이 쿼드. 반환 2D 버텍스 배열."""
    vv = [[bm.verts.new(p) for p in r] for r in rings]
    n = len(rings[0])
    faces = []
    for i in range(len(vv) - 1):
        a, b = vv[i], vv[i + 1]
        rng = range(n) if closed else range(n - 1)
        for j in rng:
            j2 = (j + 1) % n
            faces.append(bm.faces.new((a[j], a[j2], b[j2], b[j])))
    if cap_start:
        faces.append(bm.faces.new(list(reversed(vv[0]))))
    if cap_end:
        faces.append(bm.faces.new(vv[-1]))
    return vv, faces


def add_box(bm, center, size, rot=None):
    """size=(sx,sy,sz) 축 정렬 박스(로컬) → rot(Matrix 3x3) 회전 후 center 로."""
    r = bmesh.ops.create_cube(bm, size=1.0)
    vs = r["verts"]
    M = Matrix.Diagonal((size[0], size[1], size[2], 1.0))
    if rot is not None:
        M = rot.to_4x4() @ M
    M = Matrix.Translation(Vector(center)) @ M
    bmesh.ops.transform(bm, matrix=M, verts=vs)
    return vs


def add_cyl(bm, p0, p1, r0, r1=None, seg=16, cap=True):
    """p0→p1 원기둥(테이퍼)."""
    r1 = r0 if r1 is None else r1
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    L = d.length
    res = bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=seg, radius1=r0, radius2=r1, depth=L)
    q = d.normalized().to_track_quat("Z", "Y")
    M = Matrix.Translation((p0 + p1) / 2) @ q.to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=M, verts=res["verts"])
    return res["verts"]


def frame_from_z(zaxis, up_hint=Vector((0, 0, 1))):
    z = Vector(zaxis).normalized()
    x = up_hint.cross(z)
    if x.length < 1e-6:
        x = Vector((1, 0, 0))
    x.normalize()
    y = z.cross(x)
    return Matrix((x, y, z)).transposed()


def catenary_points(a, b, sag, n=18):
    a, b = Vector(a), Vector(b)
    pts = []
    for i in range(n + 1):
        t = i / n
        p = a.lerp(b, t)
        p.z -= sag * 4 * t * (1 - t)
        pts.append(p)
    return pts


def rope_curve(name, pts, radius, coll, mat, res=3):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = res
    cu.use_fill_caps = True
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for p, q in zip(sp.points, pts):
        p.co = (q.x, q.y, q.z, 1.0)
    ob = bpy.data.objects.new(name, cu)
    coll.objects.link(ob)
    if mat:
        cu.materials.append(mat)
    return ob


def solidify(ob, thick, offset=-1.0, rim=True, even=True):
    m = ob.modifiers.new("Solidify", "SOLIDIFY")
    m.thickness = thick
    m.offset = offset
    m.use_rim = rim
    m.use_even_offset = even
    m.use_quality_normals = True
    return m


def apply_modifiers(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    me.name = old.name
    bpy.data.meshes.remove(old)
    return ob


def parent_keep(child, parent):
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()


# =====================================================================================================
# 재질
# =====================================================================================================
MAT_KEYS = ["hull_wood", "hull_waterline", "roof_shell", "iron_spike", "dragon_head", "ghost_face",
            "wall_panel", "oar_wood", "mast_wood", "sail_cloth", "rope", "flag_cloth", "water",
            "stone", "ground"]
_FALLBACK_COL = {"hull_wood": (0.12, 0.08, 0.05), "hull_waterline": (0.06, 0.06, 0.04), "roof_shell": (0.06, 0.03, 0.02),
                 "iron_spike": (0.08, 0.05, 0.04), "dragon_head": (0.1, 0.25, 0.15), "ghost_face": (0.4, 0.05, 0.03),
                 "wall_panel": (0.15, 0.05, 0.03), "oar_wood": (0.2, 0.15, 0.1), "mast_wood": (0.18, 0.12, 0.08),
                 "sail_cloth": (0.5, 0.45, 0.38), "rope": (0.3, 0.25, 0.18), "flag_cloth": (0.6, 0.1, 0.1),
                 "water": (0.01, 0.03, 0.03), "stone": (0.35, 0.33, 0.3), "ground": (0.2, 0.2, 0.12)}


def _simple_mat(name, col, rough=0.6, metal=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True if m.node_tree is None else m.use_nodes
    b = m.node_tree.nodes.get("Principled BSDF")
    if b is None:
        m.node_tree.nodes.clear()
        b = m.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
        o = m.node_tree.nodes.new("ShaderNodeOutputMaterial")
        m.node_tree.links.new(b.outputs["BSDF"], o.inputs["Surface"])
    b.inputs["Base Color"].default_value = tuple(col) + (1.0,)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    m.diffuse_color = tuple(col) + (1.0,)
    return m


def load_materials(d):
    """materials/matlib.py 의 build_all() 사용. 없거나 실패하면 회색 fallback (경고)."""
    sys.path.insert(0, os.path.join(ROOT, "materials"))
    mats, used_real = {}, False
    try:
        import importlib
        import matlib  # noqa
        importlib.reload(matlib)
        rf = d["superstructure"]["roof"]
        try:
            mats = matlib.build_all(hex_cell=rf["hex_cell"], roof_arc_attr="roof_s")
        except TypeError:
            mats = matlib.build_all()
        used_real = True
    except Exception as ex:  # noqa
        print(f"[build_scene] WARNING: matlib 사용 불가 → 회색 fallback ({ex!r})")
    for k in MAT_KEYS:
        if k not in mats:
            if used_real:
                print(f"[build_scene] WARNING: matlib 에 '{k}' 없음 → fallback")
            mats[k] = _simple_mat("FB_" + k, _FALLBACK_COL[k])
    # 모델링 전용 보조 재질(구멍 속 어둠, 눈알, 이빨) — matlib 계약 밖의 작은 요소
    mats["_dark"] = _simple_mat("mdl_dark_cavity", (0.006, 0.004, 0.003), 0.9)
    mats["_eye"] = _simple_mat("mdl_eye_gloss", (0.01, 0.008, 0.006), 0.15)
    mats["_ivory"] = _simple_mat("mdl_ivory", (0.55, 0.50, 0.40), 0.45)
    mats["_eye"]["note"] = "용두 눈알"
    return mats, used_real


# =====================================================================================================
# 씬/컬렉션
# =====================================================================================================
def new_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    colls = {}
    for n in ["Hull", "Superstructure", "Details", "Rigging", "Site", "Cameras"]:
        c = bpy.data.collections.new(n)
        sc.collection.children.link(c)
        colls[n] = c
    return sc, colls


# =====================================================================================================
# 선체
# =====================================================================================================
class HullShape:
    def __init__(self, d):
        h = d["hull"]
        st = h["stations"]
        self.ymax = max(s["y"] for s in st)
        self.ymin = min(s["y"] for s in st)
        bt, stn = h["bow_transom"], h["stern_transom"]
        lo, hi = stn["y_bottom"], bt["y_bottom"]
        self.kz = Piecewise(st, "keel_z", lo, hi)
        self.bh = Piecewise(st, "bottom_half", lo, hi)
        c = station_curves(st, ["sheer_half", "sheer_z"])
        self.sh, self.sz = c["sheer_half"], c["sheer_z"]
        self.bt, self.st = bt, stn
        self.knuckles = (lo, hi)

    def transom_normal(self, y):
        """호판 바깥 법선 (ny, nz) — 아래쪽 성분 음수."""
        dz = self.kz.deriv(y)
        n = Vector((0, dz, -1.0)).normalized() if y > 0 else Vector((0, -dz, -1.0)).normalized()
        # y>0: 선수 호판, 법선 = (+Y 앞, 아래). y<0: 선미 → (−Y, 아래)
        if y > 0:
            n = Vector((0, abs(n.y), -abs(n.z)))
        else:
            n = Vector((0, -abs(n.y), -abs(n.z)))
        return n.normalized()


def build_hull(d, Q, colls, mats):
    H = HullShape(d)
    h = d["hull"]
    pw, pt = h["plank_width"], h["plank_thickness"]
    # 현측 판재 수 = 중앙단면 현측 길이 / plank_width
    side_mid = math.hypot(H.sh(0) - H.bh(0), H.sz(0) - H.kz(0))
    n_side = max(3, int(round(side_mid / pw)))
    # y 샘플: 균일 + 스테이션 + 호판 판재 이음
    special, dent_rows = [], {}
    for s in h["stations"]:
        special.append(s["y"])
    for tr, sgn in ((H.bt, 1), (H.st, -1)):
        y0, y1, n = tr["y_bottom"], tr["y_top"], tr["plank_count"]
        dy = abs(y1 - y0)
        slope_len = math.hypot(dy, tr["z_top"] - tr["z_bottom"])
        dly = PLANK_GROOVE_W / 2 * dy / slope_len
        for k in range(1, n):
            yk = y0 + (y1 - y0) * k / n
            special += [yk - dly, yk + dly]
            special.append(yk)
            dent_rows[round(yk, 5)] = True
    special = sorted(set(round(v, 5) for v in special))
    uni = list(np.arange(H.ymin, H.ymax + 1e-6, Q["y_step"]))
    ys = list(special)
    for u in uni:
        if min(abs(u - s) for s in special) > Q["y_step"] * 0.35:
            ys.append(u)
    ys = sorted(ys)

    # 단면 파라미터 (현측 홈 포함, 버텍스 수 일정)
    def side_params(side_len):
        dfrac = min(PLANK_GROOVE_W / 2 / max(side_len, 1e-3), 0.3 / n_side)
        out = [(0.0, False)]
        for k in range(n_side):
            a, b = k / n_side, (k + 1) / n_side
            a2 = a + (dfrac if k > 0 else 0.0)
            b2 = b - (dfrac if k < n_side - 1 else 0.0)
            if k > 0:
                out.append((a2, False))
            for i in range(1, Q["side_sub"]):
                out.append((a2 + (b2 - a2) * i / Q["side_sub"], False))
            if k < n_side - 1:
                out.append((b2, False))
                out.append((b, True))
        out.append((1.0, False))
        return out

    N_BOTTOM = 6
    rings = []
    for y in ys:
        bh, sh, kz, sz = H.bh(y), H.sh(y), H.kz(y), H.sz(y)
        chine, sheer = Vector((bh, kz)), Vector((sh, sz))
        sv = sheer - chine
        L = sv.length
        nrm = Vector((sv.y, -sv.x)).normalized()  # 바깥(+x) 쪽 법선
        if nrm.x < 0:
            nrm = -nrm
        pts_side = []
        for t, dent in side_params(L):
            p = chine + sv * t + nrm * (HULL_SIDE_BULGE * L * math.sin(math.pi * t))
            if dent:
                p = p - nrm * PLANK_GROOVE_D
            pts_side.append(p)
        dent_bottom = round(y, 5) in dent_rows
        tn = H.transom_normal(y) if dent_bottom else None
        ring = []
        for p in reversed(pts_side):          # 좌현 현측(위→아래)
            ring.append(Vector((-p.x, y, p.y)))
        for i in range(1, N_BOTTOM):          # 저판
            x = -bh + 2 * bh * i / N_BOTTOM
            ring.append(Vector((x, y, kz)))
        for p in pts_side:                    # 우현 현측(아래→위)
            ring.append(Vector((p.x, y, p.y)))
        if dent_bottom:
            nb0 = len(pts_side) - 1
            for j in range(nb0, nb0 + N_BOTTOM + 1):
                ring[j] = ring[j] - tn * PLANK_GROOVE_D
        rings.append(ring)
    bm = bmesh.new()
    vv, faces = loft_grid(bm, rings, closed=False, cap_start=True, cap_end=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    # 바깥 법선 확인 (중앙 저판 면은 아래를 향해야)
    bm.faces.ensure_lookup_table()
    band_top = h["waterline_stain_band"][1]
    for f in bm.faces:
        f.material_index = 1 if f.calc_center_median().z < band_top else 0
    mid = [f for f in bm.faces if abs(f.calc_center_median().y) < 0.5 and abs(f.calc_center_median().x) < 0.3]
    if mid and mid[0].normal.z > 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    hull = mesh_object("Hull", bm, colls["Hull"], [mats["hull_wood"], mats["hull_waterline"]])
    solidify(hull, pt, -1.0)

    # 갑판(가룡 돌출 갑판): sheer_z 높이, 폭 = max(sheer_half, wall.half)
    wall_st = d["superstructure"]["wall"]["stations"]
    wc = station_curves(wall_st, ["half", "top_z"])
    wy0, wy1 = min(s["y"] for s in wall_st), max(s["y"] for s in wall_st)
    dt = pt * DECK_THICK_RATIO
    drings = []
    for y in ys:
        half = wc["half"](y) if wy0 <= y <= wy1 else H.sh(y)
        half = max(half, H.sh(y))
        z = H.sz(y)
        drings.append([Vector((-half, y, z - dt)), Vector((-half, y, z)), Vector((half, y, z)), Vector((half, y, z - dt))])
    bm = bmesh.new()
    loft_grid(bm, drings, closed=True, cap_start=True, cap_end=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    deck = mesh_object("Deck", bm, colls["Hull"], [mats["hull_wood"]])

    # 가룡 머리(돌출 갑판 밑 보 끝) — 측면 실루엣 디테일
    bm = bmesh.new()
    y = wy1 - BEAM_END_SPACING / 2
    while y > wy0:
        half = max(wc["half"](y), H.sh(y))
        z = H.sz(y) - dt - BEAM_END_SIZE / 2
        for s in (-1, 1):
            inner = H.sh(y) - 0.3
            add_box(bm, (s * (inner + half + 0.05) / 2, y, z), ((half + 0.05 - inner), BEAM_END_SIZE, BEAM_END_SIZE))
        y -= BEAM_END_SPACING
    mesh_object("BeamEnds", bm, colls["Hull"], [mats["hull_wood"]], angle=30)
    return H, hull, deck, wc


# =====================================================================================================
# 상장(방패판 벽)
# =====================================================================================================
def wall_perimeter(d, wc, step):
    """평면 둘레(좌현 선수→선미, 선미막음, 우현 선미→선수, 선수막음). 각 점: (x, y, nx, ny, dent)."""
    wst = d["superstructure"]["wall"]["stations"]
    pw = d["superstructure"]["wall"]["panel_width"]
    y0, y1 = min(s["y"] for s in wst), max(s["y"] for s in wst)
    gw = PANEL_GROOVE_W / 2
    # 측면 y 목록: 패널 경계 y 에 홈 3점
    seams = list(np.arange(y1 - pw, y0 + pw * 0.5, -pw))
    ys = [(y1, False)]
    for k, s in enumerate(seams):
        prev = y1 if k == 0 else seams[k - 1]
        nsub = max(1, int(round((prev - s) / step)))
        a = prev - (gw if k > 0 else 0)
        b = s + gw
        for i in range(1, nsub):
            ys.append((a + (b - a) * i / nsub, False))
        ys += [(b, False), (s, True), (s - gw, False)]
    last = seams[-1] if seams else y1
    nsub = max(1, int(round((last - y0) / step)))
    for i in range(1, nsub):
        ys.append((last - gw + (y0 - last + gw) * i / nsub, False))
    ys.append((y0, False))

    def side(sgn, seq):
        out = []
        for y, dent in seq:
            hx = wc["half"](y)
            dh = wc["half"].deriv(y)
            n = Vector((sgn * 1.0, -sgn * dh)).normalized()
            out.append((sgn * hx, y, n.x, n.y, dent))
        return out

    def end(y, sgn_y, x_from, x_to):
        hx = abs(x_from)
        out = []
        xs = []
        nseam = int(2 * hx / pw)
        seam_x = [(-hx + 2 * hx * (k + 1) / (nseam + 1)) for k in range(nseam)]
        pts = [(x_from, False)]
        dirn = 1 if x_to > x_from else -1
        seam_x = sorted(seam_x, reverse=dirn < 0)
        for sx in seam_x:
            pts += [(sx - dirn * gw, False), (sx, True), (sx + dirn * gw, False)]
        for x, dent in pts[1:]:
            out.append((x, y, 0.0, float(sgn_y), dent))
        del xs
        return out

    port = side(-1, ys)
    stbd = side(1, list(reversed(ys)))
    per = port
    per += end(y0, -1, -wc["half"](y0), wc["half"](y0))
    per += stbd
    per += end(y1, 1, wc["half"](y1), -wc["half"](y1))
    return per, (y0, y1)


def build_wall(d, H, wc, Q, colls, mats):
    wall_d = d["superstructure"]["wall"]
    per, (y0, y1) = wall_perimeter(d, wc, Q["wall_step"])
    cols = []
    for x, y, nx, ny, dent in per:
        ye = min(max(y, y0), y1)
        zb, zt = H.sz(ye), wc["top_z"](ye)
        p = Vector((x, y, 0))
        if dent:
            p -= Vector((nx, ny, 0)) * PANEL_GROOVE_D
        cols.append([Vector((p.x, p.y, zb + (zt - zb) * k / WALL_VSEG)) for k in range(WALL_VSEG + 1)])
    # 링 = 세로 줄(열) → loft 의 '링' 은 열, closed 둘레
    bm = bmesh.new()
    vv = [[bm.verts.new(p) for p in c] for c in cols]
    n = len(vv)
    for i in range(n):
        a, b = vv[i], vv[(i + 1) % n]
        for k in range(WALL_VSEG):
            bm.faces.new((a[k], b[k], b[k + 1], a[k + 1]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    # 바깥 확인: 좌현 측면 면 법선 x<0
    bm.faces.ensure_lookup_table()
    test = [f for f in bm.faces if abs(f.calc_center_median().y) < 1 and f.calc_center_median().x < 0]
    if test and test[0].normal.x > 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    wall = mesh_object("Wall", bm, colls["Superstructure"], [mats["wall_panel"]], angle=30)
    solidify(wall, wall_d["thickness"], -1.0)

    # --- 구멍(포혈·노 구멍) Boolean
    g = d["gun_ports"]
    sz = g["size"]
    cut = bmesh.new()
    frames = bmesh.new()
    thick = wall_d["thickness"]

    def side_frame(y, sgn):
        hx = wc["half"](y)
        dh = wc["half"].deriv(y)
        n = Vector((sgn, -sgn * dh, 0)).normalized()
        t = Vector((0, 0, 1)).cross(n).normalized()
        R = Matrix((t, Vector((0, 0, 1)), n)).transposed()  # local x=t, y=up, z=n
        return Vector((sgn * hx, y, 0)), R

    ports = []
    for p in g["side"]:
        for sgn in (-1, 1):
            base, R = side_frame(p["y"], sgn)
            ports.append((Vector((base.x, base.y, p["z"])), R))
    for key, ny in (("bow", 1), ("stern", -1)):
        for p in g.get(key, []):
            n = Vector((0, ny, 0))
            t = Vector((0, 0, 1)).cross(n).normalized()
            R = Matrix((t, Vector((0, 0, 1)), n)).transposed()
            yy = y1 if ny > 0 else y0
            ports.append((Vector((p["x"], yy, p["z"])), R))
    fw = sz * PORT_FRAME_RATIO
    for c, R in ports:
        add_box(cut, c, (sz, sz, thick * 6), R)
        # 테(4변)
        nrm = R.col[2]
        cc = c + nrm * (PORT_FRAME_DEPTH / 2)
        tx, up = R.col[0], R.col[1]
        o = sz / 2 + fw / 2
        add_box(frames, cc + up * o, (sz + 2 * fw, fw, PORT_FRAME_DEPTH + 0.02), R)
        add_box(frames, cc - up * o, (sz + 2 * fw, fw, PORT_FRAME_DEPTH + 0.02), R)
        add_box(frames, cc + tx * o, (fw, sz, PORT_FRAME_DEPTH + 0.02), R)
        add_box(frames, cc - tx * o, (fw, sz, PORT_FRAME_DEPTH + 0.02), R)
    o = d["oars"]
    seg = Q["cyl"]
    for y in o["y"]:
        for sgn in (-1, 1):
            base, R = side_frame(y, sgn)
            nrm = R.col[2]
            c = Vector((base.x, base.y, o["port_z"]))
            add_cyl(cut, c - nrm * thick * 3, c + nrm * thick * 3, OAR_PORT_R, seg=seg)
            # 노 구멍 테(링)
            add_cyl(frames, c - nrm * 0.0, c + nrm * PORT_FRAME_DEPTH, OAR_PORT_R * 1.7, seg=seg)
    cutter = mesh_object("_cutter", cut, colls["Superstructure"], smooth=False)
    # 노 구멍 테는 가운데가 막힘 → 같은 cutter 로 뚫음
    fr = mesh_object("PortFrames", frames, colls["Superstructure"], [mats["hull_wood"]], angle=30)
    for ob in (wall, fr):
        b = ob.modifiers.new("Holes", "BOOLEAN")
        b.operation = "DIFFERENCE"
        b.solver = "EXACT"
        b.object = cutter
        apply_modifiers(ob)
    bpy.data.objects.remove(cutter)

    # --- 띠장(하단·상단 rail)
    bm = bmesh.new()
    for z_of, label in ((lambda y: H.sz(y), "bot"), (lambda y: wc["top_z"](y) - WALL_RAIL_H, "top")):
        rings = []
        for x, y, nx, ny, dent in per[::1]:
            if dent:
                continue
            ye = min(max(y, y0), y1)
            zb = z_of(ye)
            n = Vector((nx, ny, 0))
            p = Vector((x, y, 0))
            pin, pout = p - n * 0.02, p + n * WALL_RAIL_OUT
            rings.append([Vector((pin.x, pin.y, zb)), Vector((pout.x, pout.y, zb)),
                          Vector((pout.x, pout.y, zb + WALL_RAIL_H)), Vector((pin.x, pin.y, zb + WALL_RAIL_H))])
        rings.append(rings[0])
        vv, _ = loft_grid(bm, rings, closed=True)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    mesh_object("WallRails", bm, colls["Superstructure"], [mats["hull_wood"]], angle=30)
    return wall, (y0, y1)


# =====================================================================================================
# 개판(거북등 지붕)
# =====================================================================================================
class RoofShape:
    def __init__(self, d):
        rf = d["superstructure"]["roof"]
        self.rf = rf
        st = rf["stations"]
        self.c = station_curves(st, ["half", "eave_z", "ridge_z"])
        self.p = rf["profile_exponent"]
        self.y0, self.y1 = min(s["y"] for s in st), max(s["y"] for s in st)

    def point(self, y, th):
        """th ∈ [0, π]: 0=우현 처마, π/2=용마루, π=좌현 처마."""
        hx, e, r = self.c["half"](y), self.c["eave_z"](y), self.c["ridge_z"](y)
        c, s = math.cos(th), math.sin(th)
        x = hx * math.copysign(abs(c) ** (2.0 / self.p), c)
        z = e + (r - e) * abs(s) ** (2.0 / self.p)
        return Vector((x, y, z))

    def table(self, y, n=400):
        """th 등간격 표 → (th, s(호길이, 좌현 음수), point)"""
        ths = np.linspace(math.pi, 0, n)
        pts = [self.point(y, t) for t in ths]
        s = [0.0]
        for a, b in zip(pts, pts[1:]):
            s.append(s[-1] + (b - a).length)
        s = np.array(s)
        mid = np.interp(0.0, [p.x for p in pts], s)
        return ths, s - mid, pts

    def at_s(self, y, sq, tab=None):
        ths, s, pts = tab or self.table(y)
        th = float(np.interp(sq, s, ths))
        p = self.point(y, th)
        # 법선: 접선(호) × y축 근사 → 수치 미분
        e = 1e-3
        dth = self.point(y, th + e) - self.point(y, th - e)
        dy = self.point(y + e, th) - self.point(y - e, th)
        n = dy.cross(dth).normalized()
        if n.z < 0:
            n = -n
        return p, n


def build_roof(d, Q, colls, mats):
    R = RoofShape(d)
    rf = d["superstructure"]["roof"]
    ys = list(np.arange(R.y1, R.y0 - 1e-6, -Q["y_step"]))
    if abs(ys[-1] - R.y0) > 1e-4:
        ys.append(R.y0)
    for s in rf["stations"]:
        ys.append(s["y"])
    ys = sorted(set(round(v, 5) for v in ys), reverse=True)
    n = Q["roof_n"]
    rings, svals = [], []
    for y in ys:
        ths = np.linspace(math.pi, 0, n + 1)
        pts = [R.point(y, t) for t in ths]
        s = [0.0]
        for a, b in zip(pts, pts[1:]):
            s.append(s[-1] + (b - a).length)
        s = np.array(s)
        s -= s[n // 2] if n % 2 == 0 else np.interp(0.0, [p.x for p in pts], s)
        rings.append(pts)
        svals.append(s)
    bm = bmesh.new()
    lay = bm.verts.layers.float.new("roof_s")   # 레이어는 버텍스 생성 전에(참조 무효화 방지)
    vv, _ = loft_grid(bm, rings, closed=False, cap_start=True, cap_end=True)
    for row, srow in zip(vv, svals):
        for v, sv in zip(row, srow):
            v[lay] = float(sv) if abs(sv) > 2e-4 else 2e-4
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.faces.ensure_lookup_table()
    top = max(bm.faces, key=lambda f: f.calc_center_median().z)
    if top.normal.z < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    roof = mesh_object("Roof", bm, colls["Superstructure"], [mats["roof_shell"]], angle=40)
    solidify(roof, rf["thickness"], -1.0)

    # --- 통로(용마루 길이방향 + 십자 횡방향) : 판재 띠
    cw = rf["cross_walkway_width"]
    cy = rf["cross_walkway_y"]
    nb = max(2, int(round(cw / WALKWAY_BOARD)))
    bm = bmesh.new()

    def strip_long():
        rr = []
        for y in ys:
            tab = R.table(y, 200)
            row = []
            for k in range(nb + 1):
                sq = -cw / 2 + cw * k / nb
                p, nn = R.at_s(y, sq, tab)
                row.append(p + nn * WALKWAY_RAISE)
            rr.append(row)
        return rr

    loft_grid(bm, strip_long())
    # 횡 통로
    yy = [cy + cw / 2 - cw * k / nb for k in range(nb + 1)]
    tabs = [R.table(y, 300) for y in yy]
    smax = min(t[1][-1] for t in tabs) - 0.05
    smin = max(t[1][0] for t in tabs) + 0.05
    ns = max(8, int((smax - smin) / 0.15))
    rr = []
    for y, tab in zip(yy, tabs):
        row = []
        for k in range(ns + 1):
            sq = smin + (smax - smin) * k / ns
            p, nn = R.at_s(y, sq, tab)
            row.append(p + nn * (WALKWAY_RAISE * 1.4))
        rr.append(row)
    loft_grid(bm, rr)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    walk = mesh_object("Walkways", bm, colls["Superstructure"], [mats["hull_wood"]], angle=40)
    solidify(walk, WALKWAY_THICK, -1.0)

    # --- 해치
    bm = bmesh.new()
    for hc in rf.get("hatches", []):
        p, nn = R.at_s(hc["y"], 0.0)
        add_box(bm, p + Vector((0, 0, HATCH_H / 2)), (hc["w"], hc["l"], HATCH_H))
        add_box(bm, p + Vector((0, 0, HATCH_H + 0.03)), (hc["w"] + 0.08, hc["l"] + 0.08, 0.06))
    mesh_object("Hatches", bm, colls["Superstructure"], [mats["hull_wood"]], angle=30)

    # --- 철첨: 점 + GN Instance on Points
    sp = rf["spikes"]
    spacing = sp["spacing"]
    lane = sp["exclude_ridge_lane"]
    masts = [(m["y"], m["diameter"]) for m in d["masts"]]
    rnd = random.Random(SEED)
    P, N, S = [], [], []
    y = R.y1 - spacing * SPIKE_EDGE_MARGIN * 2
    row = 0
    while y > R.y0 + spacing * SPIKE_EDGE_MARGIN * 2:
        tab = R.table(y, 300)
        s_lo, s_hi = tab[1][0] + spacing * SPIKE_EDGE_MARGIN, tab[1][-1] - spacing * SPIKE_EDGE_MARGIN
        off = (spacing / 2) if row % 2 else 0.0
        sq = math.floor(s_lo / spacing) * spacing + off
        in_cross = abs(y - cy) < cw / 2 + spacing * 0.3
        while sq < s_hi:
            if sq > s_lo and abs(sq) > lane / 2 + spacing * 0.3 and not in_cross:
                ok = True
                for hc in rf.get("hatches", []):
                    if abs(y - hc["y"]) < hc["l"] / 2 + spacing and abs(sq) < hc["w"] / 2 + spacing:
                        ok = False
                for my, md in masts:
                    if math.hypot(sq, y - my) < md * 2:
                        ok = False
                if ok:
                    p, nn = R.at_s(y, sq, tab)
                    P.append(p)
                    N.append(nn)
                    S.append(1.0 + rnd.uniform(-SPIKE_SCALE_JITTER, SPIKE_SCALE_JITTER))
            sq += spacing
        y -= spacing * math.sqrt(3) / 2   # 엇갈림(삼각) 배열
        row += 1
    me = bpy.data.meshes.new("SpikePoints")
    me.vertices.add(len(P))
    me.vertices.foreach_set("co", [c for p in P for c in p])
    an = me.attributes.new("spike_n", "FLOAT_VECTOR", "POINT")
    an.data.foreach_set("vector", [c for n_ in N for c in n_])
    asc = me.attributes.new("spike_s", "FLOAT", "POINT")
    asc.data.foreach_set("value", S)
    sob = bpy.data.objects.new("Spikes", me)
    colls["Superstructure"].objects.link(sob)
    me.materials.append(mats["iron_spike"])
    ng = spike_nodegroup(sp, mats["iron_spike"])
    mod = sob.modifiers.new("SpikeInstances", "NODES")
    mod.node_group = ng
    return R, roof, len(P)


def spike_nodegroup(sp, mat):
    ng = bpy.data.node_groups.new("GN_Spikes", "GeometryNodeTree")
    ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    nd = ng.nodes
    gi = nd.new("NodeGroupInput")
    go = nd.new("NodeGroupOutput")
    cone = nd.new("GeometryNodeMeshCone")
    cone.inputs["Vertices"].default_value = SPIKE_SIDES
    cone.inputs["Radius Bottom"].default_value = sp["base_radius"]
    cone.inputs["Radius Top"].default_value = 0.0
    cone.inputs["Depth"].default_value = sp["height"]
    tr = nd.new("GeometryNodeTransform")
    tr.inputs["Translation"].default_value = (0, 0, sp["height"] / 2 - 0.01)
    sm = nd.new("GeometryNodeSetMaterial")
    sm.inputs["Material"].default_value = mat
    na = nd.new("GeometryNodeInputNamedAttribute")
    na.data_type = "FLOAT_VECTOR"
    na.inputs["Name"].default_value = "spike_n"
    ns = nd.new("GeometryNodeInputNamedAttribute")
    ns.data_type = "FLOAT"
    ns.inputs["Name"].default_value = "spike_s"
    al = nd.new("FunctionNodeAlignRotationToVector")
    al.axis = "Z"
    iop = nd.new("GeometryNodeInstanceOnPoints")
    L = ng.links
    L.new(cone.outputs["Mesh"], tr.inputs["Geometry"])
    L.new(tr.outputs["Geometry"], sm.inputs["Geometry"])
    L.new(gi.outputs[0], iop.inputs["Points"])
    L.new(sm.outputs["Geometry"], iop.inputs["Instance"])
    L.new(na.outputs["Attribute"], al.inputs["Vector"])
    L.new(al.outputs["Rotation"], iop.inputs["Rotation"])
    L.new(ns.outputs["Attribute"], iop.inputs["Scale"])
    L.new(iop.outputs["Instances"], go.inputs[0])
    return ng


# =====================================================================================================
# 용두
# =====================================================================================================
def _superring(cy, cz, w, h, n, e=2.4, y=0.0, zoff_fn=None):
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        c, s = math.cos(a), math.sin(a)
        x = w * math.copysign(abs(c) ** (2 / e), c)
        z = h * math.copysign(abs(s) ** (2 / e), s)
        pts.append(Vector((x, y, cz + z)))
    return pts


def _smooth_profile(keys, u):
    """keys: [(u, val)] → 부드러운 보간 (PCHIP)."""
    return Curve1D([k[0] for k in keys], [k[1] for k in keys])(u)


def build_dragon(d, Q, colls, mats):
    dh = d["dragon_head"]
    L, Hh, W, mo = dh["length"], dh["height"], dh["width"], dh["mouth_open"]
    hw = W / 2
    nsec = Q["dragon_sec"]
    nr = DRAGON_RING
    bm = bmesh.new()
    # 로컬: +Y 앞(주둥이), +Z 위, X 좌우. 원점 = base
    # 목+머리통 (u: -0.3..0.62)
    neck_w = [(-0.3, 0.55), (0.0, 0.52), (0.22, 0.44), (0.40, 0.50), (0.52, 0.52), (0.62, 0.40)]
    neck_h = [(-0.3, 0.50), (0.0, 0.45), (0.22, 0.38), (0.40, 0.42), (0.52, 0.40), (0.62, 0.26)]
    neck_c = [(-0.3, -0.05), (0.0, 0.0), (0.22, 0.05), (0.40, 0.13), (0.52, 0.14), (0.62, 0.12)]
    rings = []
    for i in range(nsec + 1):
        u = -0.3 + 0.92 * i / nsec
        w = _smooth_profile(neck_w, u) * hw
        h = _smooth_profile(neck_h, u) * Hh
        c = _smooth_profile(neck_c, u) * Hh
        rings.append(_superring(0, c, w, h, nr, 2.3, y=u * L))
    loft_grid(bm, rings, closed=True, cap_start=True, cap_end=True)
    # 입 축(mouth line): u=0.5 부터 벌어짐
    us = 0.50
    mz0 = 0.02 * Hh

    def gap(u):
        return max(0.0, (u - us) / (1 - us)) * mo / 2

    # 위턱 (u 0.45..1.0): 아래면 = 입선+gap, 위면 높이 감소, 코끝 살짝 들림
    up_w = [(0.45, 0.46), (0.65, 0.40), (0.85, 0.34), (0.97, 0.30), (1.0, 0.22)]
    up_h = [(0.45, 0.30), (0.65, 0.22), (0.85, 0.17), (0.95, 0.19), (1.0, 0.12)]
    rings = []
    for i in range(nsec + 1):
        u = 0.45 + 0.55 * i / nsec
        w = _smooth_profile(up_w, u) * hw
        h = _smooth_profile(up_h, u) * Hh
        base = mz0 + gap(u)
        rings.append(_superring(0, base + h, w, h, nr, 2.6, y=u * L))
    loft_grid(bm, rings, closed=True, cap_start=True, cap_end=True)
    # 아래턱 (u 0.45..0.95), 아래로 벌어짐
    lo_w = [(0.45, 0.40), (0.7, 0.33), (0.9, 0.26), (0.95, 0.20)]
    lo_h = [(0.45, 0.14), (0.7, 0.10), (0.9, 0.08), (0.95, 0.05)]
    rings = []
    for i in range(nsec + 1):
        u = 0.45 + 0.50 * i / nsec
        w = _smooth_profile(lo_w, u) * hw
        h = _smooth_profile(lo_h, u) * Hh
        top = mz0 - gap(u) * 1.15
        rings.append(_superring(0, top - h, w, h, nr, 2.6, y=u * L))
    loft_grid(bm, rings, closed=True, cap_start=True, cap_end=True)

    def tube(path, radii, ring_n=10):
        rr = []
        for k, (p, r) in enumerate(zip(path, radii)):
            t = (path[min(k + 1, len(path) - 1)] - path[max(k - 1, 0)]).normalized()
            F = frame_from_z(t, Vector((0, 0, 1)) if abs(t.z) < 0.95 else Vector((0, 1, 0)))
            rr.append([p + F @ Vector((r * math.cos(2 * math.pi * j / ring_n), r * math.sin(2 * math.pi * j / ring_n), 0))
                       for j in range(ring_n)])
        loft_grid(bm, rr, closed=True, cap_start=True, cap_end=True)

    # 뿔 2: 머리 위 뒤쪽에서 뒤·위·바깥으로 휘어짐
    for sgn in (-1, 1):
        pth, rad = [], []
        for k in range(9):
            t = k / 8
            pth.append(Vector((sgn * hw * (0.30 + 0.35 * t), L * (0.44 - 0.42 * t), Hh * (0.48 + 0.50 * t - 0.12 * t * t))))
            rad.append(Hh * 0.075 * (1 - 0.85 * t) + 0.004)
        tube(pth, rad, 10)
        # 갈래 뿔
        pth2, rad2 = [], []
        for k in range(5):
            t = k / 4
            b = pth[4]
            pth2.append(b + Vector((sgn * hw * 0.15 * t, -L * 0.04 * t, Hh * 0.20 * t)))
            rad2.append(Hh * 0.035 * (1 - 0.8 * t) + 0.003)
        tube(pth2, rad2, 8)
    # 눈두덩(눈썹 융기)
    for sgn in (-1, 1):
        pth, rad = [], []
        for k in range(7):
            t = k / 6
            pth.append(Vector((sgn * hw * (0.42 - 0.06 * t), L * (0.46 + 0.16 * t), Hh * (0.47 - 0.10 * t + 0.08 * math.sin(math.pi * t)))))
            rad.append(Hh * 0.06 * math.sin(math.pi * (0.15 + 0.7 * t)))
        tube(pth, rad, 10)
    # 콧방울
    for sgn in (-1, 1):
        c = Vector((sgn * hw * 0.17, L * 0.97, mz0 + gap(0.97) + Hh * 0.30))
        r = bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=7, radius=Hh * 0.075)
        bmesh.ops.translate(bm, verts=r["verts"], vec=c)
    # 턱수염: 아래턱 밑에서 뒤·아래로 말려 늘어지는 짧은 다발 5개 (끝이 앞으로 살짝 말림)
    for k in range(5):
        xo = (k - 2) / 2 * hw * 0.40
        pth, rad = [], []
        for j in range(8):
            t = j / 7
            pth.append(Vector((xo * (1 + 0.4 * t), L * (0.74 - 0.16 * t + 0.06 * t * t - 0.025 * abs(k - 2)),
                               mz0 - gap(0.74) * 1.15 - Hh * (0.15 + 0.20 * t))))
            rad.append(Hh * 0.04 * (1 - 0.75 * t) + 0.004)
        tube(pth, rad, 8)
    # 갈기: 목 뒤·옆 불꽃 판(삼각 지느러미)
    for k in range(6):
        u = 0.30 - 0.12 * k
        for sgn in (-1, 1):
            root = Vector((sgn * hw * 0.42, u * L, Hh * (0.30 - 0.02 * k)))
            tip = root + Vector((sgn * hw * 0.55, -L * 0.18, Hh * 0.22))
            a = root + Vector((0, L * 0.07, 0))
            b = root - Vector((0, L * 0.07, 0))
            th = Vector((0, 0, 0.015))
            vs = [bm.verts.new(p) for p in (a - th, b - th, tip - th, a + th, b + th, tip + th)]
            bm.faces.new((vs[0], vs[1], vs[2]))
            bm.faces.new((vs[5], vs[4], vs[3]))
            bm.faces.new((vs[0], vs[3], vs[4], vs[1]))
            bm.faces.new((vs[1], vs[4], vs[5], vs[2]))
            bm.faces.new((vs[2], vs[5], vs[3], vs[0]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    base = Vector(dh["base"])
    rot = Matrix.Rotation(math.radians(dh["pitch_deg"]), 4, "X")
    head = mesh_object("DragonHead", bm, colls["Details"], [mats["dragon_head"]], angle=70)
    head.matrix_world = Matrix.Translation(base) @ rot
    sub = head.modifiers.new("Subdiv", "SUBSURF")
    sub.levels = Q["subdiv"]
    sub.render_levels = Q["subdiv"]

    # 눈알
    bm = bmesh.new()
    for sgn in (-1, 1):
        r = bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=Hh * 0.085)
        bmesh.ops.translate(bm, verts=r["verts"], vec=Vector((sgn * hw * 0.44, L * 0.56, Hh * 0.36)))
    eyes = mesh_object("DragonEyes", bm, colls["Details"], [mats["_eye"]], angle=80)
    eyes.matrix_world = head.matrix_world.copy()
    parent_keep(eyes, head)
    # 이빨(위·아래 턱 가장자리 원뿔) + 송곳니
    bm = bmesh.new()
    for jaw in (1, -1):
        for k in range(6):
            u = 0.58 + 0.065 * k
            for sgn in (-1, 1):
                w = _smooth_profile(up_w if jaw > 0 else lo_w, u) * hw * 0.82
                z = mz0 + gap(u) if jaw > 0 else mz0 - gap(u) * 1.15
                ln = Hh * (0.09 if k in (0, 5) else 0.045)
                p0 = Vector((sgn * w, u * L, z + jaw * 0.01))
                add_cyl(bm, p0, p0 + Vector((0, 0, -jaw * ln)), Hh * 0.022, 0.002, seg=6)
    teeth = mesh_object("DragonTeeth", bm, colls["Details"], [mats["_ivory"]], angle=60)
    teeth.matrix_world = head.matrix_world.copy()
    parent_keep(teeth, head)
    # 입 속(어두운 구멍: 연기 분출 포혈)
    bm = bmesh.new()
    r = bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=1.0)
    bmesh.ops.scale(bm, vec=Vector((hw * 0.32, L * 0.28, max(mo * 0.45, 0.05))), verts=r["verts"])
    bmesh.ops.translate(bm, verts=r["verts"], vec=Vector((0, L * 0.70, mz0)))
    mouth = mesh_object("DragonMouth", bm, colls["Details"], [mats["_dark"]])
    mouth.matrix_world = head.matrix_world.copy()
    parent_keep(mouth, head)
    # 수염(긴 곡선 2가닥)
    for sgn in (-1, 1):
        pts = []
        for k in range(14):
            t = k / 13
            pts.append(Vector((sgn * hw * (0.25 + 0.9 * t), L * (0.95 - 0.55 * t), Hh * (0.32 + 0.15 * math.sin(math.pi * t * 1.3) - 0.3 * t))))
        pts = [head.matrix_world @ p for p in pts]
        wob = rope_curve(f"DragonWhisker_{'L' if sgn < 0 else 'R'}", pts, 0.012, colls["Details"], mats["dragon_head"])
        parent_keep(wob, head)
    return head


# =====================================================================================================
# 귀면
# =====================================================================================================
def build_ghost_face(d, H, Q, colls, mats):
    gf = d["ghost_face"]
    W, Hf = gf["width"], gf["height"]
    nx, nz = Q["ghost"]
    # 부조 높이 함수 (Generated x,z 0..1 기준 — matlib.ghost_face 의 그림 위치와 맞춤)

    def g(x, z, sx, sz, cx, cz):
        return math.exp(-(((x - cx) / sx) ** 2 + ((z - cz) / sz) ** 2))

    def relief(u, v):
        dx = abs(u - 0.5)
        r = 0.0
        # 판 외곽 둥근 테(가장자리 낮아짐)
        edge = min(u, 1 - u, v, 1 - v)
        base = min(1.0, edge / 0.06) ** 0.5
        r += 0.25 * base
        # 이마·볼 볼록
        r += 0.25 * g(u, v, 0.35, 0.35, 0.5, 0.55)
        # 눈알 (dx 0.2, gz 0.64)
        for cx in (0.3, 0.7):
            r += 0.55 * g(u, v, 0.09, 0.075, cx, 0.64)
        # 눈썹 융기
        bz = 0.80 + 0.25 * dx
        if 0.05 < dx < 0.38:
            r += 0.35 * math.exp(-((v - bz) / 0.04) ** 2)
        # 코
        r += 0.45 * g(u, v, 0.07, 0.09, 0.5, 0.50)
        # 입(오목)
        if dx < 0.33:
            r -= 0.30 * math.exp(-((v - 0.27) / 0.07) ** 2)
        # 이빨 줄 (위/아래 입술 근처)
        tf = (u * 11.0) % 1.0
        if dx < 0.30 and abs(v - 0.27) < 0.085:
            r += 0.18 * math.exp(-((tf - 0.5) / 0.22) ** 2)
        # 송곳니 (dx=0.24, 위로)
        for cx in (0.26, 0.74):
            if 0.18 < v < 0.47:
                r += 0.25 * g(u, v, 0.03, 0.12, cx, 0.33)
        return r * base

    bm = bmesh.new()
    grid = []
    for j in range(nz + 1):
        v = j / nz
        row = []
        for i in range(nx + 1):
            u = i / nx
            x = (u - 0.5) * W
            z = (v - 0.5) * Hf
            row.append(Vector((x, GHOST_BACKING + GHOST_RELIEF * relief(u, v), z)))
        grid.append(row)
    vv, faces = loft_grid(bm, grid)
    # 뒷판
    back = [bm.verts.new(Vector((p.x, 0.0, p.z))) for p in (grid[0][0], grid[0][-1], grid[-1][-1], grid[-1][0])]
    bm.faces.new(back)
    # 테두리 측면
    border = [vv[0][i] for i in range(nx + 1)] + [vv[j][nx] for j in range(1, nz + 1)] + \
             [vv[nz][i] for i in range(nx - 1, -1, -1)] + [vv[j][0] for j in range(nz - 1, 0, -1)]
    bset = []
    for v in border:
        bset.append(bm.verts.new(Vector((v.co.x, 0.0, v.co.z))))
    nb = len(border)
    for k in range(nb):
        bm.faces.new((border[k], border[(k + 1) % nb], bset[(k + 1) % nb], bset[k]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ob = mesh_object("GhostFace", bm, colls["Details"], [mats["ghost_face"]], angle=60)
    # 배치: 호판 표면(x=0)에서 center.z 높이 지점 찾기 → 법선 방향
    zc = gf["center"][2]
    yb = H.bt["y_bottom"]
    lo, hi = yb, H.ymax
    for _ in range(60):
        m = (lo + hi) / 2
        if H.kz(m) < zc:
            lo = m
        else:
            hi = m
    yc = (lo + hi) / 2
    n = H.transom_normal(yc)          # 바깥(앞·아래)
    upslope = Vector((0, 1.0, H.kz.deriv(yc))).normalized()
    xax = Vector((1, 0, 0))
    M = Matrix((xax, n, upslope)).transposed()   # local x→X, local +Y→n, local Z→upslope
    ob.matrix_world = Matrix.Translation(Vector((gf["center"][0], yc, zc)) + n * 0.005) @ M.to_4x4()
    ob["placed_center"] = (gf["center"][0], yc, zc)
    ob["normal_tilt_deg_geometry"] = math.degrees(math.atan2(n.z, n.y))
    return ob


# =====================================================================================================
# 노
# =====================================================================================================
def build_oars(d, wc, Q, colls, mats):
    o = d["oars"]
    Lt = o["length"]
    li = Lt * o["inboard_fraction"]
    lo = Lt - li
    bl, bw = o["blade_length"], o["blade_width"]
    seg = max(8, Q["cyl"] // 2)
    bm = bmesh.new()
    # 로컬 Z = 자루 축(안쪽 끝 −li, 바깥 끝 +lo). 원점 = 노 구멍.
    add_cyl(bm, (0, 0, -li), (0, 0, lo - bl * 0.85), OAR_SHAFT_R * 0.85, OAR_SHAFT_R, seg=seg)
    # 노손(손잡이 가로대)
    add_cyl(bm, (-OAR_HANDLE_LEN / 2, 0, -li + 0.08), (OAR_HANDLE_LEN / 2, 0, -li + 0.08), OAR_SHAFT_R * 0.6, seg=seg)
    # 노 날: 자루 쪽 좁고 끝이 넓은 판 (단면 렌즈형)
    rings = []
    nseg = 8
    for k in range(nseg + 1):
        t = k / nseg
        z = lo - bl + bl * t
        w = (OAR_SHAFT_R * 1.6 + (bw / 2 - OAR_SHAFT_R * 1.6) * min(1.0, t * 2.2)) * (1 - 0.15 * max(0, t - 0.9) / 0.1)
        th = OAR_BLADE_T / 2 * (1.25 - 0.5 * t)
        ring = []
        for j in range(12):
            a = 2 * math.pi * j / 12
            ring.append(Vector((w * math.cos(a), th * math.sin(a) * (1 if abs(math.cos(a)) < 0.98 else 0.4), z)))
        rings.append(ring)
    loft_grid(bm, rings, closed=True, cap_start=True, cap_end=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    auto_smooth(bm, 40)
    me = bpy.data.meshes.new("Oar")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mats["oar_wood"])
    a = math.radians(o["angle_deg"])
    obs = []
    for i, y in enumerate(o["y"]):
        for sgn in (-1, 1):
            hx = wc["half"](y)
            out_h = lo * math.cos(a)
            dirv = Vector((sgn * out_h, -OAR_AFT_SWEEP, -lo * math.sin(a))).normalized()
            F = frame_from_z(dirv, Vector((0, 0, 1)))
            # 날 너비축(로컬 X) = 수평 접선 → 날 면이 대략 위/아래를 향함
            ob = bpy.data.objects.new(f"Oar_{'P' if sgn < 0 else 'S'}{i:02d}", me)
            ob.matrix_world = Matrix.Translation((sgn * hx, y, o["port_z"])) @ F.to_4x4()
            colls["Details"].objects.link(ob)
            obs.append(ob)
    return obs


# =====================================================================================================
# 돛대·돛·삭구·깃발
# =====================================================================================================
def build_rigging(d, H, wc, R, Q, colls, mats):
    seg = Q["cyl"]
    masts = []
    roof_ridge = R.c["ridge_z"]
    for i, m in enumerate(d["masts"]):
        r0 = m["diameter"] / 2
        r1 = r0 * MAST_TOP_TAPER
        Hm = m["height"]
        bm = bmesh.new()
        add_cyl(bm, (0, 0, 0), (0, 0, Hm), r0, r1, seg=seg)
        # 돛대 끝 꼭지 + 쇠띠
        add_cyl(bm, (0, 0, Hm), (0, 0, Hm + r1 * 1.5), r1 * 1.1, r1 * 0.3, seg=seg)
        mo = mesh_object(f"Mast{i}", bm, colls["Rigging"], [mats["mast_wood"]], angle=50)
        tilt = math.radians(MAST_LOWERED_TILT_DEG) if m.get("lowered") else 0.0
        mo.matrix_world = Matrix.Translation((0, m["y"], m["base_z"])) @ Matrix.Rotation(-tilt, 4, "X")
        # 쇠띠(밴드) & 지붕 관통부 칼라
        bm = bmesh.new()
        zr = roof_ridge(m["y"]) - m["base_z"]
        for zb in (zr + 0.25, zr + 1.2, Hm * 0.55, Hm - YARD_DROP - 0.5):
            rr = r0 + (r1 - r0) * zb / Hm
            add_cyl(bm, (0, 0, zb), (0, 0, zb + 0.07), rr * 1.07, seg=seg)
        bands = mesh_object(f"Mast{i}_Bands", bm, colls["Rigging"], [mats["iron_spike"]], angle=50)
        bands.matrix_world = mo.matrix_world.copy()
        parent_keep(bands, mo)
        bm = bmesh.new()
        add_cyl(bm, (0, 0, zr - 0.25), (0, 0, zr + 0.18), r0 * 1.9, r0 * 1.5, seg=seg)
        collar = mesh_object(f"Mast{i}_Partner", bm, colls["Rigging"], [mats["hull_wood"]], angle=50)
        collar.matrix_world = Matrix.Translation((0, m["y"], m["base_z"]))
        # 활대(로컬 Z 결 → X 방향으로 눕힘)
        sw = m["sail"]["w"]
        yl = sw * YARD_OVER
        yr = r0 * YARD_R_RATIO
        zy = Hm - YARD_DROP
        yfwd = r0 + yr + 0.02
        bm = bmesh.new()
        add_cyl(bm, (0, 0, -yl / 2), (0, 0, yl / 2), yr * 0.7, seg=seg)
        add_cyl(bm, (0, 0, -yl / 4), (0, 0, yl / 4), yr, seg=seg)
        yard = mesh_object(f"Yard{i}", bm, colls["Rigging"], [mats["mast_wood"]], angle=50)
        yard.matrix_world = mo.matrix_world @ Matrix.Translation((0, yfwd, zy)) @ Matrix.Rotation(math.pi / 2, 4, "Y")
        parent_keep(yard, mo)
        # 접은 돛: 활대 밑 말린 원통(묶음 사이 볼록)
        fr = FURL_DIAM / 2
        bm = bmesh.new()
        nx = 48 if Q["cyl"] > 16 else 28
        rings = []
        for k in range(nx + 1):
            t = k / nx
            x = -sw / 2 + sw * t
            ph = (t * FURL_TIES) % 1.0
            bulge = 1.0 + 0.22 * math.sin(math.pi * ph) - 0.08
            taper = math.sin(math.pi * min(1.0, 0.08 + 0.92 * t) ) ** 0.25
            rr = fr * bulge * (0.55 + 0.45 * taper)
            sag = 0.10 * fr * math.sin(math.pi * t)
            ring = [Vector((x, yfwd + rr * math.cos(2 * math.pi * j / 14) * 0.9,
                            zy - yr - fr - sag + rr * math.sin(2 * math.pi * j / 14))) for j in range(14)]
            rings.append(ring)
        loft_grid(bm, rings, closed=True, cap_start=True, cap_end=True)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        sail = mesh_object(f"SailFurled{i}", bm, colls["Rigging"], [mats["sail_cloth"]], angle=60)
        sail.matrix_world = mo.matrix_world.copy()
        parent_keep(sail, mo)
        # 묶음 끈(토러스)
        bm = bmesh.new()
        for k in range(FURL_TIES + 1):
            x = -sw / 2 + sw * k / FURL_TIES
            x = max(-sw / 2 + 0.1, min(sw / 2 - 0.1, x))
            ring = []
            for j in range(12):
                a = 2 * math.pi * j / 12
                ring.append(Vector((x, yfwd + (fr * 0.95) * math.cos(a), zy - yr - fr + (fr + yr * 0.9) * math.sin(a))))
            rings = []
            for dx in (-0.025, 0.025):
                rings.append([p + Vector((dx, 0, 0)) for p in ring])
            # 단순 띠: 두 링 사이 면 + 바깥으로 약간
            loft_grid(bm, [[p + (p - Vector((x, yfwd, zy - yr - fr))).normalized() * 0.012 for p in rings[0]],
                           [p + (p - Vector((x, yfwd, zy - yr - fr))).normalized() * 0.012 for p in rings[1]]],
                      closed=True)
        ties = mesh_object(f"SailTies{i}", bm, colls["Rigging"], [mats["rope"]], angle=60)
        ties.matrix_world = mo.matrix_world.copy()
        parent_keep(ties, mo)
        masts.append((mo, m, zy, yfwd))

    # 삭구(밧줄): 돛대 끝 → 선수·선미·양현, 활대 매달기(halyard)
    wall_st = d["superstructure"]["wall"]["stations"]
    wy0, wy1 = min(s["y"] for s in wall_st), max(s["y"] for s in wall_st)
    for i, (mo, m, zy, yfwd) in enumerate(masts):
        top = mo.matrix_world @ Vector((0, 0, m["height"] - 0.15))
        yardc = mo.matrix_world @ Vector((0, yfwd, zy + 0.05))
        rope_curve(f"Halyard{i}", [top + Vector((0, 0.1, 0)), yardc], ROPE_R * 0.8, colls["Rigging"], mats["rope"])
        # 활대 양끝 → 갑판 (브레이스)
        for sgn in (-1, 1):
            ye = mo.matrix_world @ Vector((sgn * m["sail"]["w"] * YARD_OVER / 2 * 0.95, yfwd, zy))
            yd = m["y"] - 2.5
            tgt = Vector((sgn * wc["half"](yd), yd, wc["top_z"](yd) + 0.05))
            rope_curve(f"Brace{i}{'P' if sgn < 0 else 'S'}", catenary_points(ye, tgt, (ye - tgt).length * ROPE_SAG),
                       ROPE_R, colls["Rigging"], mats["rope"])
        if m.get("lowered"):
            continue
        # 앞·뒤 버팀줄
        if i == 0:
            tgt = Vector((0, wy1, R.c["ridge_z"](wy1) + 0.05))
        else:
            tgt = masts[0][0].matrix_world @ Vector((0, 0, d["masts"][0]["height"] * 0.75))
        rope_curve(f"Stay{i}F", catenary_points(top, tgt, (top - tgt).length * ROPE_SAG * 0.5), ROPE_R,
                   colls["Rigging"], mats["rope"])
        tgt = Vector((0, m["y"] - 6.0, R.c["ridge_z"](m["y"] - 6.0) + 0.05))
        rope_curve(f"Stay{i}A", catenary_points(top, tgt, (top - tgt).length * ROPE_SAG * 0.5), ROPE_R,
                   colls["Rigging"], mats["rope"])
        for sgn in (-1, 1):
            yy = m["y"] - 0.8
            tgt = Vector((sgn * wc["half"](yy), yy, wc["top_z"](yy) + 0.05))
            rope_curve(f"Shroud{i}{'P' if sgn < 0 else 'S'}",
                       catenary_points(top, tgt, (top - tgt).length * ROPE_SAG * 0.4), ROPE_R,
                       colls["Rigging"], mats["rope"])

    # 깃발
    fl_objs = []
    for k, f in enumerate(d["flags"]):
        w, h = f["size"]
        pole = f.get("pole", "")
        parent = None
        offx = 0.0
        if pole.startswith("mast") and pole.endswith("_top"):
            mi = int(pole[4:-4])
            mo, m, _, _ = masts[mi]
            parent = mo
            offx = m["diameter"] / 2 * MAST_TOP_TAPER
        else:
            bm = bmesh.new()
            zb = f.get("pole_base_z", H.sz(f["pos"][1]))
            add_cyl(bm, (f["pos"][0], f["pos"][1], zb), (f["pos"][0], f["pos"][1], f["pos"][2] + FLAG_POLE_TOP),
                    FLAG_POLE_R, FLAG_POLE_R * 0.7, seg=12)
            r = bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=FLAG_POLE_R * 1.8)
            bmesh.ops.translate(bm, verts=r["verts"], vec=Vector((f["pos"][0], f["pos"][1], f["pos"][2] + FLAG_POLE_TOP)))
            mesh_object(f"FlagPole{k}", bm, colls["Rigging"], [mats["mast_wood"]], angle=50)
            offx = FLAG_POLE_R
        nxs, nzs = (28, 16) if Q["cyl"] > 16 else (18, 10)
        bm = bmesh.new()
        grid = []
        for j in range(nzs + 1):
            v = j / nzs
            row = []
            for i in range(nxs + 1):
                u = i / nxs
                x = offx + u * w
                yo = FLAG_WAVE_AMP * w * u * math.sin(2 * math.pi * (u * w / (FLAG_WAVE_LEN * w)) + 0.7 * v + k)
                z = -v * h - FLAG_DROOP * h * u * u * (0.6 + 0.4 * v)
                row.append(Vector((x, yo, z)))
            grid.append(row)
        vv, _ = loft_grid(bm, grid)
        col = hex_to_linear(f["color"])
        fo = mesh_object(f"Flag{k}", bm, colls["Rigging"], [mats["flag_cloth"]], angle=80)
        ca = fo.data.color_attributes.new("flag_color", "FLOAT_COLOR", "POINT")
        for dd in ca.data:
            dd.color = col
        fo.color = col
        fo.matrix_world = Matrix.Translation(Vector(f["pos"]))
        if parent:
            parent_keep(fo, parent)
        fl_objs.append(fo)
    return masts


# =====================================================================================================
# 키 + 소품
# =====================================================================================================
def build_rudder_props(d, H, Q, colls, mats):
    r = d["rudder"]
    seg = Q["cyl"]
    bot = r["top_z"] - r["depth"]
    bm = bmesh.new()
    add_cyl(bm, (0, r["y"], bot), (0, r["y"], r["top_z"] + RUDDER_STOCK_EXT), r["stock_diameter"] / 2, seg=seg)
    stock = mesh_object("RudderStock", bm, colls["Details"], [mats["mast_wood"]], angle=50)
    bm = bmesh.new()
    bh = r["depth"] * RUDDER_BLADE_FRAC
    bdh = bh / RUDDER_BOARDS
    for k in range(RUDDER_BOARDS):
        zc = bot + bdh * (k + 0.5)
        add_box(bm, (0, r["y"] - r["width"] / 2 - r["stock_diameter"] * 0.3, zc),
                (r["thickness"], r["width"], bdh - 0.015))
    # 날개 보강 띠(세로)
    for t in (0.3, 0.7):
        add_box(bm, (0, r["y"] - r["width"] * t - r["stock_diameter"] * 0.3, bot + bh / 2),
                (r["thickness"] + 0.04, 0.08, bh))
    mesh_object("RudderBlade", bm, colls["Details"], [mats["hull_wood"]], angle=30)
    bm = bmesh.new()
    zt = r["top_z"] + RUDDER_STOCK_EXT * 0.6
    add_cyl(bm, (0, r["y"], zt), (0, r["y"] + RUDDER_TILLER, zt + 0.15), 0.06, 0.045, seg=12)
    mesh_object("RudderTiller", bm, colls["Details"], [mats["mast_wood"]], angle=50)

    # 소품: 선미 갑판 물통 2, 선수 갑판 밧줄 사리, 닻(나무닻+돌)
    rnd = random.Random(SEED + 3)
    bm = bmesh.new()
    wall_st = d["superstructure"]["wall"]["stations"]
    wy0, wy1 = min(s["y"] for s in wall_st), max(s["y"] for s in wall_st)
    yb = (wy0 + H.ymin) / 2
    for k, sgn in enumerate((-1, 1)):
        x = sgn * H.sh(yb) * 0.55
        z = H.sz(yb)
        rings = []
        for j in range(9):
            t = j / 8
            rr = 0.26 * (1 + 0.12 * math.sin(math.pi * t))
            rings.append([Vector((x + rr * math.cos(2 * math.pi * i / 16), yb + rr * math.sin(2 * math.pi * i / 16),
                                  z + 0.62 * t)) for i in range(16)])
        loft_grid(bm, rings, closed=True, cap_start=True, cap_end=True)
    mesh_object("WaterBarrels", bm, colls["Details"], [mats["oar_wood"]], angle=50)
    bm = bmesh.new()
    for k in range(2):
        for sgn in (-1, 1):
            add_cyl(bm, (sgn * H.sh(yb) * 0.55, yb, H.sz(yb) + 0.12 + 0.38 * k),
                    (sgn * H.sh(yb) * 0.55, yb, H.sz(yb) + 0.16 + 0.38 * k), 0.30, seg=16)
    mesh_object("BarrelHoops", bm, colls["Details"], [mats["iron_spike"]], angle=50)
    # 밧줄 사리(선수 갑판)
    yf = (wy1 + H.ymax) / 2
    pts = []
    for k in range(80):
        a = k / 80 * 2 * math.pi * 4
        rr = 0.18 + 0.012 * k / 6
        pts.append(Vector((0.9 + rr * math.cos(a), yf + rr * math.sin(a) * 0.8, H.sz(yf) + 0.03 + 0.02 * (k // 20))))
    rope_curve("RopeCoil", pts, 0.022, colls["Details"], mats["rope"])
    # 닻: 선수 우현 쪽 매달린 나무닻
    bm = bmesh.new()
    ax, ay = H.sh(11.0) + 0.15, 11.0
    az = H.sz(11.0) - 0.4
    add_box(bm, (ax, ay, az - 0.6), (0.12, 0.12, 1.4), Matrix.Rotation(math.radians(8), 3, "Y"))
    add_box(bm, (ax, ay, az - 1.25), (0.1, 0.9, 0.1))
    for sgn in (-1, 1):
        add_box(bm, (ax, ay + sgn * 0.42, az - 1.1), (0.08, 0.08, 0.35), Matrix.Rotation(math.radians(-sgn * 30), 3, "X"))
    mesh_object("Anchor", bm, colls["Details"], [mats["oar_wood"]], angle=30)
    rope_curve("AnchorRope", catenary_points(Vector((ax - 0.05, ay, H.sz(11.0) + 0.1)), Vector((ax, ay, az + 0.1)), 0.02),
               0.02, colls["Details"], mats["rope"])
    del rnd


# =====================================================================================================
# 부두·해안·원경
# =====================================================================================================
def build_site(d, Q, colls, mats):
    site = d["site"]
    rnd = random.Random(SEED)
    p = site.get("pier")
    if p:
        bl, bd, bhh = p["block_size"]
        cap = p["cap_stone"]
        xf = p["x_max"]
        z0, z1 = p["bottom_z"], p["top_z"] - cap["height"]
        nrows = max(1, int(round((z1 - z0) / bhh)))
        rh = (z1 - z0) / nrows
        bm = bmesh.new()

        def jitter_block(center, size, axis_out):
            s = [v * (1 + rnd.uniform(-STONE_JITTER_SIZE, STONE_JITTER_SIZE)) for v in size]
            rot = (Matrix.Rotation(math.radians(rnd.uniform(-1, 1) * STONE_JITTER_ROT_DEG), 3, "X") @
                   Matrix.Rotation(math.radians(rnd.uniform(-1, 1) * STONE_JITTER_ROT_DEG), 3, "Y") @
                   Matrix.Rotation(math.radians(rnd.uniform(-1, 1) * STONE_JITTER_ROT_DEG), 3, "Z"))
            c = Vector(center) + axis_out * rnd.uniform(-STONE_JITTER_OUT, STONE_JITTER_OUT)
            add_box(bm, c, (s[0] - STONE_GAP, s[1] - STONE_GAP, s[2] - STONE_GAP), rot)

        def course_wall(fixed_axis, fixed_val, run_lo, run_hi, out_dir):
            for r_ in range(nrows):
                zc = z0 + rh * (r_ + 0.5)
                off = (bl / 2) if r_ % 2 else 0.0
                t = run_lo - off
                while t < run_hi:
                    a, b = max(t, run_lo), min(t + bl * (1 + rnd.uniform(-0.15, 0.15)), run_hi)
                    if b - a > 0.15:
                        c = (a + b) / 2
                        if fixed_axis == "x":
                            jitter_block((fixed_val - out_dir.x * bd / 2, c, zc), (bd, b - a, rh), out_dir)
                        else:
                            jitter_block((c, fixed_val - out_dir.y * bd / 2, zc), (b - a, bd, rh), out_dir)
                    t = b
        course_wall("x", xf, p["y_min"], p["y_max"], Vector((1, 0, 0)))
        course_wall("y", p["y_max"], p["x_min"], xf, Vector((0, 1, 0)))
        course_wall("y", p["y_min"], p["x_min"], xf, Vector((0, -1, 0)))
        # 갓돌
        cl = bl * CAP_LEN_RATIO
        t = p["y_min"]
        zc = p["top_z"] - cap["height"] / 2
        while t < p["y_max"] - 0.1:
            b = min(t + cl, p["y_max"])
            jitter_block((xf - cap["depth"] / 2 + CAP_OVERHANG, (t + b) / 2, zc), (cap["depth"], b - t, cap["height"]),
                         Vector((0, 0, 1)) * 0.3)
            t = b
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=STONE_BEVEL, segments=1, affect="EDGES", clamp_overlap=True)
        mesh_object("QuayFaceStones", bm, colls["Site"], [mats["stone"]], angle=30)
        # 상판 포장석
        bm = bmesh.new()
        x = p["x_min"]
        rowi = 0
        while x < xf - cap["depth"] - 0.05:
            xb = min(x + bl, xf - cap["depth"])
            off = (bd / 2) * (rowi % 2)
            t = p["y_min"] - off
            while t < p["y_max"]:
                a, b = max(t, p["y_min"]), min(t + bd * 2 * (1 + rnd.uniform(-0.2, 0.2)), p["y_max"])
                if b - a > 0.1:
                    s = 1 + rnd.uniform(-0.02, 0.02)
                    add_box(bm, ((x + xb) / 2, (a + b) / 2, p["top_z"] - 0.06 + rnd.uniform(-0.008, 0.008)),
                            ((xb - x) * s - STONE_GAP, (b - a) - STONE_GAP, 0.12),
                            Matrix.Rotation(math.radians(rnd.uniform(-0.4, 0.4)), 3, "X"))
                t = b
            x = xb
            rowi += 1
        bmesh.ops.bevel(bm, geom=[e for e in bm.edges], offset=0.02, segments=1, affect="EDGES", clamp_overlap=True)
        mesh_object("QuayPaving", bm, colls["Site"], [mats["stone"]], angle=30)
        # 안벽 몸체(속채움)
        bm = bmesh.new()
        add_box(bm, ((p["x_min"] + xf - bd) / 2, (p["y_min"] + p["y_max"]) / 2 - 0.0, (p["bottom_z"] + p["top_z"] - 0.1) / 2),
                (xf - bd - p["x_min"] + 0.05, p["y_max"] - p["y_min"] - 2 * bd + 0.05, p["top_z"] - 0.1 - p["bottom_z"]))
        mesh_object("QuayCore", bm, colls["Site"], [mats["stone"]], smooth=False)
        # 계선주
        bm = bmesh.new()
        for b in p.get("bollards", []):
            zt = p["top_z"]
            add_cyl(bm, (b["x"], b["y"], zt - 0.05), (b["x"], b["y"], zt + BOLLARD_H * 0.8), BOLLARD_R, BOLLARD_R * 0.85, seg=20)
            add_cyl(bm, (b["x"], b["y"], zt + BOLLARD_H * 0.8), (b["x"], b["y"], zt + BOLLARD_H), BOLLARD_R * 1.3, BOLLARD_R * 1.15, seg=20)
        mesh_object("Bollards", bm, colls["Site"], [mats["iron_spike"]], angle=40)
        for k, ml in enumerate(p.get("mooring_lines", [])):
            b = p["bollards"][ml["from_bollard"]]
            a = Vector((b["x"], b["y"], p["top_z"] + BOLLARD_H * 0.65))
            t = Vector(ml["to"])
            rope_curve(f"MooringLine{k}", catenary_points(a, t, (a - t).length * ROPE_SAG * 1.5, 24), MOOR_R,
                       colls["Site"], mats["rope"])
    s = site.get("shore")
    if s:
        bm = bmesh.new()
        nx_, ny_ = 24, 48
        grid = []
        for j in range(ny_ + 1):
            y = s["y_min"] + (s["y_max"] - s["y_min"]) * j / ny_
            row = []
            for i in range(nx_ + 1):
                x = s["x_min"] + (s["x_max"] - s["x_min"]) * i / nx_
                row.append(Vector((x, y, s["z"])))
            grid.append(row)
        loft_grid(bm, grid)
        # 경사 둑 (수면 쪽 가장자리: y 양끝, x_max 쪽에서 부두 밖 구간)
        b = SHORE_BANK
        zb = SHORE_BANK_BOTTOM
        bank = []
        for (x0, y0_), (x1, y1_), out in [((s["x_min"], s["y_max"]), (s["x_max"], s["y_max"]), (0, 1)),
                                          ((s["x_max"], s["y_min"]), (s["x_min"], s["y_min"]), (0, -1))]:
            bank.append(([Vector((x0, y0_, s["z"])), Vector((x1, y1_, s["z"]))],
                         [Vector((x0 + out[0] * b, y0_ + out[1] * b, zb)), Vector((x1 + out[0] * b, y1_ + out[1] * b, zb))]))
        segs = []
        if p:
            segs = [(p["y_max"], s["y_max"]), (s["y_min"], p["y_min"])]
        else:
            segs = [(s["y_min"], s["y_max"])]
        for ya, yb_ in segs:
            bank.append(([Vector((s["x_max"], ya, s["z"])), Vector((s["x_max"], yb_, s["z"]))],
                         [Vector((s["x_max"] + b, ya, zb)), Vector((s["x_max"] + b, yb_, zb))]))
        for top, botm in bank:
            nseg = max(2, int((top[1] - top[0]).length / 2))
            rr = []
            for line in (top, botm):
                rr.append([line[0].lerp(line[1], k / nseg) for k in range(nseg + 1)])
            loft_grid(bm, rr)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        for f in bm.faces:
            if f.normal.z < 0:
                f.normal_flip()
        sh = mesh_object("Shore", bm, colls["Site"], [mats["ground"]], angle=30)
        dm = sh.modifiers.new("Rough", "DISPLACE")
        tex = bpy.data.textures.new("ShoreNoise", "CLOUDS")
        tex.noise_scale = 3.0
        dm.texture = tex
        dm.strength = 0.08
        dm.mid_level = 0.5
        dm.texture_coords = "GLOBAL"
    hills = site.get("background_hills")
    if hills:
        az = math.radians(hills["direction_deg"])
        dist, hh = hills["distance"], hills["height"]
        c = Vector((math.sin(az) * dist, math.cos(az) * dist, 0))
        fwd = Vector((math.sin(az), math.cos(az), 0))
        side = Vector((fwd.y, -fwd.x, 0))
        a, bb = hh * HILL_LEN_RATIO, hh * HILL_WID_RATIO
        nu, nv = Q["hill"]
        hr = random.Random(SEED + 11)
        bumps = [(hr.uniform(-0.7, 0.7), hr.uniform(-0.3, 0.3), hr.uniform(0.25, 0.5), hr.uniform(0.45, 1.0)) for _ in range(6)]
        bumps.append((0.0, 0.0, 0.55, 1.0))
        grid = []
        for j in range(nv + 1):
            v = -1.2 + 2.4 * j / nv
            row = []
            for i in range(nu + 1):
                u = -1.2 + 2.4 * i / nu
                hgt = 0.0
                for bu, bv, br, ba in bumps:
                    hgt = max(hgt, ba * math.exp(-(((u - bu) / br) ** 2 + ((v - bv) / (br * 0.9)) ** 2)))
                hgt *= (1 + 0.08 * math.sin(u * 23 + v * 7) * math.sin(u * 11 - v * 13))
                hgt = hh * hgt - 3.0
                row.append(c + side * (u * a) + fwd * (v * bb) + Vector((0, 0, hgt)))
            grid.append(row)
        bm = bmesh.new()
        loft_grid(bm, grid)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        for f in bm.faces:
            if f.normal.z < 0:
                f.normal_flip()
        mesh_object("BackgroundHills", bm, colls["Site"], [mats["ground"]], angle=60)


def build_water(d, Q, colls, mats):
    site = d["site"]
    wz = site["water_z"]
    ext = site["water_size"] * OCEAN_EXTENT_RATIO
    me = bpy.data.meshes.new("Water")
    ob = bpy.data.objects.new("Water", me)
    colls["Site"].objects.link(ob)
    me.materials.append(mats["water"])
    ob.location = (0, 0, wz)
    m = ob.modifiers.new("Ocean", "OCEAN")
    m.geometry_mode = "GENERATE"
    m.spatial_size = int(round(ext))
    m.size = 1.0
    m.resolution = Q["ocean_res"]
    m.viewport_resolution = min(Q["ocean_res"], 10)
    m.wind_velocity = OCEAN_WIND
    m.wave_scale = OCEAN_WAVE_SCALE
    m.choppiness = OCEAN_CHOP
    m.random_seed = OCEAN_SEED
    m.wave_alignment = 0.3
    m.time = 1.0
    m.use_normals = False
    # 원경 수면: 근경 Ocean 바깥 고리 ~ 수평선
    inner = ext / 2 - 1.0
    bm = bmesh.new()
    outer_r = HORIZON_FAR
    ring_in = [Vector((inner * math.copysign(1, math.cos(a)) * min(1, abs(math.cos(a)) / max(abs(math.sin(a)), 1e-9)),
                       inner * math.copysign(1, math.sin(a)) * min(1, abs(math.sin(a)) / max(abs(math.cos(a)), 1e-9)), wz - 0.01))
               for a in np.linspace(0, 2 * math.pi, 65)[:-1]]
    rings = [ring_in]
    for rr in (ext, ext * 2, ext * 6, ext * 20, outer_r):
        rings.append([Vector((rr * math.cos(a), rr * math.sin(a), wz - 0.01)) for a in np.linspace(0, 2 * math.pi, 65)[:-1]])
    loft_grid(bm, rings, closed=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    far = mesh_object("WaterFar", bm, colls["Site"], [mats["water"]], angle=80)
    return ob, far


# =====================================================================================================
# 카메라
# =====================================================================================================
def build_cameras(d, colls, sc):
    cams = {}
    for v in d["views"]:
        cd = bpy.data.cameras.new("CAM_" + v["id"])
        cd.lens = v["lens_mm"]
        cd.sensor_width = v.get("sensor_mm", 36)
        cd.sensor_fit = "HORIZONTAL"
        cd.clip_start = 0.1
        cd.clip_end = HORIZON_FAR * 1.5
        ob = bpy.data.objects.new("CAM_" + v["id"], cd)
        colls["Cameras"].objects.link(ob)
        c, la = Vector(v["cam"]), Vector(v["look_at"])
        ob.location = c
        ob.rotation_mode = "XYZ"
        ob.rotation_euler = (la - c).to_track_quat("-Z", "Y").to_euler()
        ob["look_at"] = list(la)
        cams[v["id"]] = ob
    sc.camera = cams.get("bow34") or next(iter(cams.values()))
    return cams


# =====================================================================================================
def build(design_path=DEFAULT_DESIGN, quality="preview"):
    t0 = time.time()
    with open(design_path, encoding="utf-8") as f:
        d = json.load(f)
    Q = QUALITY[quality]
    sc, colls = new_scene()
    mats, real = load_materials(d)
    H, hull, deck, wc = build_hull(d, Q, colls, mats)
    build_wall(d, H, wc, Q, colls, mats)
    R, roof, nsp = build_roof(d, Q, colls, mats)
    build_dragon(d, Q, colls, mats)
    build_ghost_face(d, H, Q, colls, mats)
    build_oars(d, wc, Q, colls, mats)
    build_rigging(d, H, wc, R, Q, colls, mats)
    build_rudder_props(d, H, Q, colls, mats)
    build_site(d, Q, colls, mats)
    build_water(d, Q, colls, mats)
    build_cameras(d, colls, sc)
    try:
        import world  # noqa
        world.setup_world(sc, d["sun"]["azimuth_deg"], d["sun"]["elevation_deg"])
        if hasattr(world, "setup_render"):
            world.setup_render(sc, "CYCLES", quality)
    except Exception as ex:  # noqa
        print(f"[build_scene] WARNING: world.setup_world 실패 → 기본 조명 ({ex!r})")
        sd = bpy.data.lights.new("SUN_Key", "SUN")
        so = bpy.data.objects.new("SUN_Key", sd)
        sc.collection.objects.link(so)
        az, el = math.radians(d["sun"]["azimuth_deg"]), math.radians(d["sun"]["elevation_deg"])
        so.rotation_euler = (Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
                             ).to_track_quat("Z", "Y").to_euler()
        sc.render.engine = "CYCLES"
    sc["geobuk_quality"] = quality
    sc["geobuk_real_materials"] = int(real)
    sc["geobuk_spikes"] = nsp
    bpy.context.view_layer.update()
    sc["geobuk_build_sec"] = round(time.time() - t0, 2)
    return sc


def scene_stats(sc):
    dg = bpy.context.evaluated_depsgraph_get()
    tot, per = 0, {}
    for inst in dg.object_instances:
        ob = inst.object
        if ob.type not in ("MESH", "CURVE"):
            continue
        try:
            me = ob.to_mesh()
        except RuntimeError:
            continue
        n = len(me.polygons) if me else 0
        ob.to_mesh_clear()
        tot += n
        root = inst.instance_object.name if inst.is_instance and inst.instance_object else ob.original.name
        per[root] = per.get(root, 0) + n
    return tot, per


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", default=DEFAULT_DESIGN)
    ap.add_argument("--save", default=DEFAULT_SAVE)
    ap.add_argument("--quality", default="preview", choices=list(QUALITY))
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args(sys.argv[1:] if "--" not in sys.argv else sys.argv[sys.argv.index("--") + 1:])
    sc = build(os.path.abspath(a.design), a.quality)
    print(f"[build_scene] built ({a.quality}) in {sc['geobuk_build_sec']} s; spikes={sc['geobuk_spikes']}; "
          f"real_materials={bool(sc['geobuk_real_materials'])}")
    for c in bpy.data.collections:
        print(f"   {c.name:15s} {len(c.objects):4d} objects")
    if a.stats:
        tot, per = scene_stats(sc)
        print(f"[build_scene] evaluated polygons: {tot:,}")
        for k, v in sorted(per.items(), key=lambda kv: -kv[1])[:15]:
            print(f"   {k:22s} {v:,}")
    save = os.path.abspath(a.save)
    os.makedirs(os.path.dirname(save), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=save, compress=True)
    print("[build_scene] saved", save)


if __name__ == "__main__":
    main()
