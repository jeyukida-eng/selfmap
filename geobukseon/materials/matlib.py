"""거북선 프로젝트 — 절차적 재질 라이브러리 (Blender 5.2, Cycles/EEVEE 공용, 이미지 텍스처·UV 미사용).

사용:  import matlib; mats = matlib.build_all(hex_cell=0.9)   # dict[name -> bpy.types.Material]
단독 확인: /opt/bvenv/bin/python materials/matlib.py

좌표 규약
- 패턴 좌표: Object 좌표(m, 오브젝트 스케일 1 가정) 또는 Generated(바운딩박스 0..1).
- 흘수선/물때/먼지: 월드 Position.z (수선 z=0) 및 월드 Normal.
- 소켓은 이름(identifier/name)으로만 찾는다. 없으면 KeyError (인덱스 fallback 없음).
"""
import math
import bpy

MAT_NAMES = [
    "hull_wood", "hull_waterline", "roof_shell", "iron_spike", "dragon_head", "ghost_face",
    "wall_panel", "oar_wood", "mast_wood", "sail_cloth", "rope", "flag_cloth", "water",
    "stone", "ground",
]


# ----------------------------------------------------------------------------------------------
# 노드 그래프 헬퍼
# ----------------------------------------------------------------------------------------------
def _sock(sockets, key):
    for s in sockets:
        if s.identifier == key and s.enabled:
            return s
    c = [s for s in sockets if s.name == key and s.enabled]
    if len(c) != 1:
        raise KeyError(f"socket '{key}' not found/ambiguous: {[s.identifier for s in sockets if s.enabled]}")
    return c[0]


