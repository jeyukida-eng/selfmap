"""검증 비교: 렌더 vs 참고사진(있으면) 또는 설계 JSON 투영 → round<N>/compare_<id>.png, contact_sheet.png, scores.json, fixlist.md
실행: /opt/bvenv/bin/python validation/compare.py --round 2

입력: round<N>/render_<id>.png, mask_<id>.png, render_meta.json (render_views.py 산출)
      round<N>/assessment.json (선택) — 사람이/에이전트가 렌더를 직접 보고 쓴 [주관] 점수·근거·수정목록.
      없으면 assessment_template.json 을 써 두고 [정량] 축만 채운다.

모드
 * refs/ref_<id>.jpg 가 있으면(참고 모드): 참고|렌더 나란히(참고 사진은 리사이즈만 — 사진 위에 선·라벨을 그리지 않음,
   라벨은 별도 띠에) + 보조 지표:
   - 실루엣 IoU: validation/ref_masks/<id>.json 의 수동 다각형(사진과 별도 파일) vs 렌더 클래스 마스크
   - 고유색 ΔE: 사진 흰 벽/바닥 patch 로 화이트밸런스 정규화(albedo≈px/white*0.8) vs 렌더 Diffuse Color 패스
     (albedo_<id>.npy) 의 같은 클래스 평균; 보이는 색(렌더 beauty vs WB 사진)도 L*·C* 로 병기
   - 엣지 밀도: 배 영역 안 그래디언트>임계 비율
   설계 투영 비교(와이어 오버레이·IoU)는 렌더 쪽에만 그려 병기.
 * 없으면(현재 컨테이너: Wikimedia 차단): 설계 기반 비교.
   설계 JSON 의 선체·상장벽·개판 스테이션 단면을 같은 카메라 행렬로 투영 →
   (a) 렌더 (b) 설계 와이어 (c) 렌더+와이어 오버레이 (d) 마스크 차이(초록=일치, 빨강=렌더만, 파랑=설계만)
   렌더 클래스 마스크(물 위·부두에 안 가린 부분) 대 설계 투영 마스크 IoU 를 실루엣/비례 점수 근거로 사용.
"""
import argparse
import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DESIGN = os.path.join(ROOT, "design", "geobukseon_design.json")
REFS = os.path.join(ROOT, "refs")
AXES = ["silhouette", "detail", "material", "lighting", "composition", "environment"]
WEIGHTS = {"silhouette": 0.25, "detail": 0.20, "material": 0.20, "lighting": 0.10,
           "composition": 0.10, "environment": 0.15}
# render_views.py 와 동일 (선형 0/0.5/1)
CLASS_COLORS = {"hull": (1, 0, 0), "wall": (0, 1, 0), "roof": (0.5, 1, 0), "dragon": (0, 0, 1), "ghost": (1, 1, 0),
                "oars": (1, 0, 1), "rigging": (0, 1, 1), "sail": (1, 0.5, 0), "other": (1, 1, 1)}
BODY = ("hull", "wall", "roof", "dragon", "ghost")
OCCLUDERS = ("oars", "rigging", "sail", "other")
REF_MASKS = os.path.join(HERE, "ref_masks")
COLOR_CLASSES = ("hull", "wall", "roof", "sail", "dragon")


def font(sz):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


# ------------------------------------------------------------------------------------------------
# 카메라 투영
# ------------------------------------------------------------------------------------------------
class Cam:
    def __init__(self, m):
        self.M = np.array(m["world_to_cam"], float)
        self.fx, self.fy, self.cx, self.cy = m["fx"], m["fy"], m["cx"], m["cy"]
        self.w, self.h = m["width"], m["height"]

    def proj(self, P):
        P = np.atleast_2d(np.asarray(P, float))
        q = P @ self.M[:3, :3].T + self.M[:3, 3]
        z = np.minimum(q[:, 2], -1e-3)  # 카메라는 -Z 를 봄
        u = self.cx + self.fx * q[:, 0] / -z
        v = self.cy - self.fy * q[:, 1] / -z
        return np.stack([u, v], 1)


def interp(st, key, y):
    s = sorted(st, key=lambda r: r["y"])
    return np.interp(y, [r["y"] for r in s], [r[key] for r in s])


