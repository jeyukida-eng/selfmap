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

# 참고 사진(refs/ref_*.jpg, 전쟁기념관 복원선) 고유색 샘플 → 선형 albedo 기준값 (README 표 참고)
REF = {
    "hull_dark": (0.080, 0.034, 0.015), "hull_light": (0.215, 0.098, 0.040),     # 적갈~꿀색 소나무
    "board_dark": (0.115, 0.044, 0.018), "board_light": (0.245, 0.098, 0.036),   # 방패판 판재
    "roof_dark": (0.040, 0.037, 0.035), "roof_light": (0.068, 0.062, 0.057),     # 회흑 육각판
    "iron": (0.020, 0.019, 0.018),                                               # 흑철
    "dragon_wood": (0.034, 0.026, 0.023),                                        # 흑갈 목조
    "sail": (0.42, 0.29, 0.16), "bamboo": (0.36, 0.24, 0.095),
}

MAT_NAMES = [
    "hull_wood", "hull_waterline", "roof_shell", "iron_spike", "dragon_head", "ghost_face",
    "wall_panel", "oar_wood", "mast_wood", "sail_cloth", "rope", "flag_cloth", "water",
    "stone", "ground", "iron_fitting", "bamboo",
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
          seam_dark=0.6, seam_w=0.010, grain_k=0.45):
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
    grain_dark = g.mix(grain_k, base, g.mix(1.0, base, (0.55, 0.50, 0.45), "MULTIPLY"))
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
    col = g.mix(g.m("MULTIPLY", wet, 0.85), col, g.mix(1.0, col, (0.30, 0.28, 0.24), "MULTIPLY"))
    if algae:
        an = g.nfac(P, 4.0, 5.0, 0.7, dist=0.3)
        algae_c = g.mix(an, (0.020, 0.032, 0.010), (0.060, 0.075, 0.022))
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
    col, rv, h = _wood(g, P, REF["hull_dark"], REF["hull_light"], plank_w=0.32, seg=7.5,
                       grain_axis="Y", grey=0.18, seed=1.0, grain_k=0.75)
    col = _ao_dirt(g, col)
    rough = g.lin(rv, 0.0, 1.0, 0.40, 0.65)
    col, rough, _ = _waterline(g, col, rough, strength=0.9)
    nrm = g.bump(h, 0.25, 0.012)
    # 니스(오일) 약한 광택: Coat
    b = g.principled(Base_Color=col, Roughness=rough, Normal=nrm, Specular_IOR_Level=0.4,
                     Coat_Weight=0.25, Coat_Roughness=0.35)
    g.output(g.o(b, "BSDF"))
    return mat