class G:
    """작은 노드 DSL. 값 인자는 float/tuple 또는 NodeSocket."""

    def __init__(self, mat):
        self.mat = mat
        self.nt = mat.node_tree
        self.nt.nodes.clear()
        self.n = 0

    # 기본 -----------------------------------------------------------------
    def node(self, typ, inputs=None, **props):
        nd = self.nt.nodes.new(typ)
        self.n += 1
        nd.location = ((self.n % 12) * 220 - 2600, -(self.n // 12) * 260)
        for k, v in props.items():
            setattr(nd, k, v)
        for k, v in (inputs or {}).items():
            self.set(_sock(nd.inputs, k), v)
        return nd

    def set(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.nt.links.new(v, sock)
            return
        if sock.type == "RGBA" and isinstance(v, (tuple, list)) and len(v) == 3:
            v = (*v, 1.0)
        if sock.type in ("VECTOR",) and isinstance(v, (int, float)):
            v = (v, v, v)
        if sock.type == "RGBA" and isinstance(v, (int, float)):
            v = (v, v, v, 1.0)
        sock.default_value = v

    @staticmethod
    def o(nd, name):
        return _sock(nd.outputs, name)

    # 좌표 ------------------------------------------------------------------
    def texco(self):
        if not hasattr(self, "_tc"):
            self._tc = self.node("ShaderNodeTexCoord")
        return self._tc

    def obj(self):
        return self.o(self.texco(), "Object")

    def gen(self):
        return self.o(self.texco(), "Generated")

    def geo(self):
        if not hasattr(self, "_geo"):
            self._geo = self.node("ShaderNodeNewGeometry")
        return self._geo

    def wpos(self):
        return self.o(self.geo(), "Position")

    def wnorm(self):
        return self.o(self.geo(), "Normal")

    # 수학 ------------------------------------------------------------------
    def m(self, op, a, b=0.0, c=0.0, clamp=False):
        nd = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        ins = [s for s in nd.inputs if s.enabled]
        for s, v in zip(ins, (a, b, c)):
            self.set(s, v)
        return self.o(nd, "Value")

    def v(self, op, a, b=(0, 0, 0), scale=1.0):
        nd = self.node("ShaderNodeVectorMath", operation=op)
        ins = [s for s in nd.inputs if s.enabled]
        for s, val in zip(ins, (a, b)):
            if s.type == "VALUE":
                self.set(s, scale)
            else:
                self.set(s, val)
        if op == "SCALE":
            self.set(_sock(nd.inputs, "Scale"), scale)
        return self.o(nd, "Value" if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else "Vector")

    def sep(self, vec):
        nd = self.node("ShaderNodeSeparateXYZ", {"Vector": vec})
        return self.o(nd, "X"), self.o(nd, "Y"), self.o(nd, "Z")

    def comb(self, x, y, z):
        nd = self.node("ShaderNodeCombineXYZ", {"X": x, "Y": y, "Z": z})
        return self.o(nd, "Vector")

    def smooth(self, val, lo, hi, a=0.0, b=1.0):
        nd = self.node("ShaderNodeMapRange", {"Value": val, "From Min": lo, "From Max": hi,
                                              "To Min": a, "To Max": b},
                       interpolation_type="SMOOTHSTEP", clamp=True)
        return self.o(nd, "Result")

    def lin(self, val, lo, hi, a=0.0, b=1.0, clamp=True):
        nd = self.node("ShaderNodeMapRange", {"Value": val, "From Min": lo, "From Max": hi,
                                              "To Min": a, "To Max": b},
                       interpolation_type="LINEAR", clamp=clamp)
        return self.o(nd, "Result")

    def mix(self, fac, a, b, blend="MIX", clamp=True):
        nd = self.node("ShaderNodeMix", data_type="RGBA", blend_type=blend, clamp_result=clamp)
        self.set(_sock(nd.inputs, "Factor"), fac)
        self.set(_sock(nd.inputs, "A"), a)
        self.set(_sock(nd.inputs, "B"), b)
        return self.o(nd, "Result")

    def mixf(self, fac, a, b):
        nd = self.node("ShaderNodeMix", data_type="FLOAT", clamp_factor=True)
        self.set(_sock(nd.inputs, "Factor"), fac)
        self.set(_sock(nd.inputs, "A"), a)
        self.set(_sock(nd.inputs, "B"), b)
        return self.o(nd, "Result")

    def ramp(self, fac, stops, interp="LINEAR"):
        nd = self.node("ShaderNodeValToRGB", {"Fac": fac})
        cr = nd.color_ramp
        cr.interpolation = interp
        while len(cr.elements) > 1:
            cr.elements.remove(cr.elements[-1])
        cr.elements[0].position = stops[0][0]
        cr.elements[0].color = (*stops[0][1], 1.0) if len(stops[0][1]) == 3 else stops[0][1]
        for pos, col in stops[1:]:
            e = cr.elements.new(pos)
            e.color = (*col, 1.0) if len(col) == 3 else col
        return self.o(nd, "Color")

    def bw(self, col):
        return self.o(self.node("ShaderNodeRGBToBW", {"Color": col}), "Val")

    def hsv(self, col, h=0.5, s=1.0, v=1.0, fac=1.0):
        nd = self.node("ShaderNodeHueSaturation", {"Hue": h, "Saturation": s, "Value": v,
                                                   "Factor": fac, "Color": col})
        return self.o(nd, "Color")

    # 텍스처 ----------------------------------------------------------------
    def noise(self, vec, scale=1.0, detail=4.0, rough=0.55, dist=0.0, lac=2.0, dims="3D",
              ntype="FBM", w=0.0, normalize=True):
        ins = {"Vector": vec, "Scale": scale, "Detail": detail, "Roughness": rough,
               "Distortion": dist, "Lacunarity": lac}
        if dims in ("1D", "4D"):
            ins["W"] = w
        if dims == "1D":
            ins.pop("Vector")
        return self.node("ShaderNodeTexNoise", ins, noise_dimensions=dims, noise_type=ntype,
                         normalize=normalize)

    def nfac(self, *a, **k):
        return self.o(self.noise(*a, **k), "Fac")

    def white(self, vec, dims="3D"):
        nd = self.node("ShaderNodeTexWhiteNoise", {"Vector": vec} if dims != "1D" else {"W": vec},
                       noise_dimensions=dims)
        return nd

    def voronoi(self, vec, scale=1.0, feature="F1", metric="EUCLIDEAN", rand=1.0, dims="3D",
                detail=0.0):
        return self.node("ShaderNodeTexVoronoi", {"Vector": vec, "Scale": scale, "Randomness": rand,
                                                  "Detail": detail},
                         feature=feature, distance=metric, voronoi_dimensions=dims)

    def wave(self, vec, scale=1.0, dist=0.0, detail=2.0, dscale=1.0, droug=0.5, wtype="BANDS",
             direction="X", profile="SIN", phase=0.0):
        nd = self.node("ShaderNodeTexWave", {"Vector": vec, "Scale": scale, "Distortion": dist,
                                             "Detail": detail, "Detail Scale": dscale,
                                             "Detail Roughness": droug, "Phase Offset": phase},
                       wave_type=wtype, wave_profile=profile)
        if wtype == "BANDS":
            nd.bands_direction = direction
        else:
            nd.rings_direction = direction
        return self.o(nd, "Fac")

    def ao(self, dist=0.4, samples=8):
        nd = self.node("ShaderNodeAmbientOcclusion", {"Distance": dist}, samples=samples)
        return self.o(nd, "AO")

    # 출력 ------------------------------------------------------------------
    def bump(self, height, strength=0.3, distance=0.01, normal=None):
        ins = {"Height": height, "Strength": strength, "Distance": distance}
        if normal is not None:
            ins["Normal"] = normal
        return self.o(self.node("ShaderNodeBump", ins), "Normal")

    def principled(self, **ins):
        nd = self.node("ShaderNodeBsdfPrincipled")
        for k, v in ins.items():
            self.set(_sock(nd.inputs, k.replace("_", " ")), v)
        return nd

    def output(self, shader_sock, volume=None, disp=None):
        out = self.node("ShaderNodeOutputMaterial", target="ALL")
        self.nt.links.new(shader_sock, _sock(out.inputs, "Surface"))
        if volume is not None:
            self.nt.links.new(volume, _sock(out.inputs, "Volume"))
        return out


def _new_mat(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    if m.node_tree is None:
        m.use_nodes = True
    return m


# ----------------------------------------------------------------------------------------------
# 공용 서브그래프
# ----------------------------------------------------------------------------------------------
def _wood(g, P, dark, light, plank_w=0.30, seg=6.0, grain_axis="Y", grey=0.35, seed=0.0,
          seam_dark=0.6, seam_w=0.010):
    """판재 나뭇결. grain_axis = 결 방향(판재 장축). 판재는 grain_axis 와 수직한 축으로 쌓인다.
    반환: (color, rough_var 0..1, height)"""
    x, y, z = g.sep(P)
    if grain_axis == "Y":      # 선체 외판: 결 = Y, 판 = Z 로 적층
        along, across, third = y, z, x
    elif grain_axis == "Z":    # 돛대/노: 결 = 로컬 Z
        along, across, third = z, x, y
    else:                      # "X"
        along, across, third = x, z, y
    # 판재 행/구간 인덱스
    a_s = g.m("DIVIDE", across, plank_w)
    row = g.m("FLOOR", a_s)
    row_r = g.o(g.white(g.m("ADD", row, seed), dims="1D"), "Value")
    al = g.m("DIVIDE", g.m("MULTIPLY_ADD", row_r, seg, along), seg)
    segi = g.m("FLOOR", al)
    pid = g.comb(row, segi, seed)
    prnd = g.white(pid)
    pr = g.o(prnd, "Value")
    pcol = g.o(prnd, "Color")
    # 이음선 거리(m)
    fa = g.m("FRACT", a_s)
    da = g.m("MULTIPLY", g.m("MINIMUM", fa, g.m("SUBTRACT", 1.0, fa)), plank_w)
    fl = g.m("FRACT", al)
    dl = g.m("MULTIPLY", g.m("MINIMUM", fl, g.m("SUBTRACT", 1.0, fl)), seg)
    seam_d = g.m("MINIMUM", da, dl)
    seam = g.smooth(seam_d, 0.0, seam_w, 1.0, 0.0)
    # 결: 판재마다 오프셋 → 좌표 늘이기
    off = g.v("SCALE", pcol, scale=37.0)
    gv = g.v("ADD", g.comb(g.m("MULTIPLY", along, 0.06), across, third), off)
    wavevec = g.v("ADD", gv, g.v("SCALE", g.o(g.noise(gv, 2.0, 3.0, 0.5), "Color"), scale=0.35))
    if grain_axis == "Y":
        bands = g.wave(wavevec, 9.0, 4.0, 3.0, 1.5, 0.6, direction="Z")
    elif grain_axis == "Z":
        bands = g.wave(wavevec, 9.0, 4.0, 3.0, 1.5, 0.6, direction="Y")
    else:
        bands = g.wave(wavevec, 9.0, 4.0, 3.0, 1.5, 0.6, direction="Y")
    fine = g.nfac(g.comb(g.m("MULTIPLY", along, 0.08), across, third), 60.0, 6.0, 0.6)
    grain = g.m("ADD", g.m("MULTIPLY", g.smooth(bands, 0.15, 0.95), 0.6), g.m("MULTIPLY", fine, 0.4))
    # 색: 판재별 톤 + 결 + 대형 얼룩
    big = g.nfac(P, 0.35, 4.0, 0.6)
    tone = g.m("ADD", g.m("MULTIPLY", pr, 0.55), g.m("MULTIPLY", big, 0.45))
    base = g.mix(tone, dark, light)
    grain_dark = g.mix(0.45, base, g.mix(1.0, base, (0.55, 0.50, 0.45), "MULTIPLY"))
    col = g.mix(g.smooth(grain, 0.35, 0.8), base, grain_dark)
    # 회색 풍화 (얼룩 마스크)
    wmask = g.m("MULTIPLY", g.smooth(g.nfac(P, 0.8, 5.0, 0.65, dist=0.4), 0.35, 0.7), grey)
    weath = g.mix(0.6, col, g.mix(0.0, (0.20, 0.18, 0.16), (0.20, 0.18, 0.16)))
    col = g.mix(wmask, col, weath)
    # 이음선 어둡게
    col = g.mix(g.m("MULTIPLY", seam, seam_dark), col, (0.015, 0.012, 0.01))
    height = g.m("SUBTRACT", g.m("MULTIPLY", grain, 0.25), g.m("MULTIPLY", seam, 1.0))
    rvar = g.m("ADD", g.m("MULTIPLY", grain, 0.5), g.m("MULTIPLY", wmask, 0.5))
    return col, rvar, height


def _ao_dirt(g, col, dirt=(0.03, 0.025, 0.02), amount=0.6, dist=0.35):
    ao = g.ao(dist)
    f = g.m("MULTIPLY", g.smooth(ao, 0.95, 0.35), amount)
    return g.mix(f, col, g.mix(1.0, col, dirt, "MULTIPLY"))


def _waterline(g, col, rough, strength=1.0, band_top=0.45, algae=True):
    """월드 z 기반 물때: 수면 아래 어둡고 녹조, 수선 위 띠는 젖은 얼룩 + 흘러내린 줄무늬."""
    P = g.wpos()
    x, y, z = g.sep(P)
    edge_n = g.m("MULTIPLY", g.nfac(P, 2.5, 4.0, 0.6), 0.25)
    zz = g.m("SUBTRACT", z, edge_n)
    under = g.smooth(zz, 0.10, -0.15)                       # 1 = 수면 아래
    band = g.smooth(zz, band_top, 0.0)                      # 수선 위 젖은 띠
    streak = g.nfac(g.comb(g.m("MULTIPLY", x, 1.0), g.m("MULTIPLY", y, 1.0), g.m("MULTIPLY", z, 0.04)),
                    7.0, 3.0, 0.5)
    streak = g.m("MULTIPLY", g.smooth(streak, 0.5, 0.75), g.smooth(z, 2.2, 0.0))
    wet = g.m("MAXIMUM", band, g.m("MULTIPLY", streak, 0.55))
    wet = g.m("MULTIPLY", wet, strength)
    col = g.mix(g.m("MULTIPLY", wet, 0.7), col, g.mix(1.0, col, (0.35, 0.33, 0.28), "MULTIPLY"))
    if algae:
        an = g.nfac(P, 4.0, 5.0, 0.7, dist=0.3)
        algae_c = g.mix(an, (0.018, 0.028, 0.010), (0.045, 0.055, 0.020))
        amask = g.m("MULTIPLY", g.m("MAXIMUM", under, g.m("MULTIPLY", band, g.smooth(an, 0.45, 0.7))), strength)
        col = g.mix(amask, col, algae_c)
    else:
        amask = under
    rough = g.mixf(g.m("MAXIMUM", g.m("MULTIPLY", wet, 0.8), g.m("MULTIPLY", under, strength)), rough, 0.35)
    return col, rough, under


def _box_pattern(g, builder):
    """간이 박스 투영: builder(vec2d_as3d) -> (color, height) 를 세 평면에서 계산해 법선으로 블렌드."""
    P = g.obj()
    x, y, z = g.sep(P)
    N = g.v("ABSOLUTE", g.wnorm())
    nx, ny, nz = g.sep(N)
    p = 6.0
    wx, wy, wz = (g.m("POWER", nx, p), g.m("POWER", ny, p), g.m("POWER", nz, p))
    s = g.m("ADD", g.m("ADD", wx, wy), wz)
    wx, wy, wz = (g.m("DIVIDE", wx, s), g.m("DIVIDE", wy, s), g.m("DIVIDE", wz, s))
    cx, hx = builder(g.comb(y, z, 11.0))
    cy, hy = builder(g.comb(x, z, 23.0))
    cz, hz = builder(g.comb(x, y, 37.0))
    col = g.mix(wy, cx, cy)
    col = g.mix(g.m("DIVIDE", wz, g.m("ADD", g.m("ADD", wx, wy), wz)), col, cz)
    h = g.m("ADD", g.m("ADD", g.m("MULTIPLY", hx, wx), g.m("MULTIPLY", hy, wy)), g.m("MULTIPLY", hz, wz))
    return col, h


# ----------------------------------------------------------------------------------------------
# 재질
# ----------------------------------------------------------------------------------------------
def mat_hull_wood(name="hull_wood"):
    mat = _new_mat(name)
    g = G(mat)
    P = g.obj()
    col, rv, h = _wood(g, P, (0.050, 0.032, 0.020), (0.120, 0.085, 0.055), plank_w=0.32, seg=7.5,
                       grain_axis="Y", grey=0.55, seed=1.0)
    col = _ao_dirt(g, col)
    rough = g.lin(rv, 0.0, 1.0, 0.62, 0.88)
    col, rough, _ = _waterline(g, col, rough, strength=0.9)
    nrm = g.bump(h, 0.25, 0.012)
    b = g.principled(Base_Color=col, Roughness=rough, Normal=nrm, Specular_IOR_Level=0.35)
    g.output(g.o(b, "BSDF"))
    return mat


def mat_hull_waterline(name="hull_waterline"):
    mat = _new_mat(name)
    g = G(mat)
    P = g.obj()
    col, rv, h = _wood(g, P, (0.035, 0.026, 0.017), (0.080, 0.060, 0.040), plank_w=0.32, seg=7.5,
                       grain_axis="Y", grey=0.3, seed=1.0)
    col = _ao_dirt(g, col, amount=0.8)
    rough = g.lin(rv, 0.0, 1.0, 0.5, 0.8)
    col, rough, under = _waterline(g, col, rough, strength=1.0, band_top=0.8)
    # 따개비/흰 염분 반점 (수선 부근)
    W = g.wpos()
    _, _, wz = g.sep(W)
    vor = g.voronoi(W, 28.0, "F1")
    spots = g.smooth(g.o(vor, "Distance"), 0.18, 0.08)
    spots = g.m("MULTIPLY", spots, g.m("MULTIPLY", g.smooth(wz, 0.25, 0.05), g.smooth(wz, -0.6, -0.1)))
    spots = g.m("MULTIPLY", spots, g.smooth(g.nfac(W, 3.0, 2.0), 0.45, 0.65))
    col = g.mix(spots, col, (0.30, 0.29, 0.25))
    salt = g.m("MULTIPLY", g.smooth(wz, 0.9, 0.35), g.smooth(wz, 0.15, 0.3))
    salt = g.m("MULTIPLY", salt, g.smooth(g.nfac(W, 6.0, 4.0, 0.6), 0.5, 0.8))
    col = g.mix(g.m("MULTIPLY", salt, 0.5), col, (0.22, 0.21, 0.19))
    slime = g.m("MULTIPLY", g.nfac(W, 9.0, 3.0), 0.3)
    h = g.m("ADD", h, g.m("ADD", g.m("MULTIPLY", spots, 1.5), slime))
    nrm = g.bump(h, 0.3, 0.012)
    b = g.principled(Base_Color=col, Roughness=rough, Normal=nrm, Specular_IOR_Level=0.45)
    g.output(g.o(b, "BSDF"))
    return mat


def _hex(g, u, v, cell):
    """진짜 육각 격자 (flat-to-flat = cell[m]). 반환 (edge_dist_m, cell_id_vec)."""
    pu = g.m("DIVIDE", u, cell)
    pv = g.m("DIVIDE", v, cell)
    S3 = math.sqrt(3.0)

    def fmod(a, b):
        return g.m("FLOORED_MODULO", a, b)
    # 격자 A: 주기 (1, √3), 격자 B: 반주기 오프셋
    ax = g.m("SUBTRACT", fmod(pu, 1.0), 0.5)
    ay = g.m("SUBTRACT", fmod(pv, S3), S3 / 2)
    bx = g.m("SUBTRACT", fmod(g.m("SUBTRACT", pu, 0.5), 1.0), 0.5)
    by = g.m("SUBTRACT", fmod(g.m("SUBTRACT", pv, S3 / 2), S3), S3 / 2)
    da = g.m("ADD", g.m("MULTIPLY", ax, ax), g.m("MULTIPLY", ay, ay))
    db = g.m("ADD", g.m("MULTIPLY", bx, bx), g.m("MULTIPLY", by, by))
    useb = g.m("GREATER_THAN", da, db)
    gx = g.mixf(useb, ax, bx)
    gy = g.mixf(useb, ay, by)
    # 육각 거리 (꼭짓점이 v축 위: pointy-top) : max(|x|, |x|/2 + |y|√3/2) → 가장자리 0.5
    axb, ayb = g.m("ABSOLUTE", gx), g.m("ABSOLUTE", gy)
    hd = g.m("MAXIMUM", axb, g.m("ADD", g.m("MULTIPLY", axb, 0.5), g.m("MULTIPLY", ayb, S3 / 2)))
    edge = g.m("MULTIPLY", g.m("SUBTRACT", 0.5, hd), cell)
    cid = g.comb(g.m("ROUND", g.m("MULTIPLY", g.m("SUBTRACT", pu, gx), 2.0)),
                 g.m("ROUND", g.m("MULTIPLY", g.m("SUBTRACT", pv, gy), 2.0)), 3.0)
    return edge, cid


def mat_roof_shell(name="roof_shell", hex_cell=0.9, line_w=0.075, arc_attr="roof_s"):
    """거북등 지붕: 판 길이방향=Object Y, 가로방향 = attribute `arc_attr`(용마루로부터의 호길이 m,
    좌현 음수) 가 있으면 그것, 없으면 Object X (위에서 투영)."""
    mat = _new_mat(name)
    g = G(mat)
    P = g.obj()
    x, y, z = g.sep(P)
    at = g.node("ShaderNodeAttribute", attribute_name=arc_attr, attribute_type="GEOMETRY")
    s_attr = g.o(at, "Factor")
    has = g.m("GREATER_THAN", g.m("ABSOLUTE", s_attr), 1e-4)
    s = g.mixf(has, x, s_attr)
    edge, cid = _hex(g, s, y, hex_cell)
    crnd = g.white(cid)
    cr = g.o(crnd, "Value")
    line = g.smooth(edge, line_w * 0.5 + 0.004, line_w * 0.5 - 0.004)       # 1 = 굵은 선
    rim = g.m("MULTIPLY", g.smooth(edge, line_w * 0.5 + 0.06, line_w * 0.5 + 0.01), g.m("SUBTRACT", 1.0, line))
    # 판 바탕: 적갈 ~ 흑갈 (셀별), 대형 얼룩
    big = g.nfac(P, 0.25, 3.0, 0.6)
    tone = g.m("ADD", g.m("MULTIPLY", cr, 0.6), g.m("MULTIPLY", big, 0.4))
    plate = g.ramp(tone, [(0.0, (0.022, 0.016, 0.013)), (0.35, (0.055, 0.020, 0.012)),
                          (0.7, (0.110, 0.032, 0.018)), (1.0, (0.150, 0.050, 0.028))])
    # 판 내부 나무결(도장 아래로 비침)
    gr = g.wave(g.comb(g.m("MULTIPLY", s, 1.0), g.m("MULTIPLY", y, 0.08), z), 30.0, 6.0, 3.0, 1.0,
                direction="X")
    plate = g.mix(g.m("MULTIPLY", g.smooth(gr, 0.3, 0.9), 0.25), plate,
                  g.mix(1.0, plate, (0.6, 0.6, 0.6), "MULTIPLY"))
    linec = (0.012, 0.010, 0.009)
    col = g.mix(line, plate, linec)
    col = g.mix(g.m("MULTIPLY", rim, 0.35), col, g.mix(1.0, col, (0.6, 0.55, 0.5), "MULTIPLY"))
    # 도장 벗겨짐 → 회갈 목재
    chip_n = g.nfac(P, 3.0, 6.0, 0.7, dist=0.2)
    chips = g.smooth(chip_n, 0.66, 0.70)
    col = g.mix(chips, col, (0.13, 0.11, 0.09))
    # 먼지·염분 (위를 향한 면) + 빗물 줄
    _, _, nz = g.sep(g.wnorm())
    dust = g.m("MULTIPLY", g.smooth(nz, 0.3, 0.95), g.smooth(g.nfac(P, 1.5, 5.0, 0.6), 0.4, 0.75))
    col = g.mix(g.m("MULTIPLY", dust, 0.35), col, (0.16, 0.14, 0.12))
    col = _ao_dirt(g, col, amount=0.7, dist=0.25)
    rough = g.m("ADD", g.lin(cr, 0.0, 1.0, 0.55, 0.75), g.m("MULTIPLY", g.m("ADD", dust, chips), 0.2))
    rough = g.mixf(line, rough, 0.8)
    h = g.m("SUBTRACT", g.m("MULTIPLY", g.smooth(edge, 0.0, 0.18), 1.0), g.m("MULTIPLY", line, 0.5))
    h = g.m("ADD", h, g.m("MULTIPLY", chips, -0.15))
    h = g.m("ADD", h, g.m("MULTIPLY", g.nfac(P, 25.0, 3.0), 0.08))
    nrm = g.bump(h, 0.35, 0.02)
    b = g.principled(Base_Color=col, Roughness=rough, Normal=nrm, Specular_IOR_Level=0.45)
    g.output(g.o(b, "BSDF"))
    return mat


def mat_iron_spike(name="iron_spike"):
    mat = _new_mat(name)
    g = G(mat)
    P = g.obj()
    n1 = g.nfac(P, 18.0, 6.0, 0.65, dist=0.3)
    n2 = g.nfac(P, 70.0, 4.0, 0.6)
    W = g.wpos()
    rust = g.smooth(g.m("ADD", n1, g.m("MULTIPLY", n2, 0.25)), 0.48, 0.62)
    rust_c = g.ramp(n2, [(0.0, (0.06, 0.022, 0.010)), (0.5, (0.17, 0.060, 0.022)), (1.0, (0.28, 0.11, 0.04))])
    iron_c = g.mix(n2, (0.035, 0.034, 0.033), (0.08, 0.075, 0.07))
    col = g.mix(rust, iron_c, rust_c)
    col = _ao_dirt(g, col, amount=0.5, dist=0.08)
    metal = g.lin(rust, 0.0, 1.0, 0.85, 0.0)
    rough = g.lin(rust, 0.0, 1.0, 0.42, 0.92)
    rough = g.m("ADD", rough, g.m("MULTIPLY", n2, 0.12))
    h = g.m("ADD", g.m("MULTIPLY", rust, 0.6), g.m("MULTIPLY", n2, 0.4))
    nrm = g.bump(h, 0.35, 0.002)
    b = g.principled(Base_Color=col, Metallic=metal, Roughness=rough, Normal=nrm)
    g.output(g.o(b, "BSDF"))
    return mat


def _fade(g, col, P, amount=0.35):
    """채색 바램: 채도/명도 감소 + 얼룩."""
    n = g.nfac(P, 2.0, 5.0, 0.6)
    faded = g.hsv(col, 0.5, 0.6, 1.15)
    faded = g.mix(0.25, faded, (0.28, 0.26, 0.22))
    return g.mix(g.m("MULTIPLY", g.lin(n, 0.3, 0.8, 0.5, 1.0), amount), col, faded)


def mat_dragon_head(name="dragon_head"):
    """용두 단청: Generated Y(뒤→주둥이) 따라 녹·적·청·백·황 띠 + 비늘(Voronoi) + 바램.
    단청 색 기준(선형): 뇌록, 석간주(적), 군청, 백토, 황토."""
    mat = _new_mat(name)
    g = G(mat)
    P = g.obj()
    Gc = g.gen()
    gx, gy, gz = g.sep(Gc)
    dn = g.nfac(P, 3.0, 3.0, 0.5)
    t = g.m("ADD", gy, g.m("MULTIPLY", g.m("SUBTRACT", dn, 0.5), 0.05))
    t = g.m("ADD", t, g.m("MULTIPLY", g.m("SUBTRACT", gz, 0.5), 0.15))
    bands = g.m("FRACT", g.m("MULTIPLY", t, 6.0))
    green = (0.045, 0.20, 0.13)
    red = (0.36, 0.045, 0.030)
    blue = (0.025, 0.07, 0.24)
    white = (0.62, 0.60, 0.54)
    yellow = (0.50, 0.32, 0.08)
    stripe = g.ramp(bands, [(0.0, green), (0.42, white), (0.47, red), (0.70, white), (0.74, blue),
                            (0.90, yellow), (0.95, green)], interp="CONSTANT")
    # 아래턱/목 아랫면은 적색, 윗면은 녹색 비중
    lower = g.smooth(gz, 0.38, 0.30)
    col = g.mix(g.m("MULTIPLY", lower, 0.8), stripe, red)
    # 비늘
    vor = g.voronoi(P, 14.0, "DISTANCE_TO_EDGE")
    scale_line = g.smooth(g.o(vor, "Distance"), 0.06, 0.0)
    col = g.mix(g.m("MULTIPLY", scale_line, 0.6), col, (0.03, 0.03, 0.025))
    col = _fade(g, col, P, 0.5)
    chips = g.smooth(g.nfac(P, 5.0, 6.0, 0.7), 0.66, 0.70)
    col = g.mix(chips, col, (0.12, 0.10, 0.08))
    col = _ao_dirt(g, col, amount=0.85, dist=0.2)
    rough = g.m("ADD", 0.62, g.m("MULTIPLY", chips, 0.2))
    h = g.m("ADD", g.m("MULTIPLY", scale_line, -0.5), g.m("MULTIPLY", g.nfac(P, 40.0, 3.0), 0.2))
    nrm = g.bump(h, 0.3, 0.004)
    b = g.principled(Base_Color=col, Roughness=rough, Normal=nrm, Specular_IOR_Level=0.4)
    g.output(g.o(b, "BSDF"))
    return mat


def mat_ghost_face(name="ghost_face"):
    """귀면: Generated(x=가로 0..1, z=세로 0..1) 기준. 얼굴 평면 = 로컬 XZ(법선 ±Y) 가정.
    붉은 바탕 + 흰 눈자위 + 검은 눈동자 + 녹색 눈썹 + 흰 이빨/송곳니."""
    mat = _new_mat(name)
    g = G(mat)
    P = g.obj()
    gx, gy, gz = g.sep(g.gen())
    dx = g.m("ABSOLUTE", g.m("SUBTRACT", gx, 0.5))  # 좌우 대칭
    red = (0.33, 0.035, 0.025)
    col = g.mix(g.m("MULTIPLY", g.nfac(P, 4.0, 4.0), 0.5), red, (0.20, 0.025, 0.02))
    # 눈
    ed = g.v("LENGTH", g.comb(g.m("SUBTRACT", dx, 0.2), g.m("MULTIPLY", g.m("SUBTRACT", gz, 0.64), 1.3), 0.0))
    sclera = g.smooth(ed, 0.135, 0.125)
    pupil = g.smooth(ed, 0.065, 0.055)
    ring = g.m("MULTIPLY", g.smooth(ed, 0.16, 0.15), g.m("SUBTRACT", 1.0, sclera))
    col = g.mix(ring, col, (0.02, 0.02, 0.02))
    col = g.mix(sclera, col, (0.62, 0.60, 0.52))
    col = g.mix(pupil, col, (0.008, 0.008, 0.008))
    # 눈썹 (녹색 사선 띠)
    bz = g.m("SUBTRACT", gz, g.m("ADD", 0.80, g.m("MULTIPLY", dx, 0.25)))
    brow = g.m("MULTIPLY", g.smooth(g.m("ABSOLUTE", bz), 0.045, 0.035), g.smooth(dx, 0.38, 0.36))
    brow = g.m("MULTIPLY", brow, g.smooth(dx, 0.04, 0.06))
    col = g.mix(brow, col, (0.04, 0.17, 0.10))
    # 코 (어두운 콧구멍)
    nd = g.v("LENGTH", g.comb(g.m("SUBTRACT", dx, 0.07), g.m("MULTIPLY", g.m("SUBTRACT", gz, 0.46), 1.6), 0.0))
    col = g.mix(g.smooth(nd, 0.045, 0.035), col, (0.03, 0.006, 0.005))
    # 입 + 이빨
    mouth = g.m("MULTIPLY", g.smooth(g.m("ABSOLUTE", g.m("SUBTRACT", gz, 0.27)), 0.11, 0.10), g.smooth(dx, 0.33, 0.31))
    col = g.mix(mouth, col, (0.05, 0.008, 0.006))
    tf = g.m("FRACT", g.m("MULTIPLY", gx, 11.0))
    tooth = g.m("MULTIPLY", g.smooth(g.m("ABSOLUTE", g.m("SUBTRACT", tf, 0.5)), 0.42, 0.36),
                g.m("MULTIPLY", g.smooth(g.m("ABSOLUTE", g.m("SUBTRACT", gz, 0.27)), 0.085, 0.075), g.smooth(dx, 0.30, 0.28)))
    # 송곳니(위로 삼각)
    fx = g.m("ABSOLUTE", g.m("SUBTRACT", dx, 0.24))
    fang = g.m("MULTIPLY", g.smooth(fx, g.m("MULTIPLY", g.m("SUBTRACT", 0.47, gz), 0.25), 0.0),
               g.m("MULTIPLY", g.smooth(gz, 0.47, 0.45), g.smooth(gz, 0.18, 0.2)))
    teeth = g.m("MAXIMUM", tooth, g.smooth(fang, 0.2, 0.5))
    col = g.mix(teeth, col, (0.66, 0.63, 0.55))
    col = _fade(g, col, P, 0.45)
    chips = g.smooth(g.nfac(P, 6.0, 6.0, 0.7), 0.67, 0.71)
    col = g.mix(chips, col, (0.11, 0.09, 0.07))
    col = _ao_dirt(g, col, amount=0.8, dist=0.15)
    h = g.m("ADD", g.m("MULTIPLY", g.m("ADD", sclera, teeth), 0.6), g.m("MULTIPLY", g.nfac(P, 35.0, 3.0), 0.2))
    h = g.m("SUBTRACT", h, g.m("ADD", pupil, g.m("MULTIPLY", mouth, 0.5)))
    nrm = g.bump(h, 0.25, 0.006)
    b = g.principled(Base_Color=col, Roughness=g.m("ADD", 0.6, g.m("MULTIPLY", chips, 0.25)), Normal=nrm)
    g.output(g.o(b, "BSDF"))
    return mat


def mat_wall_panel(name="wall_panel"):
    """방패판: 세로 판재(폭 0.28m, 결=Z) 검붉은 도장 + Generated Z 상단 흰 띠/청 띠, 하단 청 띠 흔적."""
    mat = _new_mat(name)
    g = G(mat)
    P = g.obj()
    x, y, z = g.sep(P)
    Pr = g.comb(g.m("ADD", x, y), z, g.m("SUBTRACT", x, y))
    col, rv, h = _wood(g, Pr, (0.08, 0.03, 0.02), (0.15, 0.07, 0.045), plank_w=0.28, seg=50.0,
                       grain_axis="Y", grey=0.25, seed=5.0, seam_w=0.012, seam_dark=0.75)
    # ↑ Pr: (가로=x+y, Y슬롯=z) → 결 방향=z(세로), 판은 가로로 나열
    paint = (0.11, 0.022, 0.016)
    pn = g.nfac(P, 1.2, 5.0, 0.6)
    painted = g.mix(g.lin(pn, 0.3, 0.8, 0.0, 0.5), paint, (0.05, 0.015, 0.012))
    painted = g.mix(0.35, painted, g.mix(1.0, painted, col, "MULTIPLY"))
    painted = g.mix(1.0, painted, g.hsv(col, 0.5, 0.0, 6.0), "MULTIPLY")
    _, _, gz = g.sep(g.gen())
    wn = g.m("MULTIPLY", g.m("SUBTRACT", g.nfac(P, 6.0, 3.0), 0.5), 0.03)
    gzn = g.m("ADD", gz, wn)
    top_w = g.m("MULTIPLY", g.smooth(gzn, 0.90, 0.92), g.smooth(gzn, 0.985, 0.975))
    top_b = g.m("MULTIPLY", g.smooth(gzn, 0.84, 0.855), g.smooth(gzn, 0.89, 0.88))
    bot_b = g.m("MULTIPLY", g.smooth(gzn, 0.04, 0.05), g.smooth(gzn, 0.11, 0.10))
    wear = g.smooth(g.nfac(P, 4.0, 6.0, 0.7), 0.55, 0.62)    # 띠 도장 흔적만 남김
    keep = g.m("SUBTRACT", 1.0, g.m("MULTIPLY", wear, 0.85))
    painted = g.mix(g.m("MULTIPLY", top_w, keep), painted, (0.45, 0.43, 0.38))
    painted = g.mix(g.m("MULTIPLY", g.m("MAXIMUM", top_b, bot_b), keep), painted, (0.03, 0.06, 0.15))
    chips = g.smooth(g.nfac(P, 2.5, 7.0, 0.7, dist=0.3), 0.64, 0.69)
    col = g.mix(chips, painted, col)
    col = _ao_dirt(g, col, amount=0.7, dist=0.3)
    col, rough, _ = _waterline(g, col, g.lin(rv, 0, 1, 0.6, 0.85), strength=0.6)
    nrm = g.bump(g.m("ADD", h, g.m("MULTIPLY", chips, -0.3)), 0.25, 0.01)
    b = g.principled(Base_Color=col, Roughness=rough, Normal=nrm, Specular_IOR_Level=0.4)
    g.output(g.o(b, "BSDF"))
    return mat


def mat_pole_wood(name, dark, light, grey, seed):
    """노/돛대: 결 = 로컬 Z (원기둥을 Z축으로 만든 뒤 회전한다고 가정)."""
    mat = _new_mat(name)
    g = G(mat)
    P = g.obj()
    col, rv, h = _wood(g, P, dark, light, plank_w=0.6, seg=40.0, grain_axis="Z", grey=grey, seed=seed,
                       seam_w=0.0005, seam_dark=0.0)
    knots = g.voronoi(g.comb(*[g.m("MULTIPLY", c, k) for c, k in zip(g.sep(P), (1.0, 1.0, 0.3))]), 3.0, "F1")
    kn = g.smooth(g.o(knots, "Distance"), 0.08, 0.02)
    col = g.mix(g.m("MULTIPLY", kn, 0.7), col, (0.03, 0.02, 0.012))
    col = _ao_dirt(g, col, amount=0.5, dist=0.2)
    col, rough, _ = _waterline(g, col, g.lin(rv, 0, 1, 0.55, 0.8), strength=0.8, band_top=0.3)
    nrm = g.bump(g.m("SUBTRACT", h, kn), 0.25, 0.006)
    b = g.principled(Base_Color=col, Roughness=rough, Normal=nrm, Specular_IOR_Level=0.4)
    g.output(g.o(b, "BSDF"))
    return mat


def _cloth_weave(g, P, period=0.012):
    x, y, z = g.sep(P)
    w1 = g.wave(P, 1.0 / period / 6.283, 0.5, 0.0, direction="X")
    w2 = g.wave(P, 1.0 / period / 6.283, 0.5, 0.0, direction="Z")
    return g.m("MULTIPLY", g.m("ADD", w1, w2), 0.5)


def mat_sail_cloth(name="sail_cloth"):
    """마포 돛: 미색~회갈, 세로 폭(0.55m) 이음 솔기, 얼룩, 은은한 투과(역광)."""
    mat = _new_mat(name)
    g = G(mat)
    P = g.obj()
    x, y, z = g.sep(P)
    across = g.m("ADD", x, y)
    pw = 0.55
    pidx = g.m("FLOOR", g.m("DIVIDE", across, pw))
    pr = g.o(g.white(pidx, dims="1D"), "Value")
    base = g.mix(pr, (0.36, 0.31, 0.23), (0.45, 0.40, 0.31))
    stain = g.nfac(P, 0.9, 5.0, 0.65, dist=0.5)
    base = g.mix(g.smooth(stain, 0.45, 0.8), base, (0.20, 0.17, 0.12))
    streak = g.nfac(g.comb(g.m("MULTIPLY", across, 3.0), g.m("MULTIPLY", z, 0.15), 0.0), 3.0, 3.0)
    base = g.mix(g.m("MULTIPLY", g.smooth(streak, 0.55, 0.8), 0.5), base, (0.18, 0.15, 0.11))
    fa = g.m("FRACT", g.m("DIVIDE", across, pw))
    seam = g.smooth(g.m("MULTIPLY", g.m("MINIMUM", fa, g.m("SUBTRACT", 1.0, fa)), pw), 0.012, 0.004)
    base = g.mix(g.m("MULTIPLY", seam, 0.6), base, (0.12, 0.10, 0.07))
    weave = _cloth_weave(g, P)
    base = g.mix(g.m("MULTIPLY", weave, 0.25), base, g.mix(1.0, base, (0.7, 0.7, 0.7), "MULTIPLY"))
    base = _ao_dirt(g, base, amount=0.4, dist=0.3)
    nrm = g.bump(g.m("ADD", g.m("MULTIPLY", weave, 0.3), g.m("MULTIPLY", seam, 0.6)), 0.15, 0.003)
    b = g.principled(Base_Color=base, Roughness=0.92, Normal=nrm, Sheen_Weight=0.3,
                     Sheen_Roughness=0.6, Specular_IOR_Level=0.25)
    tr = g.node("ShaderNodeBsdfTranslucent", {"Color": g.mix(1.0, base, (0.9, 0.8, 0.6), "MULTIPLY"), "Normal": nrm})
    mx = g.node("ShaderNodeMixShader", {"Fac": 0.22})
    g.nt.links.new(g.o(b, "BSDF"), mx.inputs[1])
    g.nt.links.new(g.o(tr, "BSDF"), mx.inputs[2])
    g.output(g.o(mx, "Shader"))
    return mat


def mat_rope(name="rope"):
    mat = _new_mat(name)
    g = G(mat)
    P = g.obj()
    x, y, z = g.sep(P)
    tw = g.wave(g.comb(g.m("ADD", g.m("ADD", x, y), z), 0.0, 0.0), 16.0, 1.5, 2.0, direction="X")
    n = g.nfac(P, 30.0, 5.0, 0.7)
    col = g.mix(n, (0.11, 0.075, 0.045), (0.20, 0.15, 0.09))
    col = g.mix(g.m("MULTIPLY", g.m("SUBTRACT", 1.0, tw), 0.5), col, g.mix(1.0, col, (0.4, 0.4, 0.4), "MULTIPLY"))
    col = _ao_dirt(g, col, amount=0.5, dist=0.05)
    nrm = g.bump(g.m("ADD", tw, g.m("MULTIPLY", n, 0.3)), 0.4, 0.004)
    b = g.principled(Base_Color=col, Roughness=0.9, Normal=nrm, Sheen_Weight=0.3, Specular_IOR_Level=0.3)
    g.output(g.o(b, "BSDF"))
    return mat


def mat_flag_cloth(name="flag_cloth"):
    """깃발: 색 = 메시 attribute 'flag_color'(색 속성) 우선, 없으면(검정) Object Color(ob.color)."""
    mat = _new_mat(name)
    g = G(mat)
    P = g.obj()
    at = g.node("ShaderNodeAttribute", attribute_name="flag_color", attribute_type="GEOMETRY")
    ac = g.o(at, "Color")
    oi = g.node("ShaderNodeObjectInfo")
    oc = g.o(oi, "Color")
    has = g.m("GREATER_THAN", g.bw(ac), 0.0005)
    col = g.mix(has, oc, ac)
    col = g.hsv(col, 0.5, 0.8, 0.85)  # 바랜 염료
    stain = g.nfac(P, 2.0, 4.0, 0.6)
    col = g.mix(g.m("MULTIPLY", g.smooth(stain, 0.4, 0.8), 0.35), col, g.mix(1.0, col, (0.55, 0.5, 0.42), "MULTIPLY"))
    weave = _cloth_weave(g, P, 0.008)
    col = g.mix(g.m("MULTIPLY", weave, 0.2), col, g.mix(1.0, col, (0.75, 0.75, 0.75), "MULTIPLY"))
    nrm = g.bump(weave, 0.1, 0.002)
    b = g.principled(Base_Color=col, Roughness=0.85, Normal=nrm, Sheen_Weight=0.5, Sheen_Roughness=0.5,
                     Specular_IOR_Level=0.3)
    tr = g.node("ShaderNodeBsdfTranslucent", {"Color": col, "Normal": nrm})
    mx = g.node("ShaderNodeMixShader", {"Fac": 0.3})
    g.nt.links.new(g.o(b, "BSDF"), mx.inputs[1])
    g.nt.links.new(g.o(tr, "BSDF"), mx.inputs[2])
    g.output(g.o(mx, "Shader"))
    return mat


def mat_water(name="water"):
    """바다: 불투명 유전체 반사(IOR 1.333) + 짙은 청록 산란색. Cycles·EEVEE 모두 안정.
    법선 = 다중 스케일 Noise/Wave 잔물결 (월드 XY m 기준). 큰 파도는 모델러 Ocean modifier."""
    mat = _new_mat(name)
    g = G(mat)
    W = g.wpos()
    x, y, z = g.sep(W)
    # 바람 방향으로 늘린 좌표
    Pw = g.comb(g.m("MULTIPLY", x, 1.0), g.m("MULTIPLY", y, 0.6), z)
    n1 = g.nfac(Pw, 0.18, 3.0, 0.5)                      # ~5m 너울 조각
    n2 = g.nfac(Pw, 0.9, 4.0, 0.55, dist=0.3)            # ~1m
    n3 = g.nfac(W, 4.5, 3.0, 0.5)                        # ~20cm
    n4 = g.nfac(W, 18.0, 2.0, 0.5)                       # 미세
    wv = g.wave(g.v("ADD", Pw, g.v("SCALE", g.o(g.noise(W, 0.5, 2.0), "Color"), scale=2.0)),
                0.6, 3.0, 2.0, direction="Y", profile="SIN")
    h = g.m("ADD", g.m("MULTIPLY", n1, 1.6), g.m("MULTIPLY", n2, 0.55))
    h = g.m("ADD", h, g.m("ADD", g.m("MULTIPLY", n3, 0.12), g.m("MULTIPLY", n4, 0.03)))
    h = g.m("ADD", h, g.m("MULTIPLY", wv, 0.25))
    nrm = g.bump(h, 0.55, 0.12)
    # 바람결 패치 → 거칠기 변이
    patch = g.nfac(W, 0.04, 3.0, 0.6)
    rough = g.lin(patch, 0.35, 0.7, 0.025, 0.11)
    col = g.mix(g.smooth(n1, 0.3, 0.7), (0.004, 0.018, 0.020), (0.010, 0.035, 0.034))
    b = g.principled(Base_Color=col, Roughness=rough, IOR=1.333, Normal=nrm, Specular_IOR_Level=0.5,
                     Coat_Weight=0.0)
    g.output(g.o(b, "BSDF"))
    mat.surface_render_method = "DITHERED"
    return mat


def mat_stone(name="stone"):
    """부두 석축: 화강암 마름돌(박스 투영 Brick) + 반점 + 이끼(하부)."""
    mat = _new_mat(name)
    g = G(mat)

    def builder(v):
        br = g.node("ShaderNodeTexBrick", {"Vector": v, "Scale": 1.0, "Mortar Size": 0.025,
                                           "Mortar Smooth": 0.3, "Bias": 0.0, "Brick Width": 1.1,
                                           "Row Height": 0.45, "Color1": (0.30, 0.29, 0.27),
                                           "Color2": (0.20, 0.19, 0.18), "Mortar": (0.05, 0.05, 0.045)},
                        offset=0.5, squash=1.0)
        return g.o(br, "Color"), g.o(br, "Factor")
    col, mort = _box_pattern(g, builder)
    P = g.obj()
    speck = g.nfac(P, 60.0, 2.0, 0.5)
    col = g.mix(g.m("MULTIPLY", g.smooth(speck, 0.55, 0.7), 0.6), col, (0.05, 0.05, 0.05))
    col = g.mix(g.m("MULTIPLY", g.smooth(speck, 0.35, 0.25), 0.4), col, (0.45, 0.44, 0.41))
    blot = g.nfac(P, 1.0, 5.0, 0.6)
    col = g.mix(g.m("MULTIPLY", blot, 0.4), col, g.mix(1.0, col, (0.6, 0.58, 0.52), "MULTIPLY"))
    col = _ao_dirt(g, col, amount=0.7, dist=0.3)
    col, rough, _ = _waterline(g, col, g.lin(blot, 0, 1, 0.7, 0.9), strength=1.0, band_top=0.6)
    h = g.m("ADD", g.m("MULTIPLY", mort, -1.0), g.m("MULTIPLY", g.nfac(P, 8.0, 5.0, 0.6), 0.3))
    nrm = g.bump(h, 0.4, 0.02)
    b = g.principled(Base_Color=col, Roughness=rough, Normal=nrm)
    g.output(g.o(b, "BSDF"))
    return mat


def mat_ground(name="ground"):
    """해안 지면: 흙·모래 + 풀 패치(평탄부) + 자갈 + 경사면은 흙/암반."""
    mat = _new_mat(name)
    g = G(mat)
    W = g.wpos()
    _, _, nz = g.sep(g.wnorm())
    _, _, wz = g.sep(W)
    n1 = g.nfac(W, 0.15, 5.0, 0.6)
    n2 = g.nfac(W, 2.0, 6.0, 0.6)
    soil = g.mix(n2, (0.10, 0.075, 0.05), (0.19, 0.15, 0.11))
    sand = g.mix(n2, (0.28, 0.24, 0.18), (0.36, 0.31, 0.24))
    grass = g.mix(g.nfac(W, 8.0, 4.0, 0.6), (0.035, 0.05, 0.015), (0.09, 0.10, 0.035))
    col = g.mix(g.smooth(wz, 0.8, 0.3), soil, sand)                 # 물가는 모래
    gmask = g.m("MULTIPLY", g.smooth(n1, 0.45, 0.6), g.smooth(nz, 0.8, 0.95))
    gmask = g.m("MULTIPLY", gmask, g.smooth(wz, 0.6, 1.2))
    col = g.mix(gmask, col, grass)
    vor = g.voronoi(W, 9.0, "F1")
    pebble = g.m("MULTIPLY", g.smooth(g.o(vor, "Distance"), 0.3, 0.15), g.smooth(g.nfac(W, 1.2), 0.5, 0.65))
    col = g.mix(pebble, col, g.mix(g.o(vor, "Color"), (0.15, 0.14, 0.13), (0.30, 0.29, 0.27)))
    rock = g.smooth(nz, 0.75, 0.55)
    col = g.mix(rock, col, g.mix(n2, (0.12, 0.115, 0.10), (0.22, 0.21, 0.19)))
    col, rough, _ = _waterline(g, col, g.lin(n2, 0, 1, 0.8, 0.95), strength=0.8, band_top=0.4, algae=False)
    h = g.m("ADD", g.m("MULTIPLY", n2, 0.5), g.m("MULTIPLY", pebble, 0.6))
    h = g.m("ADD", h, g.m("MULTIPLY", g.nfac(W, 25.0, 3.0), 0.2))
    nrm = g.bump(h, 0.35, 0.03)
    b = g.principled(Base_Color=col, Roughness=rough, Normal=nrm, Specular_IOR_Level=0.3)
    g.output(g.o(b, "BSDF"))
    return mat


# ----------------------------------------------------------------------------------------------
def build_all(hex_cell=0.9, hex_line_w=0.075, roof_arc_attr="roof_s", rebuild=True):
    """SPEC §4 재질 전부 생성. rebuild=False 면 이미 있는 재질은 노드를 다시 만들지 않고 재사용."""
    makers = {
        "hull_wood": mat_hull_wood,
        "hull_waterline": mat_hull_waterline,
        "roof_shell": lambda n: mat_roof_shell(n, hex_cell, hex_line_w, roof_arc_attr),
        "iron_spike": mat_iron_spike,
        "dragon_head": mat_dragon_head,
        "ghost_face": mat_ghost_face,
        "wall_panel": mat_wall_panel,
        "oar_wood": lambda n: mat_pole_wood(n, (0.10, 0.075, 0.05), (0.21, 0.16, 0.11), 0.5, 7.0),
        "mast_wood": lambda n: mat_pole_wood(n, (0.08, 0.055, 0.035), (0.17, 0.12, 0.08), 0.4, 9.0),
        "sail_cloth": mat_sail_cloth,
        "rope": mat_rope,
        "flag_cloth": mat_flag_cloth,
        "water": mat_water,
        "stone": mat_stone,
        "ground": mat_ground,
    }
    out = {}
    for name in MAT_NAMES:
        existing = bpy.data.materials.get(name)
        if existing is not None and not rebuild and existing.get("geobuk_matlib"):
            out[name] = existing
            continue
        m = makers[name](name)
        m["geobuk_matlib"] = 1
        out[name] = m
    return out


if __name__ == "__main__":
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mats = build_all()
    print("matlib OK:", ", ".join(f"{k}({len(v.node_tree.nodes)})" for k, v in mats.items()))