# ------------------------------------------------------------------------------------------------
# 설계 기하 (JSON → 3D 폴리곤/폴리라인)
# ------------------------------------------------------------------------------------------------
def design_geometry(d, dy=0.2):
    """반환: polys{cls:[Nx3,...]} (마스크 채움용, 물 아래는 z=0으로 눌러 수면 위 실루엣만),
             lines[(Nx3, color, width)] (와이어 오버레이용)."""
    polys = {"hull": [], "super": [], "dragon": []}
    lines = []
    H = d["hull"]["stations"]
    ys = np.arange(min(r["y"] for r in H), max(r["y"] for r in H) + 1e-6, dy)

    def hsec(y):
        bh, sh, kz, sz = (interp(H, k, y) for k in ("bottom_half", "sheer_half", "keel_z", "sheer_z"))
        return np.array([[-sh, y, sz], [-bh, y, kz], [bh, y, kz], [sh, y, sz]])

    def below(P):
        """수면 아래 부분 (참고 모드에서 실내 거치 사진과 비교 제외 영역 계산용)."""
        Q = P.copy()
        Q[:, 2] = -Q[:, 2]
        R = clampz_(Q)
        if len(R):
            R[:, 2] = -R[:, 2]
        return R

    def clampz(P):
        if len(P) >= 3:
            polys.setdefault("submerged", []).append(below(P))
        return clampz_(P)

    def clampz_(P):
        """폴리곤을 수면(z=0) 위로 클리핑(Sutherland-Hodgman). 전부 물 아래면 빈 배열."""
        out = []
        n = len(P)
        for i in range(n):
            a, b = P[i], P[(i + 1) % n]
            if a[2] >= 0:
                out.append(a)
            if (a[2] >= 0) != (b[2] >= 0):
                t = a[2] / (a[2] - b[2])
                out.append(a + t * (b - a))
        return np.array(out) if len(out) >= 3 else np.zeros((0, 3))
    secs = [hsec(y) for y in ys]
    for a, b in zip(secs, secs[1:]):
        for i in range(3):
            polys["hull"].append(clampz(np.array([a[i], a[i + 1], b[i + 1], b[i]])))
        polys["hull"].append(clampz(np.array([a[0], a[3], b[3], b[0]])))  # 갑판 면
    polys["hull"] += [clampz(secs[0]), clampz(secs[-1])]
    for r in H:  # 스테이션 링
        lines.append((hsec(r["y"])[[0, 1, 2, 3, 0]], (255, 80, 80), 1))
    for i, c in ((0, (255, 80, 80)), (1, (255, 140, 140)), (2, (255, 140, 140)), (3, (255, 80, 80))):
        lines.append((np.array([s[i] for s in secs]), c, 2))
    # 수선(z=0) 교선: 현측 선분과 z=0 교점
    wl = []
    for s in secs:
        for (p, q) in ((s[0], s[1]), (s[3], s[2])):
            if (p[2] - 0) * (q[2] - 0) < 0:
                t = p[2] / (p[2] - q[2])
                wl.append(p + t * (q - p))
    if wl:
        wl = np.array(wl)
        for sgn in (-1, 1):
            side = wl[np.sign(wl[:, 0]) == sgn]
            if len(side) > 1:
                lines.append((side[np.argsort(side[:, 1])], (80, 200, 255), 2))

    # 상장(벽)
    W = d["superstructure"]["wall"]["stations"]
    wys = np.arange(min(r["y"] for r in W), max(r["y"] for r in W) + 1e-6, dy)
    wy_top = lambda y: interp(W, "top_z", y)
    wy_half = lambda y: interp(W, "half", y)
    wy_bot = lambda y: interp(H, "sheer_z", y) - 0.25
    for sgn in (-1, 1):
        top = np.array([[sgn * wy_half(y), y, wy_top(y)] for y in wys])
        bot = np.array([[sgn * wy_half(y), y, wy_bot(y)] for y in wys])
        for i in range(len(wys) - 1):
            polys["super"].append(np.array([bot[i], bot[i + 1], top[i + 1], top[i]]))
        lines.append((top, (80, 255, 80), 2))
    for y in (wys[0], wys[-1]):
        hw = wy_half(y)
        polys["super"].append(np.array([[-hw, y, wy_bot(y)], [hw, y, wy_bot(y)], [hw, y, wy_top(y)], [-hw, y, wy_top(y)]]))
    for r in W:
        y = r["y"]
        lines.append((np.array([[-r["half"], y, wy_top(y)], [-r["half"], y, wy_bot(y)]]), (80, 255, 80), 1))
        lines.append((np.array([[r["half"], y, wy_top(y)], [r["half"], y, wy_bot(y)]]), (80, 255, 80), 1))

    # 개판(지붕) 초타원 단면
    rf = d["superstructure"]["roof"]
    Rt = rf["stations"]
    pexp = rf.get("profile_exponent", 2.0)
    ths = np.linspace(math.pi, 0, 33)

    def rring(y):
        hx, e, r = interp(Rt, "half", y), interp(Rt, "eave_z", y), interp(Rt, "ridge_z", y)
        c, s = np.cos(ths), np.sin(ths)
        x = hx * np.sign(c) * np.abs(c) ** (2.0 / pexp)
        z = e + (r - e) * np.abs(s) ** (2.0 / pexp)
        return np.column_stack([x, np.full_like(x, y), z])

    rys = np.arange(min(r["y"] for r in Rt), max(r["y"] for r in Rt) + 1e-6, dy)
    rings = [rring(y) for y in rys]
    for a, b in zip(rings, rings[1:]):
        for i in range(len(ths) - 1):
            polys["super"].append(np.array([a[i], a[i + 1], b[i + 1], b[i]]))
    polys["super"] += [rings[0], rings[-1]]
    for r in Rt:
        lines.append((rring(r["y"]), (255, 230, 60), 1))
    lines.append((np.array([g[len(ths) // 2] for g in rings]), (255, 230, 60), 2))  # 용마루
    for i in (0, -1):
        lines.append((np.array([g[i] for g in rings]), (255, 200, 40), 2))  # 처마

    # 용두: v2 = 목(base→head_base 원기둥) + 머리(head_base 에서 pitch 방향 length 타원체). v1 = base 에서 머리.
    dh = d["dragon_head"]
    p = math.radians(dh["pitch_deg"])
    ax = np.array([0, math.cos(p), math.sin(p)])
    up = np.array([0, -math.sin(p), math.cos(p)])
    h0 = np.array(dh.get("head_base", dh["base"]), float)
    c0 = h0 + ax * dh["length"] / 2
    uu, vv = np.meshgrid(np.linspace(0, 2 * math.pi, 24), np.linspace(-math.pi / 2, math.pi / 2, 12))
    pts = (c0[None, :] + (np.cos(vv) * np.cos(uu)).reshape(-1, 1) * ax * dh["length"] / 2
           + (np.cos(vv) * np.sin(uu)).reshape(-1, 1) * np.array([1, 0, 0]) * dh.get("width", 0.75) / 2
           + np.sin(vv).reshape(-1, 1) * up * dh["height"] / 2)
    polys["dragon"].append(("hull3d", pts))
    if "head_base" in dh:
        b0 = np.array(dh["base"], float)
        r = dh.get("neck_radius", 0.3)
        ring = np.array([[r * math.cos(t), r * math.sin(t), 0] for t in np.linspace(0, 2 * math.pi, 16)])
        polys["dragon"].append(("hull3d", np.vstack([b0 + ring, h0 + ring])))
        lines.append((np.array([b0, h0]), (90, 140, 255), 3))
    lines.append((np.array([h0, h0 + ax * dh["length"]]), (90, 140, 255), 3))

    # 귀면 사각형 (JSON 해석 그대로: 법선 = +Y 에서 위로 tilt)
    gf = d["ghost_face"]
    t = math.radians(gf.get("normal_tilt_deg", 0))
    gup = np.array([0, -math.sin(t), math.cos(t)])
    gx = np.array([1, 0, 0])
    gc = np.array(gf["center"])
    q = [gc + sx * gx * gf["width"] / 2 + sz * gup * gf["height"] / 2 for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1))]
    lines.append((np.array(q), (255, 60, 255), 2))

    # 노
    o = d["oars"]
    a = math.radians(o["angle_deg"])
    Lout = o["length"] * (1 - o.get("inboard_fraction", 0.3))
    for y in o["y"]:
        for sgn in (-1, 1):
            p0 = np.array([sgn * wy_half(y), y, o["port_z"]])
            p1 = p0 + Lout * np.array([sgn * math.cos(a), 0, -math.sin(a)])
            lines.append((np.array([p0, p1]), (255, 150, 40), 2))
    # 돛대
    for m in d["masts"]:
        lines.append((np.array([[0, m["y"], m["base_z"]], [0, m["y"], m["base_z"] + m["height"]]]), (60, 230, 230), 2))
    # 포혈(현측)
    gp = d["gun_ports"]
    s2 = gp["size"] / 2
    for g in gp["side"]:
        for sgn in (-1, 1):
            x = sgn * wy_half(g["y"])
            sq = np.array([[x, g["y"] - s2, g["z"] - s2], [x, g["y"] + s2, g["z"] - s2], [x, g["y"] + s2, g["z"] + s2],
                           [x, g["y"] - s2, g["z"] + s2], [x, g["y"] - s2, g["z"] - s2]])
            lines.append((sq, (255, 255, 255), 1))
    return polys, lines


def convex_hull(P):
    P = sorted(map(tuple, P))
    if len(P) < 3:
        return P

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in P:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(P):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


def design_masks(cam, polys):
    """화가 알고리즘(먼 것부터)으로 클래스 라벨 이미지를 그려 가림을 반영한 클래스별 마스크."""
    items = []
    for ci, (cls, lst) in enumerate(polys.items(), start=1):
        for P in lst:
            P3 = P[1] if isinstance(P, tuple) else P
            if len(P3) < 3:
                continue
            q = P3 @ cam.M[:3, :3].T + cam.M[:3, 3]
            depth = float(-q[:, 2].mean())
            uv = convex_hull(cam.proj(P3)) if isinstance(P, tuple) else [tuple(x) for x in cam.proj(P3)]
            items.append((depth, ci, uv))
    items.sort(key=lambda t: -t[0])
    im = Image.new("L", (cam.w, cam.h), 0)
    dr = ImageDraw.Draw(im)
    for _, ci, uv in items:
        if len(uv) >= 3:
            dr.polygon(uv, fill=ci)
    lab = np.array(im)
    return {cls: lab == ci for ci, cls in enumerate(polys, start=1)}



def srgb2lin(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin2srgb(c):
    c = np.clip(np.asarray(c, float), 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def lin2lab(rgb):
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = M @ np.asarray(rgb, float) / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    L, a, b = 116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])
    return np.array([L, a, b])


def lab_desc(lab):
    return {"L": round(float(lab[0]), 1), "C": round(float(math.hypot(lab[1], lab[2])), 1),
            "h_deg": round(float(math.degrees(math.atan2(lab[2], lab[1])) % 360), 1)}


def palette_classify(path, w, h):
    m = np.array(Image.open(path).convert("RGBA").resize((w, h), Image.NEAREST)).astype(float)
    alpha = m[..., 3] > 127
    names = list(CLASS_COLORS)
    pal = np.array([lin2srgb(np.array(CLASS_COLORS[k], float)) * 255 for k in names])
    d = ((m[..., None, :3] - pal[None, None]) ** 2).sum(-1)
    idx = d.argmin(-1)
    return {k: alpha & (idx == i) for i, k in enumerate(names)}


def poly_mask(polys, src_size, w, h):
    sx, sy = w / src_size[0], h / src_size[1]
    im = Image.new("L", (w, h), 0)
    dr = ImageDraw.Draw(im)
    for P in polys:
        dr.polygon([(x * sx, y * sy) for x, y in P], fill=255)
    return np.array(im) > 127


def erode(m, n=2):
    out = m.copy()
    for _ in range(n):
        o = out.copy()
        o[1:] &= out[:-1]; o[:-1] &= out[1:]; o[:, 1:] &= out[:, :-1]; o[:, :-1] &= out[:, 1:]
        out = o
    return out


def iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else float("nan")


def bbox(m):
    ys, xs = np.nonzero(m)
    if not len(xs):
        return None
    return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]


def bbox_iou(a, b):
    if not a or not b:
        return 0.0
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - ix
    return ix / ua if ua else 0.0


def strip(w, text, sz=16, h=26):
    im = Image.new("RGB", (w, h), (0, 0, 0))
    ImageDraw.Draw(im).text((6, 4), text, fill=(255, 255, 255), font=font(sz))
    return im


def tile(im, text, sz=15):
    """라벨을 이미지 위가 아니라 위쪽 띠에 붙임(참고 사진 비변형)."""
    s = strip(im.width, text, sz)
    out = Image.new("RGB", (im.width, im.height + s.height))
    out.paste(s, (0, 0))
    out.paste(im, (0, s.height))
    return out


def draw_lines(im, cam, lines, scale=1.0):
    dr = ImageDraw.Draw(im)
    for P, col, wdt in lines:
        uv = [tuple(x * scale) for x in cam.proj(P)]
        dr.line(uv, fill=col, width=max(1, int(round(wdt * scale))))
    return im


def edge_density(gray, mask=None):
    g = gray.astype(float) / 255
    ref_px = g[mask] if mask is not None and mask.any() else g
    g = g / max(np.percentile(ref_px, 98), 1e-3)  # 노출 차이 정규화(배 영역 기준)
    gx = np.abs(np.diff(g, axis=1))[:-1, :]
    gy = np.abs(np.diff(g, axis=0))[:, :-1]
    mag = np.hypot(gx, gy) > 0.08
    if mask is not None:
        mk = mask[:-1, :-1]
        return float(mag[mk].mean()) if mk.any() else float("nan")
    return float(mag.mean())


def diff_image(ren, a, b, valid=None):
    """초록=둘 다, 빨강=렌더만(a), 파랑=비교대상만(b), 회색 점=비교 제외."""
    W, H = ren.size
    g = np.array(ren.convert("L")) // 3
    out = np.repeat(g[..., None], 3, 2).astype(np.uint8)
    out[a & b] = (40, 170, 60)
    out[a & ~b] = (230, 50, 50)
    out[b & ~a] = (50, 90, 240)
    if valid is not None:
        inv = ~valid
        out[inv & ((np.indices((H, W)).sum(0) % 4) == 0)] = (150, 150, 150)
    return Image.fromarray(out)


# ------------------------------------------------------------------------------------------------
# 설계 검사 (정량, 렌더 무관)
# ------------------------------------------------------------------------------------------------
def design_checks(d):
    out = {}
    bt = d["hull"]["bow_transom"]
    gf = d["ghost_face"]
    cz = gf["center"][2]
    t = (cz - bt["z_bottom"]) / (bt["z_top"] - bt["z_bottom"])
    y_surf = bt["y_bottom"] + t * (bt["y_top"] - bt["y_bottom"])
    rake = math.degrees(math.atan2(bt["z_top"] - bt["z_bottom"], bt["y_top"] - bt["y_bottom"]))
    n_tilt = -(90 - rake)
    out["ghost_face"] = {
        "json_center_y": gf["center"][1], "transom_surface_y_at_center_z": round(y_surf, 3),
        "gap_m": round(y_surf - gf["center"][1], 3), "transom_rake_from_horizontal_deg": round(rake, 1),
        "transom_outward_normal_tilt_deg(+up)": round(n_tilt, 1), "json_normal_tilt_deg": gf.get("normal_tilt_deg"),
        "consistent": bool(abs(y_surf - gf["center"][1]) < 0.03 and gf.get("normal_tilt_deg") is not None
                           and abs(gf["normal_tilt_deg"] - n_tilt) < 3)}
    return out


def composite_score(*vals):
    vals = [v for v in vals if v is not None and not (isinstance(v, float) and math.isnan(v))]
    return round(sum(vals) / len(vals), 1) if vals else None


# ------------------------------------------------------------------------------------------------
def color_compare(vid, ref, ren, alb, rm, rj, W, H):
    """고유색: 사진 patch(WB 정규화) vs 렌더 클래스 마스크 평균(알베도/보이는 색)."""
    rw, rh = rj["size"]
    ref_lin = srgb2lin(np.array(ref.convert("RGB"), float) / 255)
    wm = poly_mask([rj["patches"]["white"]], (rw, rh), rw, rh)
    wp = ref_lin[wm]
    lum = wp @ np.array([0.2126, 0.7152, 0.0722])
    wp = wp[lum >= np.median(lum)]
    white = np.median(wp, 0)
    gains = white.mean() / white  # WB(밝기 유지)
    ren_lin = srgb2lin(np.array(ren, float) / 255)
    out = {"white_patch_lin": [round(float(x), 3) for x in white], "classes": {}}
    for cls in COLOR_CLASSES:
        if cls not in rj["patches"]:
            continue
        pm = poly_mask([rj["patches"][cls]], (rw, rh), rw, rh)
        r_alb = np.median(ref_lin[pm] / white * rj.get("white_albedo_assumed", 0.8), 0)
        r_disp = np.median(ref_lin[pm] * gains, 0)
        mk = erode(rm[cls], 2)
        if mk.sum() < 30:
            out["classes"][cls] = {"note": "렌더에서 이 클래스가 거의 안 보임", "render_px": int(mk.sum())}
            continue
        e = {"render_px": int(mk.sum())}
        la_ref = lin2lab(r_alb)
        e["ref_albedo_est"] = {"srgb": [int(x) for x in lin2srgb(r_alb) * 255], **lab_desc(la_ref)}
        if alb is not None:
            a_r = np.median(alb[mk].astype(float), 0)
            la_r = lin2lab(a_r)
            e["render_albedo"] = {"srgb": [int(x) for x in lin2srgb(a_r) * 255], **lab_desc(la_r)}
            e["dE_albedo"] = round(float(np.linalg.norm(la_r - la_ref)), 1)
            e["dL_albedo"] = round(float(la_r[0] - la_ref[0]), 1)
            e["dC_albedo"] = round(float(math.hypot(*la_r[1:]) - math.hypot(*la_ref[1:])), 1)
        d_r = np.median(ren_lin[mk], 0)
        la_d, la_rd = lin2lab(d_r), lin2lab(r_disp)
        e["render_display"] = {"srgb": [int(x) for x in lin2srgb(d_r) * 255], **lab_desc(la_d)}
        e["ref_display_wb"] = {"srgb": [int(x) for x in lin2srgb(r_disp) * 255], **lab_desc(la_rd)}
        e["dE_display"] = round(float(np.linalg.norm(la_d - la_rd)), 1)
        e["dL_display"] = round(float(la_d[0] - la_rd[0]), 1)
        e["dC_display"] = round(float(math.hypot(*la_d[1:]) - math.hypot(*la_rd[1:])), 1)
        out["classes"][cls] = e
    des = [c["dE_albedo"] for c in out["classes"].values() if "dE_albedo" in c]
    out["mean_dE_albedo"] = round(float(np.mean(des)), 1) if des else None
    dd = [c["dE_display"] for c in out["classes"].values() if "dE_display" in c]
    out["mean_dE_display"] = round(float(np.mean(dd)), 1) if dd else None
    return out


def swatch_strip(cc, w):
    """고유색 견본(사진 추정 알베도 vs 렌더 알베도, 사진 WB 보이는 색 vs 렌더 보이는 색) — 별도 이미지."""
    rows = [(k, v) for k, v in cc["classes"].items() if "render_display" in v]
    h = 30 * (len(rows) + 1)
    im = Image.new("RGB", (w, h), (25, 25, 25))
    dr = ImageDraw.Draw(im)
    f = font(13)
    dr.text((6, 8), "class | ref albedo est | render albedo | ref WB display | render display   dE(albedo) dE(display) dL dC", fill=(255, 255, 255), font=f)
    for i, (k, v) in enumerate(rows):
        y = 30 * (i + 1)
        dr.text((6, y + 8), k, fill=(255, 255, 255), font=f)
        for j, key in enumerate(("ref_albedo_est", "render_albedo", "ref_display_wb", "render_display")):
            if key in v:
                dr.rectangle((70 + j * 70, y + 3, 130 + j * 70, y + 27), fill=tuple(v[key]["srgb"]))
        dr.text((360, y + 8), f"{v.get('dE_albedo', '-')}  {v['dE_display']}  dL {v['dL_display']:+}  dC {v['dC_display']:+}  (albedo dL {v.get('dL_albedo', '-')} dC {v.get('dC_albedo', '-')})",
                fill=(255, 255, 255), font=f)
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, required=True)
    a = ap.parse_args()
    rd = os.path.join(HERE, f"round{a.round}")
    with open(DESIGN, encoding="utf-8") as f:
        d = json.load(f)
    with open(os.path.join(rd, "render_meta.json")) as f:
        meta = json.load(f)
    assess = None
    asp = os.path.join(rd, "assessment.json")
    if os.path.exists(asp):
        with open(asp, encoding="utf-8") as f:
            assess = json.load(f)
    prev = None
    pp = os.path.join(HERE, f"round{a.round - 1}", "scores.json")
    if os.path.exists(pp):
        with open(pp, encoding="utf-8") as f:
            prev = json.load(f)

    polys, lines = design_geometry(d)
    order = [v["id"] for v in d["views"] if v["id"] in meta["views"]]
    results, sheet_rows = {}, []
    for vid in order:
        vm = meta["views"][vid]
        cam = Cam(vm)
        W, H = cam.w, cam.h
        ren = Image.open(os.path.join(rd, f"render_{vid}.png")).convert("RGB")
        refp = os.path.join(REFS, f"ref_{vid}.jpg")
        rjp = os.path.join(REF_MASKS, f"{vid}.json")
        res = {"mode": "reference" if os.path.exists(refp) else "design"}
        perr = [float(np.hypot(*(cam.proj(pt)[0] - np.array(vm["probes_px"][k][:2]))))
                for k, pt in {"origin": (0, 0, 0), "bow_top": (0, 12.8, 2.45), "stern_top": (0, -12.8, 2.7)}.items()]
        res["projection_check_px"] = round(max(perr), 3)

        rm = palette_classify(os.path.join(rd, f"mask_{vid}.png"), W, H)
        occl = np.zeros((H, W), bool)
        for k in OCCLUDERS:
            occl |= rm[k]
        r_body = np.zeros((H, W), bool)
        for k in BODY:
            r_body |= rm[k]
        # --- 설계 투영 ---
        dm = design_masks(cam, {k: v for k, v in polys.items() if k != "submerged"})
        for k in dm:
            dm[k] &= ~occl
        d_body = dm["hull"] | dm["super"] | dm["dragon"]
        # 수면 아래 선체(설계 투영) 중 수면 위 몸체에 안 가린 부분 — 사진(거치대 위 선체)과 비교 시 제외
        sub = design_masks(cam, {"submerged": polys["submerged"]})["submerged"] & ~d_body & ~r_body
        res["design_iou"] = {"body": round(iou(d_body, r_body), 4), "hull": round(iou(dm["hull"], rm["hull"]), 4),
                             "superstructure": round(iou(dm["super"], rm["wall"] | rm["roof"]), 4),
                             "dragon": round(iou(dm["dragon"], rm["dragon"]), 4)}
        dr_i = res["design_iou"]["dragon"]
        sil_design = 100 * (res["design_iou"]["body"] if math.isnan(dr_i) else 0.7 * res["design_iou"]["body"] + 0.3 * dr_i)
        rb = bbox(r_body)
        res["framing"] = {"render_bbox": rb, "cropped_by_frame": bool(rb and (rb[0] <= 0 or rb[2] >= W - 1 or rb[1] <= 0 or rb[3] >= H - 1)),
                          "width_fill": round((rb[2] - rb[0]) / W, 3) if rb else 0}
        quant = {"silhouette_design": round(sil_design, 1)}
        over = draw_lines(ren.copy(), cam, lines)
        ddiff = diff_image(ren, r_body, d_body)

        alb = None
        ap_ = os.path.join(rd, f"albedo_{vid}.npy")
        if os.path.exists(ap_):
            alb = np.load(ap_)
            if alb.shape[:2] != (H, W):
                alb = None
        if res["mode"] == "reference":
            ref = Image.open(refp).convert("RGB")
            rj = json.load(open(rjp, encoding="utf-8"))
            ref_r = ref.resize((W, H), Image.LANCZOS)  # 리사이즈만
            P = rj["polygons"]
            f_body = poly_mask([P["body"]], rj["size"], W, H)
            f_sail = poly_mask([P["sail"]], rj["size"], W, H) if "sail" in P else np.zeros_like(f_body)
            valid = ~(f_sail | occl | sub)
            rb_v, fb_v = r_body & valid, f_body & valid
            res["ref_iou"] = {"body": round(iou(rb_v, fb_v), 4)}
            if "dragon" in P:
                f_dr = poly_mask([P["dragon"]], rj["size"], W, H)
                res["ref_iou"]["dragon"] = round(iou(rm["dragon"] & valid, f_dr & valid), 4)
            fbb = bbox(f_body)
            res["ref_bbox"] = fbb
            res["bbox_iou_vs_ref"] = round(bbox_iou(rb, fbb), 4)
            ed_r = edge_density(np.array(ren.convert("L")), r_body)
            ed_f = edge_density(np.array(ref_r.convert("L")), f_body)
            res["edge_density"] = {"render_body": round(ed_r, 4), "ref_body": round(ed_f, 4),
                                   "ratio": round(ed_r / ed_f, 3) if ed_f else None}
            cc = color_compare(vid, ref, ren, alb, rm, rj, W, H)
            res["color"] = cc
            quant["silhouette_ref"] = round(100 * res["ref_iou"]["body"], 1)
            quant["silhouette"] = round(0.6 * quant["silhouette_ref"] + 0.4 * sil_design, 1)
            cx_off = abs(((rb[0] + rb[2]) - (fbb[0] + fbb[2])) / 2 / W) if rb and fbb else 1
            quant["composition"] = round(max(0, 100 * res["bbox_iou_vs_ref"] - 100 * cx_off - (10 if res["framing"]["cropped_by_frame"] and not (fbb and (fbb[0] <= 1 or fbb[2] >= W - 2)) else 0)), 1)
            r = res["edge_density"]["ratio"]
            quant["detail"] = round(100 * min(r, 1 / r), 1) if r else None
            mde = cc["mean_dE_albedo"] if cc["mean_dE_albedo"] is not None else cc["mean_dE_display"]
            quant["material"] = round(max(0, 100 - 2.5 * mde), 1) if mde is not None else None
            # ---- 패널 ----
            fm = np.zeros((H, W, 3), np.uint8)
            fm[f_body] = (60, 160, 60)
            fm[f_sail] = (200, 180, 60)
            fdiff = diff_image(ren, rb_v, fb_v, valid)
            T = [tile(ref_r, f"REFERENCE {vid} (resized only) - {next((v['author'] + ', ' + v['license']) for v in json.load(open(os.path.join(REFS, 'refs_manifest.json'), encoding='utf-8'))['views'] if v['id'] == vid)}"),
                 tile(ren, f"RENDER {meta['engine']} {meta['samples']}spp {vm['render_sec']}s"),
                 tile(Image.fromarray(fm), "REF POLYGON MASK (validation/ref_masks, separate file)"),
                 tile(over, "RENDER + DESIGN JSON WIRE"),
                 tile(fdiff, f"RENDER vs REF MASK  IoU {res['ref_iou']['body']:.3f}  (grey dots = excluded: sails/rigging/oars/underwater hull)"),
                 tile(ddiff, f"RENDER vs DESIGN PROJ  IoU {res['design_iou']['body']:.3f}")]
            tw, th = T[0].size
            sw = swatch_strip(cc, tw * 3)
            panel = Image.new("RGB", (tw * 3, th * 2 + sw.height))
            for i, t in enumerate(T):
                panel.paste(t, ((i % 3) * tw, (i // 3) * th))
            panel.paste(sw, (0, th * 2))
            row_tiles = (T[0], T[1], T[4])
        else:
            quant["silhouette"] = round(sil_design, 1)
            T = [tile(ren, f"RENDER {vid}"), tile(over, "RENDER + DESIGN WIRE"), tile(ddiff, f"vs DESIGN IoU {res['design_iou']['body']:.3f}")]
            tw, th = T[0].size
            panel = Image.new("RGB", (tw * 3, th))
            for i, t in enumerate(T):
                panel.paste(t, (i * tw, 0))
            row_tiles = T
        res["quant"] = quant
        panel.save(os.path.join(rd, f"compare_{vid}.png"))
        rh = 330
        row = Image.new("RGB", (sum(int(t.width * rh / t.height) for t in row_tiles), rh))
        x = 0
        for t in row_tiles:
            tw2 = int(t.width * rh / t.height)
            row.paste(t.resize((tw2, rh), Image.LANCZOS), (x, 0))
            x += tw2
        sheet_rows.append(row)
        results[vid] = res

    SW = max(r.width for r in sheet_rows)
    mode = "reference photos (indoor museum replica: background/lighting excluded)" if any(r["mode"] == "reference" for r in results.values()) \
        else "design-based (no reference photos)"
    sheet = Image.new("RGB", (SW, sum(r.height for r in sheet_rows) + 34), (0, 0, 0))
    ImageDraw.Draw(sheet).text((8, 6), f"Round {a.round} | {mode} | columns: reference / render / render-vs-ref-mask",
                               fill=(255, 255, 255), font=font(18))
    y = 34
    for r in sheet_rows:
        sheet.paste(r, (0, y))
        y += r.height
    sheet.save(os.path.join(rd, "contact_sheet.png"))

    # ---- 점수 ----
    scores = {"round": a.round, "mode": mode, "weights": WEIGHTS,
              "render": {k: meta.get(k) for k in ("engine", "samples", "res", "long_side", "quality")},
              "render_time_sec": {v: meta["views"][v]["render_sec"] for v in order},
              "design_checks": design_checks(d), "views": {},
              "notes": "[정량]=마스크 IoU·bbox·엣지밀도·ΔE 계산, [주관]=렌더 육안 평가(assessment.json). 같은 축에 둘 다 있으면 평균. "
                       "참고 사진은 실내 전시 복원선이라 lighting·environment 는 [주관](항구/물 사실감)만."}
    if assess is None:
        with open(os.path.join(rd, "assessment_template.json"), "w", encoding="utf-8") as f:
            json.dump({"views": {v: {ax: {"score": None, "why": ""} for ax in AXES} for v in order}, "fixlist": []},
                      f, ensure_ascii=False, indent=1)
    tots = []
    for vid in order:
        r = results[vid]
        av = (assess or {}).get("views", {}).get(vid, {})
        axes = {}
        for ax in AXES:
            q = r["quant"].get(ax)
            s = av.get(ax, {}).get("score")
            basis = []
            if q is not None:
                if ax == "silhouette":
                    basis.append(f"[정량] ref IoU {r.get('ref_iou', {}).get('body', float('nan')):.3f}, design IoU {r['design_iou']['body']:.3f}")
                elif ax == "composition":
                    basis.append(f"[정량] bbox IoU vs ref {r.get('bbox_iou_vs_ref')}")
                elif ax == "detail":
                    basis.append(f"[정량] edge density ratio {r['edge_density']['ratio']}")
                elif ax == "material":
                    basis.append(f"[정량] mean ΔE albedo {r['color']['mean_dE_albedo']} / display {r['color']['mean_dE_display']}")
            if s is not None:
                basis.append("[주관] " + av[ax].get("why", ""))
            axes[ax] = {"score": composite_score(q, s), "quant": q, "subjective": s, "basis": " | ".join(basis)}
        have = [(WEIGHTS[k], v["score"]) for k, v in axes.items() if v["score"] is not None]
        tot = round(sum(w * s for w, s in have) / sum(w for w, _ in have), 1) if have else None
        tots.append(tot)
        ent = {"axes": axes, "weighted_total": tot, "quant": r["quant"], "design_iou": r["design_iou"],
               "framing": r["framing"], "projection_check_px": r["projection_check_px"]}
        for k in ("ref_iou", "ref_bbox", "bbox_iou_vs_ref", "edge_density", "color"):
            if k in r:
                ent[k] = r[k]
        if prev and vid in prev.get("views", {}):
            pv = prev["views"][vid]
            ent["delta_vs_prev"] = {ax: (round(axes[ax]["score"] - pv["axes"][ax]["score"], 1)
                                         if axes[ax]["score"] is not None and pv["axes"].get(ax, {}).get("score") is not None else None)
                                    for ax in AXES}
            ent["delta_vs_prev"]["weighted_total"] = round(tot - pv["weighted_total"], 1) if tot is not None and pv.get("weighted_total") is not None else None
        scores["views"][vid] = ent
    vals = [t for t in tots if t is not None]
    scores["overall_weighted_total"] = round(sum(vals) / len(vals), 1) if vals else None
    if prev:
        scores["overall_delta_vs_prev"] = round(scores["overall_weighted_total"] - prev["overall_weighted_total"], 1) \
            if scores["overall_weighted_total"] is not None and prev.get("overall_weighted_total") is not None else None
        scores["delta_caveat"] = (f"round{a.round - 1} 은 참고 사진 없이 설계 투영만으로 채점, 카메라도 설계 v1(안벽 구도). "
                                  f"round{a.round} 은 사진 기준·카메라 v2 — Δ 는 같은 축 정의의 점수 차이일 뿐 같은 화면 비교가 아님.")
    with open(os.path.join(rd, "scores.json"), "w", encoding="utf-8") as f:
        json.dump(scores, f, ensure_ascii=False, indent=1)

    # ---- fixlist.md ----
    L = [f"# Round {a.round} 수정목록", "",
         f"모드: {mode}. 총점(가중 평균) **{scores['overall_weighted_total']}** / 100"
         + (f" (Δ {scores['overall_delta_vs_prev']:+} vs round{a.round - 1})" if prev and scores.get('overall_delta_vs_prev') is not None else "") + ". "
         "형식: `[ID] [담당] [우선순위] 문제 → 수정 지시 → 기대 효과`. 렌더 시간 대비 효과 큰 순.", "",
         "| 뷰 | " + " | ".join(AXES) + " | 총점 | Δ총점 |", "|---|" + "---|" * (len(AXES) + 2)]
    for vid in order:
        e = scores["views"][vid]
        dl = e.get("delta_vs_prev", {})
        L.append(f"| {vid} | " + " | ".join(
            f"{e['axes'][k]['score']}" + (f" ({dl[k]:+})" if dl.get(k) is not None else "") for k in AXES)
            + f" | {e['weighted_total']} | {dl.get('weighted_total', '-') if dl.get('weighted_total') is None else format(dl['weighted_total'], '+')} |")
    L.append("")
    if any("ref_iou" in results[v] for v in order):
        L.append("정량: " + "; ".join(
            f"{v} refIoU {results[v]['ref_iou']['body']:.3f} / designIoU {results[v]['design_iou']['body']:.3f} / "
            f"edge {results[v]['edge_density']['ratio']} / ΔE albedo {results[v]['color']['mean_dE_albedo']} display {results[v]['color']['mean_dE_display']}"
            for v in order if "ref_iou" in results[v]))
        L.append("")
    if prev:
        L += ["> " + scores["delta_caveat"], ""]
    for note in (assess or {}).get("summary", []):
        L.append(f"- {note}")
    if (assess or {}).get("summary"):
        L.append("")
    items = (assess or {}).get("fixlist", [])
    for prio in ("P1", "P2", "P3"):
        sel = [it for it in items if it["prio"] == prio]
        if not sel:
            continue
        L += [f"## {prio}", ""]
        for it in sel:
            L.append(f"- **[{it['id']}] [담당: {it['owner']}] [{prio}]** {it['problem']}  \n"
                     f"  → {it['fix']}  \n  → 기대 효과: {it['effect']}")
        L.append("")
    if not items:
        L.append("(assessment.json 없음 — [주관] 평가 후 compare.py 재실행)")
    with open(os.path.join(rd, "fixlist.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    for vid in order:
        r = results[vid]
        print(f"[compare] {vid}: quant {r['quant']} refIoU {r.get('ref_iou')} designIoU {r['design_iou']} "
              f"edge {r.get('edge_density')} dE {r.get('color', {}).get('mean_dE_albedo')}/{r.get('color', {}).get('mean_dE_display')} proj {r['projection_check_px']}")
    print("[compare] overall", scores["overall_weighted_total"], "->", rd)


if __name__ == "__main__":
    main()