def mat_hull_waterline(name="hull_waterline"):
    mat = _new_mat(name)
    g = G(mat)
    P = g.obj()
    col, rv, h = _wood(g, P, (0.060, 0.026, 0.014), (0.130, 0.058, 0.030), plank_w=0.32, seg=7.5,
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


def mat_roof_shell(name="roof_shell", hex_cell=0.9, line_w=0.035, arc_attr="roof_s"):
    """거북등 지붕: 판 길이방향=Object Y, 가로방향 = attribute `arc_attr`(용마루로부터의 호길이 m,
    좌현 음수) 가 있으면 그것, 없으면 x·θ/sinθ 원호 근사. 홈선 폭 line_w(m) 거의 흑색."""
    mat = _new_mat(name)
    g = G(mat)
    P = g.obj()
    x, y, z = g.sep(P)
    at = g.node("ShaderNodeAttribute", attribute_name=arc_attr, attribute_type="GEOMETRY")
    s_attr = g.o(at, "Factor")
    has = g.m("GREATER_THAN", g.m("ABSOLUTE", s_attr), 1e-4)
    nx, _, nz = g.sep(g.wnorm())
    th = g.m("ARCTAN2", g.m("ABSOLUTE", nx), nz)
    sn = g.m("MAXIMUM", g.m("SINE", th), 0.05)
    s_arc = g.m("MULTIPLY", x, g.m("MINIMUM", g.m("DIVIDE", th, sn), 3.0))
    s = g.mixf(has, s_arc, s_attr)
    edge, cid = _hex(g, s, y, hex_cell)
    crnd = g.white(cid)
    cr = g.o(crnd, "Value")
    cc = g.o(crnd, "Color")
    cr2, _, _ = g.sep(cc)
    line = g.smooth(edge, line_w * 0.5 + 0.003, line_w * 0.5 - 0.003)       # 1 = 홈선
    # 셀별 색: 적갈 ↔ 흑갈 (cr), 명도 ±15% (cr2)
    plate = g.ramp(cr, [(0.0, REF["roof_dark"]), (1.0, REF["roof_light"])])
    plate = g.mix(1.0, plate, g.comb(*(g.lin(cr2, 0, 1, 0.85, 1.15),) * 3), "MULTIPLY")
    # 셀 중앙 마모(약간 밝게)
    center = g.smooth(edge, hex_cell * 0.12, hex_cell * 0.42)
    plate = g.mix(g.m("MULTIPLY", center, 0.15), plate, g.mix(1.0, plate, (1.5, 1.4, 1.3), "MULTIPLY", clamp=False))
    # 대형 오염(기존 대비 50%): 도장 얼룩 + 빗물 줄
    mott = g.nfac(P, 4.0, 8.0, 0.65, dist=0.2)
    plate = g.mix(g.lin(mott, 0.3, 0.75, 0.0, 0.27), plate, g.mix(1.0, plate, (0.55, 0.5, 0.48), "MULTIPLY"))
    stk = g.nfac(g.comb(g.m("MULTIPLY", x, 7.0), g.m("MULTIPLY", y, 7.0), g.m("MULTIPLY", z, 0.35)), 1.0, 4.0, 0.6)
    plate = g.mix(g.m("MULTIPLY", g.smooth(stk, 0.55, 0.78), 0.25), plate, (0.05, 0.045, 0.04))
    gr = g.wave(g.comb(s, g.m("MULTIPLY", y, 0.08), z), 30.0, 6.0, 3.0, 1.0, direction="X")
    plate = g.mix(g.m("MULTIPLY", g.smooth(gr, 0.3, 0.9), 0.2), plate,
                  g.mix(1.0, plate, (0.65, 0.65, 0.65), "MULTIPLY"))
    col = g.mix(g.m("MULTIPLY", line, 0.85), plate, (0.016, 0.015, 0.014))
    # 선 바로 옆 어두운 그늘(홈 가장자리)
    lip = g.m("MULTIPLY", g.smooth(edge, line_w * 0.5 + 0.025, line_w * 0.5), g.m("SUBTRACT", 1.0, line))
    col = g.mix(g.m("MULTIPLY", lip, 0.4), col, g.mix(1.0, col, (0.5, 0.5, 0.5), "MULTIPLY"))
    # 도장 벗겨짐
    chip_n = g.nfac(P, 1.6, 8.0, 0.72, dist=0.2)
    chips = g.smooth(chip_n, 0.70, 0.72)
    col = g.mix(g.m("MULTIPLY", chips, 0.5), col, g.mix(cr, (0.10, 0.06, 0.035), (0.16, 0.09, 0.05)))
    # 먼지(위를 향한 면, 50% 감소)
    dust = g.m("MULTIPLY", g.smooth(nz, 0.3, 0.95), g.smooth(g.nfac(P, 1.5, 5.0, 0.6), 0.45, 0.8))
    col = g.mix(g.m("MULTIPLY", dust, 0.15), col, (0.15, 0.14, 0.13))
    col = _ao_dirt(g, col, amount=0.6, dist=0.25)
    rough = g.m("ADD", g.lin(mott, 0.2, 0.8, 0.55, 0.78), g.m("MULTIPLY", g.m("ADD", dust, chips), 0.15))
    rough = g.m("SUBTRACT", rough, g.m("MULTIPLY", center, 0.08))
    rough = g.mixf(line, rough, 0.85)
    h = g.m("SUBTRACT", g.m("MULTIPLY", g.smooth(edge, 0.0, 0.03), 0.25), g.m("MULTIPLY", line, 0.5))
    h = g.m("ADD", h, g.m("MULTIPLY", chips, -0.1))
    h = g.m("ADD", h, g.m("MULTIPLY", g.nfac(P, 25.0, 3.0), 0.06))
    nrm = g.bump(h, 0.3, 0.02)
    b = g.principled(Base_Color=col, Roughness=rough, Normal=nrm, Specular_IOR_Level=0.45)
    g.output(g.o(b, "BSDF"))
    return mat


def mat_iron(name="iron_spike", rust_amt=0.35, rough_base=0.45, metal_base=0.8, bump_d=0.002):
    """흑철(단조). rust_amt 0..1 녹 비율. iron_spike: 철첨 / iron_fitting: 방패판 꺾쇠·띠·장식(반광, 녹 약간)."""
    mat = _new_mat(name)
    g = G(mat)
    P = g.obj()
    n1 = g.nfac(P, 18.0, 6.0, 0.65, dist=0.3)
    n2 = g.nfac(P, 70.0, 4.0, 0.6)
    thr = 0.75 - 0.25 * rust_amt
    rust = g.smooth(g.m("ADD", n1, g.m("MULTIPLY", n2, 0.25)), thr, thr + 0.12)
    ao = g.ao(0.05)
    rust = g.m("MAXIMUM", rust, g.m("MULTIPLY", g.smooth(ao, 0.9, 0.5), rust_amt))   # 홈·모서리 안쪽 녹
    rust_c = g.ramp(n2, [(0.0, (0.030, 0.015, 0.009)), (0.5, (0.070, 0.032, 0.015)), (1.0, (0.12, 0.055, 0.025))])
    iron_c = g.mix(n2, REF["iron"], (0.040, 0.038, 0.036))
    col = g.mix(rust, iron_c, rust_c)
    col = _ao_dirt(g, col, amount=0.5, dist=0.08)
    metal = g.lin(rust, 0.0, 1.0, metal_base, 0.0)
    rough = g.lin(rust, 0.0, 1.0, rough_base, 0.9)
    rough = g.m("ADD", rough, g.m("MULTIPLY", n2, 0.1))
    h = g.m("ADD", g.m("MULTIPLY", rust, 0.6), g.m("MULTIPLY", n2, 0.4))
    nrm = g.bump(h, 0.3, bump_d)
    b = g.principled(Base_Color=col, Metallic=metal, Roughness=rough, Normal=nrm)
    g.output(g.o(b, "BSDF"))
    return mat


def mat_bamboo(name="bamboo"):
    """대나무 돛살(batten): 황갈색, 로컬 Z 축 방향 길이, 마디(0.32m 간격 띠) + 세로 섬유 줄, 반광."""
    mat = _new_mat(name)
    g = G(mat)
    P = g.obj()
    x, y, z = g.sep(P)
    fz = g.m("FRACT", g.m("DIVIDE", z, 0.32))
    node_d = g.m("MULTIPLY", g.m("MINIMUM", fz, g.m("SUBTRACT", 1.0, fz)), 0.32)
    knot = g.smooth(node_d, 0.012, 0.003)
    fib = g.nfac(g.comb(g.m("MULTIPLY", x, 1.0), g.m("MULTIPLY", y, 1.0), g.m("MULTIPLY", z, 0.03)), 120.0, 3.0, 0.5)
    seg = g.o(g.white(g.m("FLOOR", g.m("DIVIDE", z, 0.32)), dims="1D"), "Value")
    base = g.mix(seg, g.mix(1.0, REF["bamboo"], (0.8, 0.8, 0.8), "MULTIPLY"), REF["bamboo"])
    base = g.mix(g.m("MULTIPLY", fib, 0.3), base, g.mix(1.0, base, (0.75, 0.7, 0.6), "MULTIPLY"))
    base = g.mix(g.m("MULTIPLY", knot, 0.7), base, (0.13, 0.08, 0.035))
    stain = g.smooth(g.nfac(P, 3.0, 5.0, 0.6), 0.5, 0.8)
    base = g.mix(g.m("MULTIPLY", stain, 0.4), base, (0.12, 0.085, 0.05))
    base = _ao_dirt(g, base, amount=0.5, dist=0.1)
    nrm = g.bump(g.m("ADD", knot, g.m("MULTIPLY", fib, 0.2)), 0.3, 0.003)
    b = g.principled(Base_Color=base, Roughness=g.lin(stain, 0, 1, 0.38, 0.6), Normal=nrm,
                     Specular_IOR_Level=0.45, Coat_Weight=0.2, Coat_Roughness=0.3)
    g.output(g.o(b, "BSDF"))
    return mat


def _fade(g, col, P, amount=0.35):
    """채색 바램: 채도/명도 감소 + 얼룩."""
    n = g.nfac(P, 2.0, 5.0, 0.6)
    faded = g.hsv(col, 0.5, 0.6, 1.15)
    faded = g.mix(0.25, faded, (0.28, 0.26, 0.22))
    return g.mix(g.m("MULTIPLY", g.lin(n, 0.3, 0.8, 0.5, 1.0), amount), col, faded)


def mat_dragon_head_wood(name="dragon_head"):
    """용두 (사진 기준 기본): 흑갈색 목조각 + 결 + 조각 골 AO + 모서리 마모(밝은 갈색) + 반광 오일.
    흰 이빨·흰 눈 테·붉은 입속은 모델링 보조 재질(별도 메시)."""
    mat = _new_mat(name)
    g = G(mat)
    P = g.obj()
    x, y, z = g.sep(P)
    gr = g.wave(g.v("ADD", g.comb(x, g.m("MULTIPLY", y, 0.1), z), g.v("SCALE", g.o(g.noise(P, 3.0, 3.0), "Color"), scale=0.1)),
                14.0, 5.0, 3.0, 1.0, direction="Z")
    base = g.mix(g.smooth(gr, 0.2, 0.9), REF["dragon_wood"], (0.060, 0.042, 0.032))
    big = g.nfac(P, 2.0, 5.0, 0.6)
    base = g.mix(g.m("MULTIPLY", big, 0.4), base, (0.022, 0.018, 0.016))
    # 돌출부 마모(AO 반대: 열린 곳은 살짝 밝게)
    ao = g.ao(0.12)
    base = g.mix(g.m("MULTIPLY", g.smooth(ao, 0.9, 1.0), 0.35), base, (0.085, 0.055, 0.038))
    base = _ao_dirt(g, base, (0.01, 0.008, 0.007), amount=0.9, dist=0.12)
    vor = g.voronoi(P, 16.0, "DISTANCE_TO_EDGE")
    scale_line = g.smooth(g.o(vor, "Distance"), 0.05, 0.0)
    base = g.mix(g.m("MULTIPLY", scale_line, 0.5), base, (0.012, 0.010, 0.009))
    rough = g.lin(big, 0, 1, 0.38, 0.6)
    h = g.m("ADD", g.m("MULTIPLY", scale_line, -0.5), g.m("MULTIPLY", gr, 0.25))
    nrm = g.bump(h, 0.3, 0.004)
    b = g.principled(Base_Color=base, Roughness=rough, Normal=nrm, Specular_IOR_Level=0.45,
                     Coat_Weight=0.2, Coat_Roughness=0.35)
    g.output(g.o(b, "BSDF"))
    return mat


def mat_dragon_head(name="dragon_head", style="wood"):
    """style='wood'(기본, 사진) | 'dancheong'(구역 채색)."""
    if style == "wood":
        return mat_dragon_head_wood(name)
    return mat_dragon_head_dancheong(name)


def mat_dragon_head_dancheong(name="dragon_head"):
    """용두 단청 (구역 채색, Generated 좌표: x=폭, y=뒤(0)→주둥이(1), z=아래→위).
    목·정수리 녹청 / 갈기 군청+주홍 끝 / 볼 군청 / 뿔 황토 / 눈두덩 백 / 주둥이·입술·아래턱 주홍 / 배 백토,
    구역 경계 흑선, 비늘(Voronoi), 채도 −20%, 때 20%."""
    mat = _new_mat(name)
    g = G(mat)
    P = g.obj()
    gx, gy, gz = g.sep(g.gen())
    wn = g.m("MULTIPLY", g.m("SUBTRACT", g.nfac(P, 5.0, 3.0, 0.5), 0.5), 0.05)
    gy = g.m("ADD", gy, wn)
    gz = g.m("ADD", gz, g.m("MULTIPLY", wn, 0.7))
    dx = g.m("ABSOLUTE", g.m("SUBTRACT", gx, 0.5))
    teal = (0.09, 0.30, 0.25)
    green = (0.06, 0.20, 0.10)
    blue = (0.035, 0.08, 0.22)
    verm = (0.50, 0.075, 0.035)
    ochre = (0.36, 0.23, 0.07)
    white = (0.44, 0.42, 0.36)
    belly = (0.36, 0.30, 0.19)
    w = 0.006
    col = g.mix(g.smooth(gz, 0.55, 0.75), green, teal)                  # 목: 아래 녹 → 위 녹청
    m_belly = g.smooth(gz, 0.30, 0.26)
    col = g.mix(m_belly, col, belly)
    m_head = g.smooth(gy, 0.40 - w, 0.40 + w)
    m_cheek = g.m("MULTIPLY", m_head, g.m("MULTIPLY", g.smooth(dx, 0.16, 0.19), g.smooth(gz, 0.56, 0.52)))
    col = g.mix(g.m("MULTIPLY", m_head, g.smooth(gz, 0.48, 0.52)), col, teal)
    col = g.mix(m_cheek, col, blue)
    m_jaw = g.m("MULTIPLY", g.smooth(gy, 0.45, 0.47), g.smooth(gz, 0.40, 0.36))
    col = g.mix(m_jaw, col, verm)
    m_snout = g.smooth(gy, 0.82 - w, 0.82 + w)
    col = g.mix(m_snout, col, verm)
    m_brow = g.m("MULTIPLY", g.m("MULTIPLY", g.smooth(gy, 0.45, 0.47), g.smooth(gy, 0.64, 0.62)),
                 g.m("MULTIPLY", g.smooth(gz, 0.58, 0.61), g.smooth(gz, 0.70, 0.67)))
    col = g.mix(m_brow, col, white)
    m_horn = g.m("MULTIPLY", g.smooth(gz, 0.74, 0.78), g.smooth(gy, 0.50, 0.46))
    col = g.mix(m_horn, col, ochre)
    m_mane = g.m("MULTIPLY", g.smooth(dx, 0.30, 0.33), g.smooth(gy, 0.50, 0.46))
    mane_c = g.mix(g.smooth(dx, 0.42, 0.45), blue, verm)
    col = g.mix(m_mane, col, mane_c)
    # 비늘(목·정수리·갈기 제외 영역 위주)
    vor = g.voronoi(P, 16.0, "DISTANCE_TO_EDGE")
    scale_line = g.m("MULTIPLY", g.smooth(g.o(vor, "Distance"), 0.05, 0.0),
                     g.m("SUBTRACT", 1.0, g.m("MAXIMUM", m_snout, m_horn)))
    col = g.mix(g.m("MULTIPLY", scale_line, 0.55), col, (0.02, 0.025, 0.02))
    # 구역 경계 흑선(마스크 경계의 전이폭 → 선)
    def edge_of(mk):
        return g.m("MULTIPLY", g.m("MULTIPLY", mk, g.m("SUBTRACT", 1.0, mk)), 4.0)
    ln = edge_of(m_head)
    for mk in (m_snout, m_cheek, m_jaw, m_brow, m_horn, m_mane):
        ln = g.m("MAXIMUM", ln, edge_of(mk))
    col = g.mix(g.smooth(ln, 0.3, 0.6), col, (0.012, 0.012, 0.012))
    col = g.hsv(col, 0.5, 0.8, 1.0)
    col = _fade(g, col, P, 0.45)
    chips = g.smooth(g.nfac(P, 5.0, 6.0, 0.7), 0.68, 0.71)
    col = g.mix(chips, col, (0.10, 0.085, 0.07))
    dirt = g.smooth(g.nfac(P, 1.5, 5.0, 0.6), 0.4, 0.8)
    col = g.mix(g.m("MULTIPLY", dirt, 0.2), col, g.mix(1.0, col, (0.45, 0.4, 0.33), "MULTIPLY"))
    col = _ao_dirt(g, col, amount=0.85, dist=0.15)
    rough = g.m("ADD", 0.58, g.m("MULTIPLY", g.m("ADD", chips, dirt), 0.15))
    h = g.m("ADD", g.m("MULTIPLY", scale_line, -0.5), g.m("MULTIPLY", g.nfac(P, 40.0, 3.0), 0.2))
    nrm = g.bump(h, 0.3, 0.004)
    b = g.principled(Base_Color=col, Roughness=rough, Normal=nrm, Specular_IOR_Level=0.4)
    g.output(g.o(b, "BSDF"))
    return mat


def mat_ghost_face(name="ghost_face", style="black"):
    """style='black'(기본, 사진: 흑색 바탕+흰 눈·이빨, 붉은 입속) | 'dancheong'(주토 얼굴+녹청 갈기)."""
    return _ghost_face(name, style)


def _ghost_face(name, style):
    """귀면: Generated(x=가로 0..1, z=세로 0..1), 얼굴 = 메시 로컬 XZ 평면(법선 ±Y).
    주토(검붉은) 얼굴 + 흑청 바깥 테·녹/청 불꽃 갈기, 흰 눈자위+주홍 테+흑 눈동자, 녹 눈썹(백 테),
    주홍 코, 흰 이빨·송곳니, 부조 골 AO. (부조 위치는 modeling/build_ghost_face 와 일치)"""
    mat = _new_mat(name)
    g = G(mat)
    P = g.obj()
    gx, gy, gz = g.sep(g.gen())
    dx = g.m("ABSOLUTE", g.m("SUBTRACT", gx, 0.5))
    dz = g.m("SUBTRACT", gz, 0.52)
    face_r = g.v("LENGTH", g.comb(g.m("MULTIPLY", dx, 2.0), g.m("MULTIPLY", dz, 2.0), 0.0))  # 0 중앙, ~1 가장자리
    jit = g.m("MULTIPLY", g.m("SUBTRACT", g.nfac(P, 6.0, 3.0), 0.5), 0.06)
    face_r = g.m("ADD", face_r, jit)
    if style == "black":
        base = g.mix(g.m("MULTIPLY", g.nfac(P, 4.0, 4.0), 0.5), (0.020, 0.018, 0.017), (0.035, 0.028, 0.024))
    else:
        base = g.mix(g.m("MULTIPLY", g.nfac(P, 4.0, 4.0), 0.5), (0.26, 0.04, 0.025), (0.16, 0.03, 0.02))
    # 바깥 갈기: 각도별 녹/청 불꽃 혀 + 흑청 바탕
    ang = g.m("ARCTAN2", g.m("SUBTRACT", gx, 0.5), dz)
    fl = g.m("FRACT", g.m("MULTIPLY", ang, 14.0 / 6.2832))
    flame_c = g.mix(g.smooth(g.m("ABSOLUTE", g.m("SUBTRACT", fl, 0.5)), 0.22, 0.26), (0.05, 0.17, 0.10), (0.03, 0.06, 0.16))
    tongue = g.smooth(g.m("ADD", g.m("MULTIPLY", g.m("ABSOLUTE", g.m("SUBTRACT", fl, 0.5)), 0.5), face_r), 1.08, 1.02)
    outer = g.smooth(face_r, 0.80, 0.84)
    ring_c = g.mix(tongue, (0.018, 0.028, 0.040), flame_c)
    if style == "black":
        ring_c = g.mix(tongue, (0.012, 0.011, 0.010), (0.045, 0.034, 0.026))
    col = g.mix(outer, base, ring_c)
    col = g.mix(g.m("MULTIPLY", g.smooth(g.m("ABSOLUTE", g.m("SUBTRACT", face_r, 0.82)), 0.02, 0.008), 1.0), col,
                (0.01, 0.01, 0.01))
    # 눈
    ed = g.v("LENGTH", g.comb(g.m("SUBTRACT", dx, 0.2), g.m("MULTIPLY", g.m("SUBTRACT", gz, 0.64), 1.3), 0.0))
    sclera = g.smooth(ed, 0.125, 0.115)
    pupil = g.smooth(ed, 0.06, 0.05)
    ring = g.m("MULTIPLY", g.smooth(ed, 0.16, 0.15), g.m("SUBTRACT", 1.0, sclera))
    col = g.mix(ring, col, (0.50, 0.09, 0.035) if style != "black" else (0.012, 0.011, 0.010))
    col = g.mix(g.m("MULTIPLY", g.smooth(g.m("ABSOLUTE", g.m("SUBTRACT", ed, 0.125)), 0.008, 0.003), 1.0), col,
                (0.01, 0.01, 0.01))
    col = g.mix(sclera, col, (0.46, 0.44, 0.38))
    col = g.mix(pupil, col, (0.006, 0.006, 0.006))
    # 눈썹 (녹 + 흰 테)
    bz = g.m("SUBTRACT", gz, g.m("ADD", 0.80, g.m("MULTIPLY", dx, 0.25)))
    bmask = g.m("MULTIPLY", g.smooth(dx, 0.38, 0.36), g.smooth(dx, 0.04, 0.06))
    brow_rim = g.m("MULTIPLY", g.smooth(g.m("ABSOLUTE", bz), 0.055, 0.045), bmask)
    brow = g.m("MULTIPLY", g.smooth(g.m("ABSOLUTE", bz), 0.04, 0.03), bmask)
    col = g.mix(brow_rim, col, (0.40, 0.39, 0.34) if style != "black" else (0.06, 0.05, 0.04))
    if style == "black":
        col = g.mix(brow, col, (0.05, 0.04, 0.032))
    else:
        col = g.mix(brow, col, g.mix(g.nfac(P, 12.0, 3.0), (0.04, 0.16, 0.09), (0.03, 0.08, 0.17)))
    # 코 (주홍) + 콧구멍
    nose = g.v("LENGTH", g.comb(dx, g.m("MULTIPLY", g.m("SUBTRACT", gz, 0.50), 0.8), 0.0))
    col = g.mix(g.smooth(nose, 0.10, 0.085), col, (0.42, 0.07, 0.03) if style != "black" else (0.045, 0.035, 0.028))
    nd = g.v("LENGTH", g.comb(g.m("SUBTRACT", dx, 0.07), g.m("MULTIPLY", g.m("SUBTRACT", gz, 0.46), 1.6), 0.0))
    col = g.mix(g.smooth(nd, 0.04, 0.03), col, (0.02, 0.005, 0.004))
    # 입 + 이빨 + 송곳니
    mouth = g.m("MULTIPLY", g.smooth(g.m("ABSOLUTE", g.m("SUBTRACT", gz, 0.27)), 0.11, 0.10), g.smooth(dx, 0.33, 0.31))
    col = g.mix(mouth, col, (0.035, 0.006, 0.005) if style != "black" else (0.30, 0.04, 0.025))
    tf = g.m("FRACT", g.m("MULTIPLY", gx, 11.0))
    tooth = g.m("MULTIPLY", g.smooth(g.m("ABSOLUTE", g.m("SUBTRACT", tf, 0.5)), 0.42, 0.36),
                g.m("MULTIPLY", g.smooth(g.m("ABSOLUTE", g.m("SUBTRACT", gz, 0.27)), 0.085, 0.075), g.smooth(dx, 0.30, 0.28)))
    fx = g.m("ABSOLUTE", g.m("SUBTRACT", dx, 0.24))
    fang = g.m("MULTIPLY", g.smooth(fx, g.m("MULTIPLY", g.m("SUBTRACT", 0.47, gz), 0.25), 0.0),
               g.m("MULTIPLY", g.smooth(gz, 0.47, 0.45), g.smooth(gz, 0.18, 0.2)))
    teeth = g.m("MAXIMUM", tooth, g.smooth(fang, 0.2, 0.5))
    col = g.mix(teeth, col, (0.50, 0.48, 0.42))
    col = _fade(g, col, P, 0.4)
    chips = g.smooth(g.nfac(P, 6.0, 6.0, 0.7), 0.68, 0.71)
    col = g.mix(chips, col, (0.10, 0.085, 0.07))
    col = _ao_dirt(g, col, (0.02, 0.012, 0.01), amount=1.0, dist=0.08)
    col = _ao_dirt(g, col, amount=0.5, dist=0.3)
    h = g.m("ADD", g.m("MULTIPLY", g.m("ADD", sclera, teeth), 0.4), g.m("MULTIPLY", g.nfac(P, 35.0, 3.0), 0.2))
    h = g.m("SUBTRACT", h, g.m("ADD", g.m("MULTIPLY", pupil, 0.6), g.m("MULTIPLY", mouth, 0.3)))
    nrm = g.bump(h, 0.2, 0.004)
    b = g.principled(Base_Color=col, Roughness=g.m("ADD", 0.55, g.m("MULTIPLY", chips, 0.25)), Normal=nrm)
    g.output(g.o(b, "BSDF"))
    return mat


def mat_wall_panel(name="wall_panel", panel_w=0.9, v_attr="wall_v", style="natural"):
    """방패판: 세로 판재(0.28m, 결=Z) 검붉은 도장, 패판 경계 세로 흑선(panel_w 간격, 3cm),
    상·하단 흑 테(각 ~8cm), 상단 띠에 녹·주홍 단청 반복(0.45m), 상단 흰 선 흔적, 풍화 15%.
    세로 위치 v = attribute `v_attr`(0 하단 → 1 상단, 권장) 없으면 Generated Z."""
    mat = _new_mat(name)
    g = G(mat)
    P = g.obj()
    x, y, z = g.sep(P)
    across = g.m("ADD", x, y)
    Pr = g.comb(across, z, g.m("SUBTRACT", x, y))
    col, rv, h = _wood(g, Pr, REF["board_dark"], REF["board_light"], plank_w=0.28, seg=50.0,
                       grain_axis="Y", grey=0.15, seed=5.0, seam_w=0.008, seam_dark=0.6, grain_k=0.7)
    wood = col
    if style == "natural":
        # 사진 기준: 꿀색~적갈 원목 + 패판 경계 흑선(철띠는 모델러가 iron_fitting 형상으로)
        fp = g.m("FRACT", g.m("DIVIDE", across, panel_w))
        pd = g.m("MULTIPLY", g.m("MINIMUM", fp, g.m("SUBTRACT", 1.0, fp)), panel_w)
        vline = g.smooth(pd, 0.012, 0.008)
        col = g.mix(g.m("MULTIPLY", vline, 0.8), col, (0.02, 0.012, 0.008))
        col = _ao_dirt(g, col, amount=0.7, dist=0.3)
        col, rough, _ = _waterline(g, col, g.lin(rv, 0, 1, 0.38, 0.62), strength=0.6)
        nrm = g.bump(g.m("SUBTRACT", h, g.m("MULTIPLY", vline, 0.6)), 0.25, 0.01)
        b = g.principled(Base_Color=col, Roughness=rough, Normal=nrm, Specular_IOR_Level=0.4,
                         Coat_Weight=0.25, Coat_Roughness=0.35)
        g.output(g.o(b, "BSDF"))
        return mat
    paint = (0.075, 0.019, 0.014)
    pn = g.nfac(P, 1.2, 5.0, 0.6)
    painted = g.mix(g.lin(pn, 0.3, 0.8, 0.0, 0.4), paint, (0.06, 0.016, 0.012))
    painted = g.mix(1.0, painted, g.hsv(col, 0.5, 0.0, 6.0), "MULTIPLY")
    at = g.node("ShaderNodeAttribute", attribute_name=v_attr, attribute_type="GEOMETRY")
    va = g.o(at, "Factor")
    _, _, gz = g.sep(g.gen())
    v = g.mixf(g.m("GREATER_THAN", va, 1e-4), gz, va)
    v = g.m("ADD", v, g.m("MULTIPLY", g.m("SUBTRACT", g.nfac(P, 6.0, 3.0), 0.5), 0.012))
    bt = 0.06   # ≈8cm / 1.35m
    top_k = g.smooth(v, 1.0 - bt - 0.004, 1.0 - bt + 0.004)
    bot_k = g.smooth(v, bt + 0.004, bt - 0.004)
    # 상단 단청 띠 (흑테 바로 아래, 폭 ~0.11)
    dan = g.m("MULTIPLY", g.smooth(v, 1.0 - bt - 0.12, 1.0 - bt - 0.11), g.m("SUBTRACT", 1.0, top_k))
    ph = g.m("FRACT", g.m("DIVIDE", across, 0.45))
    dan_c = g.ramp(ph, [(0.0, (0.05, 0.17, 0.11)), (0.45, (0.40, 0.38, 0.33)), (0.52, (0.42, 0.07, 0.035)),
                        (0.92, (0.40, 0.38, 0.33))], interp="CONSTANT")
    wear = g.smooth(g.nfac(P, 4.0, 6.0, 0.7), 0.58, 0.64)
    keep = g.m("SUBTRACT", 1.0, g.m("MULTIPLY", wear, 0.7))
    painted = g.mix(g.m("MULTIPLY", dan, keep), painted, dan_c)
    # 패판 경계 세로 흑선
    fp = g.m("FRACT", g.m("DIVIDE", across, panel_w))
    pd = g.m("MULTIPLY", g.m("MINIMUM", fp, g.m("SUBTRACT", 1.0, fp)), panel_w)
    vline = g.smooth(pd, 0.017, 0.013)
    black = (0.014, 0.012, 0.011)
    painted = g.mix(g.m("MAXIMUM", g.m("MAXIMUM", top_k, bot_k), vline), painted, black)
    # 흑테 위 가는 흰 선 흔적
    wl = g.m("MULTIPLY", g.smooth(g.m("ABSOLUTE", g.m("SUBTRACT", v, 1.0 - bt - 0.006)), 0.005, 0.002), keep)
    painted = g.mix(wl, painted, (0.40, 0.38, 0.33))
    chips = g.smooth(g.nfac(P, 2.5, 7.0, 0.7, dist=0.3), 0.66, 0.70)
    col = g.mix(chips, painted, wood)
    weath = g.smooth(g.nfac(P, 0.7, 5.0, 0.6), 0.45, 0.8)
    col = g.mix(g.m("MULTIPLY", weath, 0.15), col, (0.16, 0.14, 0.12))
    col = _ao_dirt(g, col, amount=0.7, dist=0.3)
    col, rough, _ = _waterline(g, col, g.lin(rv, 0, 1, 0.6, 0.85), strength=0.6)
    hh = g.m("ADD", h, g.m("MULTIPLY", chips, -0.3))
    hh = g.m("SUBTRACT", hh, g.m("MULTIPLY", vline, 0.6))
    nrm = g.bump(hh, 0.25, 0.01)
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
    base = g.mix(pr, g.mix(1.0, REF["sail"], (0.72, 0.72, 0.72), "MULTIPLY"), REF["sail"])
    stain = g.nfac(P, 0.9, 5.0, 0.65, dist=0.5)
    base = g.mix(g.m("MULTIPLY", g.smooth(stain, 0.4, 0.8), 0.6), base, (0.14, 0.10, 0.06))
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


def mat_water(name="water", foam_attr="hull_dist", foam_width=0.6):
    """바다. Cycles: 투과(IOR 1.333)+청록 볼륨 흡수(+12% 확산 몸체색). EEVEE: 같은 법선·색의 불투명 반사판
    (Material Output 타깃 분리 — 열린 수면 메시에서 EEVEE 볼륨은 바운딩박스를 채우므로 사용 안 함).
    거품: 메시 float attribute `foam_attr`(선체까지 수평거리 m) 0~foam_width 띠. 속성 없으면(0) 거품 없음.
    법선: 도메인 왜곡 + 비정수 배율 다중 스케일 Noise(타일 반복 없음). 큰 파도는 Ocean modifier."""
    mat = _new_mat(name)
    g = G(mat)
    W = g.wpos()
    # 도메인 왜곡(수십 m 스케일) → 반복감 제거
    warp = g.v("SUBTRACT", g.o(g.noise(W, 0.013, 2.0, 0.5), "Color"), (0.5, 0.5, 0.5))
    Wd = g.v("ADD", W, g.v("SCALE", warp, scale=9.0))
    x, y, z = g.sep(Wd)
    Pw = g.comb(x, g.m("MULTIPLY", y, 0.62), z)          # 바람 방향 늘림
    n1 = g.nfac(Pw, 0.2466, 3.0, 0.5)                    # ~4m
    n2 = g.nfac(Pw, 1.137, 4.0, 0.55, dist=0.35)         # ~0.9m
    n3 = g.nfac(Wd, 4.73, 3.0, 0.5)                      # ~20cm
    n4 = g.nfac(Wd, 17.3, 2.0, 0.5)                      # 미세
    rid = g.nfac(Pw, 0.61, 3.0, 0.55, ntype="RIDGED_MULTIFRACTAL", normalize=False)
    h = g.m("ADD", g.m("MULTIPLY", n1, 1.5), g.m("MULTIPLY", n2, 0.55))
    h = g.m("ADD", h, g.m("ADD", g.m("MULTIPLY", n3, 0.12), g.m("MULTIPLY", n4, 0.03)))
    h = g.m("ADD", h, g.m("MULTIPLY", rid, 0.12))
    cam = g.node("ShaderNodeCameraData")
    far = g.smooth(g.o(cam, "View Distance"), 60.0, 900.0, 1.0, 0.08)
    nrm = g.bump(h, g.m("MULTIPLY", far, 0.6), 0.2)
    patch = g.nfac(W, 0.04, 3.0, 0.6)
    rough = g.lin(patch, 0.35, 0.7, 0.02, 0.06)
    # 거품
    at = g.node("ShaderNodeAttribute", attribute_name=foam_attr, attribute_type="GEOMETRY")
    d = g.o(at, "Factor")
    has = g.m("GREATER_THAN", d, 1e-4)
    band = g.m("MULTIPLY", g.smooth(d, foam_width, 0.0), has)
    fn = g.nfac(Wd, 8.0, 6.0, 0.62, dist=0.3)
    foam = g.smooth(g.m("ADD", band, g.m("MULTIPLY", g.m("SUBTRACT", fn, 0.5), 0.9)), 0.6, 0.85)
    foam = g.m("MULTIPLY", foam, has)
    # 셰이더
    body = g.mix(g.smooth(n1, 0.3, 0.7), (0.012, 0.045, 0.042), (0.020, 0.062, 0.055))
    glass = g.principled(Base_Color=(0.85, 0.97, 0.95), Roughness=rough, IOR=1.333, Normal=nrm,
                         Transmission_Weight=1.0)
    diff = g.principled(Base_Color=body, Roughness=rough, IOR=1.333, Normal=nrm, Specular_IOR_Level=0.0)
    mx = g.node("ShaderNodeMixShader", {"Fac": 0.2})
    g.nt.links.new(g.o(glass, "BSDF"), mx.inputs[1])
    g.nt.links.new(g.o(diff, "BSDF"), mx.inputs[2])
    foam_b = g.principled(Base_Color=(0.62, 0.66, 0.66), Roughness=0.55, Normal=nrm, Specular_IOR_Level=0.3)
    mxf = g.node("ShaderNodeMixShader", {"Fac": foam})
    g.nt.links.new(g.o(mx, "Shader"), mxf.inputs[1])
    g.nt.links.new(g.o(foam_b, "BSDF"), mxf.inputs[2])
    vol = g.node("ShaderNodeVolumeAbsorption", {"Color": (0.25, 0.45, 0.42), "Density": 0.6})
    outc = g.node("ShaderNodeOutputMaterial", target="CYCLES")
    g.nt.links.new(g.o(mxf, "Shader"), _sock(outc.inputs, "Surface"))
    g.nt.links.new(g.o(vol, "Volume"), _sock(outc.inputs, "Volume"))
    # EEVEE: 불투명 반사 물 (예전 방식) + 거품
    ecol = g.mix(g.smooth(n1, 0.3, 0.7), (0.004, 0.015, 0.018), (0.008, 0.028, 0.030))
    eb = g.principled(Base_Color=ecol, Roughness=rough, IOR=1.333, Normal=nrm, Specular_IOR_Level=0.5)
    mxe = g.node("ShaderNodeMixShader", {"Fac": foam})
    g.nt.links.new(g.o(eb, "BSDF"), mxe.inputs[1])
    g.nt.links.new(g.o(foam_b, "BSDF"), mxe.inputs[2])
    oute = g.node("ShaderNodeOutputMaterial", target="EEVEE")
    g.nt.links.new(g.o(mxe, "Shader"), _sock(oute.inputs, "Surface"))
    mat.surface_render_method = "DITHERED"
    return mat


def mat_stone(name="stone"):
    """부두 석축: 화강암 마름돌(박스 투영 Brick) + 반점 + 이끼(하부)."""
    mat = _new_mat(name)
    g = G(mat)

    def builder(v):
        br = g.node("ShaderNodeTexBrick", {"Vector": v, "Scale": 1.0, "Mortar Size": 0.025,
                                           "Mortar Smooth": 0.3, "Bias": 0.0, "Brick Width": 1.3,
                                           "Row Height": 0.5, "Color1": (0.17, 0.165, 0.155),
                                           "Color2": (0.10, 0.098, 0.092), "Mortar": (0.03, 0.03, 0.027)},
                        offset=0.5, squash=1.0)
        return g.o(br, "Color"), g.o(br, "Factor")
    col, mort = _box_pattern(g, builder)
    P = g.obj()
    speck = g.nfac(P, 60.0, 2.0, 0.5)
    col = g.mix(g.m("MULTIPLY", g.smooth(speck, 0.55, 0.7), 0.6), col, (0.05, 0.05, 0.05))
    col = g.mix(g.m("MULTIPLY", g.smooth(speck, 0.35, 0.25), 0.4), col, (0.45, 0.44, 0.41))
    blot = g.nfac(P, 1.0, 5.0, 0.6)
    col = g.mix(g.smooth(blot, 0.35, 0.75), col, g.mix(1.0, col, (0.45, 0.43, 0.38), "MULTIPLY"))
    lich = g.m("MULTIPLY", g.smooth(g.nfac(P, 2.5, 6.0, 0.7), 0.6, 0.7), 0.6)
    col = g.mix(lich, col, (0.20, 0.19, 0.14))
    col = _ao_dirt(g, col, amount=0.7, dist=0.3)
    col, rough, _ = _waterline(g, col, g.lin(blot, 0, 1, 0.7, 0.9), strength=1.0, band_top=0.6)
    h = g.m("ADD", g.m("MULTIPLY", mort, -1.0), g.m("MULTIPLY", g.nfac(P, 8.0, 5.0, 0.6), 0.3))
    nrm = g.bump(h, 0.4, 0.02)
    b = g.principled(Base_Color=col, Roughness=rough, Normal=nrm)
    g.output(g.o(b, "BSDF"))
    return mat


def mat_ground(name="ground"):
    """해안 지면·원경 산: 흙/모래(물가)/풀(평탄)/자갈 + 높은 곳(z>3m)·경사면은 숲(짙은 녹, 수관 덩어리)·
    능선 암석 + 카메라 거리 대기원근(Emission 혼합, 색은 world.setup_world 가 'AERIAL_HAZE' 노드에 씀)."""
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
    col = g.mix(g.smooth(wz, 0.8, 0.3), soil, sand)
    gmask = g.m("MULTIPLY", g.smooth(n1, 0.45, 0.6), g.smooth(nz, 0.8, 0.95))
    gmask = g.m("MULTIPLY", gmask, g.smooth(wz, 0.6, 1.2))
    col = g.mix(gmask, col, grass)
    vor = g.voronoi(W, 9.0, "F1")
    pebble = g.m("MULTIPLY", g.smooth(g.o(vor, "Distance"), 0.3, 0.15), g.smooth(g.nfac(W, 1.2), 0.5, 0.65))
    col = g.mix(pebble, col, g.mix(g.o(vor, "Color"), (0.15, 0.14, 0.13), (0.30, 0.29, 0.27)))
    rock = g.smooth(nz, 0.75, 0.55)
    col = g.mix(rock, col, g.mix(n2, (0.12, 0.115, 0.10), (0.22, 0.21, 0.19)))
    # 숲: 수관(Voronoi ~6m) + 50m 노이즈 색 패치, 침엽(짙음)/활엽(밝음) 혼합
    tree = g.voronoi(W, 0.17, "F1")
    crown = g.smooth(g.o(tree, "Distance"), 0.55, 0.1)
    fpatch = g.nfac(W, 0.02, 4.0, 0.6)
    forest = g.mix(g.smooth(fpatch, 0.35, 0.7), (0.020, 0.040, 0.016), (0.055, 0.085, 0.030))
    forest = g.mix(g.m("MULTIPLY", g.o(tree, "Color"), 1.0), forest, g.mix(1.0, forest, (0.7, 0.85, 0.6), "MULTIPLY"))
    forest = g.mix(g.m("SUBTRACT", 1.0, crown), forest, g.mix(1.0, forest, (0.35, 0.35, 0.35), "MULTIPLY"))
    ridge_rock = g.m("MULTIPLY", g.smooth(nz, 0.6, 0.4), g.smooth(g.nfac(W, 0.05, 4.0), 0.5, 0.65))
    forest = g.mix(ridge_rock, forest, g.mix(n2, (0.10, 0.10, 0.09), (0.17, 0.165, 0.15)))
    fmask = g.m("MULTIPLY", g.smooth(wz, 2.5, 6.0), g.smooth(g.m("ADD", fpatch, g.m("MULTIPLY", wz, 0.004)), 0.15, 0.3))
    col = g.mix(fmask, col, forest)
    col, rough, _ = _waterline(g, col, g.lin(n2, 0, 1, 0.8, 0.95), strength=0.8, band_top=0.4, algae=False)
    h = g.m("ADD", g.m("MULTIPLY", n2, 0.5), g.m("MULTIPLY", pebble, 0.6))
    h = g.m("ADD", h, g.m("MULTIPLY", g.nfac(W, 25.0, 3.0), 0.2))
    h = g.m("ADD", h, g.m("MULTIPLY", g.m("MULTIPLY", crown, fmask), 6.0))
    nrm = g.bump(h, 0.35, 0.03)
    b = g.principled(Base_Color=col, Roughness=rough, Normal=nrm, Specular_IOR_Level=0.3)
    # 대기원근: f = 1 - exp(-d / 1800m), 최대 0.75
    cam = g.node("ShaderNodeCameraData")
    dist = g.o(cam, "View Distance")
    fa = g.m("MULTIPLY", g.m("SUBTRACT", 1.0, g.m("EXPONENT", g.m("DIVIDE", dist, -1800.0))), 0.75)
    haze = g.node("ShaderNodeRGB", name="AERIAL_HAZE")
    haze.outputs[0].default_value = (2.2, 2.7, 3.6, 1.0)
    em = g.node("ShaderNodeEmission", {"Color": g.o(haze, "Color"), "Strength": 1.0})
    mx = g.node("ShaderNodeMixShader", {"Fac": fa})
    g.nt.links.new(g.o(b, "BSDF"), mx.inputs[1])
    g.nt.links.new(g.o(em, "Emission"), mx.inputs[2])
    g.output(g.o(mx, "Shader"))
    return mat


# ----------------------------------------------------------------------------------------------
def build_all(hex_cell=0.9, hex_line_w=0.035, roof_arc_attr="roof_s", rebuild=True,
              dragon_style="wood", ghost_style="black", wall_style="natural"):
    """SPEC §4 재질 전부 생성. rebuild=False 면 이미 있는 재질은 노드를 다시 만들지 않고 재사용."""
    makers = {
        "hull_wood": mat_hull_wood,
        "hull_waterline": mat_hull_waterline,
        "roof_shell": lambda n: mat_roof_shell(n, hex_cell, hex_line_w, roof_arc_attr),
        "iron_spike": lambda n: mat_iron(n, rust_amt=0.25, rough_base=0.5),
        "iron_fitting": lambda n: mat_iron(n, rust_amt=0.15, rough_base=0.38, metal_base=0.75, bump_d=0.001),
        "bamboo": mat_bamboo,
        "dragon_head": lambda n: mat_dragon_head(n, dragon_style),
        "ghost_face": lambda n: mat_ghost_face(n, ghost_style),
        "wall_panel": lambda n: mat_wall_panel(n, style=wall_style),
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
