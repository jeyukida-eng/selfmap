"""검증 비교: 렌더 vs 참고사진(있으면) 또는 설계 JSON 투영 → round<N>/compare_<id>.png, contact_sheet.png, scores.json, fixlist.md
실행: /opt/bvenv/bin/python validation/compare.py --round 1

입력: round<N>/render_<id>.png, mask_<id>.png, render_meta.json (render_views.py 산출)
      round<N>/assessment.json (선택) — 사람이/에이전트가 렌더를 직접 보고 쓴 [주관] 점수·근거·수정목록.
      없으면 assessment_template.json 을 써 두고 [정량] 축만 채운다.

모드
 * refs/ref_<id>.jpg 가 있으면: 참고|렌더 나란히(같은 높이) + 엣지밀도/색 히스토그램 보조 지표.
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
CLASS_COLORS = {"hull": (1, 0, 0), "super": (0, 1, 0), "dragon": (0, 0, 1), "ghost": (1, 1, 0),
                "oars": (1, 0, 1), "rigging": (0, 1, 1), "other": (1, 1, 1)}
BODY = ("hull", "super", "dragon", "ghost")


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

    clampz = lambda P: np.column_stack([P[:, 0], P[:, 1], np.maximum(P[:, 2], 0.0)])
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

    # 용두: 기준점에서 pitch 방향으로 length, 타원체
    dh = d["dragon_head"]
    p = math.radians(dh["pitch_deg"])
    ax = np.array([0, math.cos(p), math.sin(p)])
    up = np.array([0, -math.sin(p), math.cos(p)])
    c0 = np.array(dh["base"]) + ax * dh["length"] / 2
    uu, vv = np.meshgrid(np.linspace(0, 2 * math.pi, 24), np.linspace(-math.pi / 2, math.pi / 2, 12))
    pts = (c0[None, :] + (np.cos(vv) * np.cos(uu)).reshape(-1, 1) * ax * dh["length"] / 2
           + (np.cos(vv) * np.sin(uu)).reshape(-1, 1) * np.array([1, 0, 0]) * dh.get("width", 0.75) / 2
           + np.sin(vv).reshape(-1, 1) * up * dh["height"] / 2)
    polys["dragon"].append(("hull3d", pts))
    lines.append((np.array([dh["base"], list(np.array(dh["base"]) + ax * dh["length"])]), (90, 140, 255), 3))

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
    out = {}
    for cls, lst in polys.items():
        im = Image.new("L", (cam.w, cam.h), 0)
        dr = ImageDraw.Draw(im)
        for P in lst:
            if isinstance(P, tuple):
                uv = convex_hull(cam.proj(P[1]))
            else:
                uv = [tuple(x) for x in cam.proj(P)]
            if len(uv) >= 3:
                dr.polygon(uv, fill=255)
        out[cls] = np.array(im) > 127
    return out


def render_masks(path, w, h):
    m = np.array(Image.open(path).convert("RGBA").resize((w, h), Image.NEAREST))
    alpha = m[..., 3] > 127
    rgb = (m[..., :3] > 127).astype(int)
    out = {}
    for k, c in CLASS_COLORS.items():
        out[k] = alpha & (rgb[..., 0] == c[0]) & (rgb[..., 1] == c[1]) & (rgb[..., 2] == c[2])
    return out


def iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else float("nan")


def bbox(m):
    ys, xs = np.nonzero(m)
    if not len(xs):
        return None
    return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]


def label(im, text, xy=(10, 8), sz=22):
    dr = ImageDraw.Draw(im)
    f = font(sz)
    x0, y0, x1, y1 = dr.textbbox(xy, text, font=f)
    dr.rectangle((x0 - 5, y0 - 3, x1 + 5, y1 + 3), fill=(0, 0, 0))
    dr.text(xy, text, fill=(255, 255, 255), font=f)
    return im


def draw_lines(im, cam, lines, scale=1.0):
    dr = ImageDraw.Draw(im)
    for P, col, wdt in lines:
        uv = [tuple(x * scale) for x in cam.proj(P)]
        dr.line(uv, fill=col, width=max(1, int(round(wdt * scale))))
    return im


# ------------------------------------------------------------------------------------------------
# 참고사진 모드 보조 지표
# ------------------------------------------------------------------------------------------------
def edge_density(gray):
    g = gray.astype(float) / 255
    gx = np.abs(np.diff(g, axis=1))[:-1, :]
    gy = np.abs(np.diff(g, axis=0))[:, :-1]
    mag = np.hypot(gx, gy)
    return float((mag > 0.08).mean())


def hist_corr(a, b, bins=32):
    ha, _ = np.histogram(a, bins=bins, range=(0, 255), density=True)
    hb, _ = np.histogram(b, bins=bins, range=(0, 255), density=True)
    ha, hb = ha - ha.mean(), hb - hb.mean()
    den = math.sqrt((ha ** 2).sum() * (hb ** 2).sum())
    return float((ha * hb).sum() / den) if den else float("nan")


def ref_metrics(ref, ren):
    r = np.array(ref.convert("HSV")).reshape(-1, 3)
    q = np.array(ren.convert("HSV")).reshape(-1, 3)
    return {"edge_density_ref": edge_density(np.array(ref.convert("L"))),
            "edge_density_render": edge_density(np.array(ren.convert("L"))),
            "hue_hist_corr": hist_corr(r[:, 0], q[:, 0]), "sat_hist_corr": hist_corr(r[:, 1], q[:, 1]),
            "val_hist_corr": hist_corr(r[:, 2], q[:, 2])}


def side_by_side(ref, ren, vid):
    h = ren.height
    rr = ref.resize((int(ref.width * h / ref.height), h), Image.LANCZOS)
    out = Image.new("RGB", (rr.width + ren.width, h))
    out.paste(rr, (0, 0))
    out.paste(ren, (rr.width, 0))
    label(out, f"REFERENCE ({vid})")
    label(out, "RENDER", (rr.width + 10, 8))
    return out


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
    # 이물비우 바깥 법선: 면 방향 (0, dy, dz) 에 수직이며 +Y 성분 양수 → (0, dz, -dy) → 아래로 기울어짐
    n_tilt = -(90 - rake)
    out["ghost_face"] = {
        "json_center_y": gf["center"][1], "transom_surface_y_at_center_z": round(y_surf, 3),
        "gap_m": round(y_surf - gf["center"][1], 3), "transom_rake_from_horizontal_deg": round(rake, 1),
        "transom_outward_normal_tilt_deg(+up)": round(n_tilt, 1), "json_normal_tilt_deg": gf.get("normal_tilt_deg"),
        "verdict": ("불일치: center 가 이물비우 면 안쪽 %.2f m, JSON normal_tilt(+%s°, 위로) ↔ 실제 바깥 법선 %.1f°(아래로)"
                    % (y_surf - gf["center"][1], gf.get("normal_tilt_deg"), n_tilt))}
    dh = d["dragon_head"]
    tip = dh["base"][1] + dh["length"] * math.cos(math.radians(dh["pitch_deg"]))
    out["dragon_tip_y"] = round(tip, 2)
    return out


# ------------------------------------------------------------------------------------------------
def composite_score(q, s):
    vals = [v for v in (q, s) if v is not None]
    return round(sum(vals) / len(vals), 1) if vals else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, required=True)
    a = ap.parse_args()
    rd = os.path.join(HERE, f"round{a.round}")
    with open(DESIGN, encoding="utf-8") as f:
        d = json.load(f)
    with open(os.path.join(rd, "render_meta.json")) as f:
        meta = json.load(f)
    asp = os.path.join(rd, "assessment.json")
    assess = None
    if os.path.exists(asp):
        with open(asp, encoding="utf-8") as f:
            assess = json.load(f)

    polys, lines = design_geometry(d)
    order = [v["id"] for v in d["views"] if v["id"] in meta["views"]]
    results, sheet_rows = {}, []
    for vid in order:
        vm = meta["views"][vid]
        cam = Cam(vm)
        ren = Image.open(os.path.join(rd, f"render_{vid}.png")).convert("RGB")
        refp = os.path.join(REFS, f"ref_{vid}.jpg")
        res = {"mode": "reference" if os.path.exists(refp) else "design"}
        # 투영 자기검증 (Blender world_to_camera_view 와 비교)
        perr = []
        for k, pt in {"origin": (0, 0, 0), "bow_top": (0, 12.8, 2.45), "stern_top": (0, -12.8, 2.7)}.items():
            mine = cam.proj(pt)[0]
            bl = vm["probes_px"][k]
            perr.append(float(np.hypot(*(mine - np.array(bl[:2])))))
        res["projection_check_px"] = round(max(perr), 3)

        dm = design_masks(cam, polys)
        rm = render_masks(os.path.join(rd, f"mask_{vid}.png"), cam.w, cam.h)
        d_body = dm["hull"] | dm["super"] | dm["dragon"]
        r_body = rm["hull"] | rm["super"] | rm["dragon"] | rm["ghost"]
        res["iou"] = {"body": round(iou(d_body, r_body), 4),
                      "hull": round(iou(dm["hull"] & ~dm["super"], rm["hull"] & ~rm["super"]), 4),
                      "superstructure": round(iou(dm["super"], rm["super"]), 4),
                      "dragon": round(iou(dm["dragon"], rm["dragon"]), 4)}
        res["area_px"] = {"render_body": int(r_body.sum()), "design_body": int(d_body.sum()),
                          "render_only": int((r_body & ~d_body).sum()), "design_only": int((d_body & ~r_body).sum())}
        rb, db = bbox(r_body), bbox(d_body)
        res["bbox"] = {"render": rb, "design": db}
        W, Hh = cam.w, cam.h
        crop = rb is not None and (rb[0] <= 0 or rb[2] >= W - 1 or rb[1] <= 0 or rb[3] >= Hh - 1)
        fill = (rb[2] - rb[0]) / W if rb else 0
        cxo = ((rb[0] + rb[2]) / 2 - W / 2) / W if rb else 0
        res["framing"] = {"cropped_by_frame": bool(crop), "width_fill": round(fill, 3), "center_offset_x": round(cxo, 3)}
        # [정량] 실루엣 점수: 몸체 IoU 70% + 용두 IoU 30%
        dr_iou = res["iou"]["dragon"] if not math.isnan(res["iou"]["dragon"]) else 0
        sil_q = 100 * (0.7 * res["iou"]["body"] + 0.3 * dr_iou)
        # [정량] 구도 점수: 설계 의도(같은 카메라) bbox 대비 일치 + 잘림 패널티 + 채움율 (0.45~0.9 권장)
        if rb and db:
            ix = max(0, min(rb[2], db[2]) - max(rb[0], db[0])) * max(0, min(rb[3], db[3]) - max(rb[1], db[1]))
            ua = (rb[2] - rb[0]) * (rb[3] - rb[1]) + (db[2] - db[0]) * (db[3] - db[1]) - ix
            bi = ix / ua if ua else 0
            comp_q = 100 * bi - (15 if crop else 0) - (10 if not (0.45 <= fill <= 0.92) else 0)
        else:
            comp_q = 0
        res["quant"] = {"silhouette": round(max(0, min(100, sil_q)), 1), "composition": round(max(0, min(100, comp_q)), 1)}

        # ---- 패널 ----
        if res["mode"] == "reference":
            ref = Image.open(refp).convert("RGB")
            res["ref_metrics"] = ref_metrics(ref, ren)
            sbs = side_by_side(ref, ren, vid)
        wire = Image.new("RGB", (W, Hh), (18, 18, 24))
        wire.paste(Image.fromarray((d_body * 50).astype(np.uint8)).convert("RGB"), (0, 0))
        draw_lines(wire, cam, lines)
        over = draw_lines(ren.copy(), cam, lines)
        diff = np.zeros((Hh, W, 3), np.uint8)
        g = np.array(ren.convert("L")) // 3
        diff[...] = g[..., None]
        diff[r_body & d_body] = (40, 170, 60)
        diff[r_body & ~d_body] = (230, 50, 50)
        diff[d_body & ~r_body] = (50, 90, 240)
        diffim = Image.fromarray(diff)
        label(ren, f"[{vid}] RENDER  ({meta['engine']} {meta['samples']}spp, {vm['render_sec']}s)")
        label(wire, "DESIGN JSON PROJECTION (hull red / wall green / roof yellow / dragon blue / ghost magenta / oars orange / masts cyan)", sz=15)
        label(over, "OVERLAY: render + design wire")
        label(diffim, f"MASK  green=both red=render-only blue=design-only   IoU body {res['iou']['body']:.3f}  "
                      f"hull {res['iou']['hull']:.3f}  super {res['iou']['superstructure']:.3f}  dragon {res['iou']['dragon']:.3f}", sz=15)
        panel = Image.new("RGB", (W * 2, Hh * 2))
        panel.paste(ren, (0, 0))
        panel.paste(wire, (W, 0))
        panel.paste(over, (0, Hh))
        panel.paste(diffim, (W, Hh))
        if res["mode"] == "reference":
            p2 = Image.new("RGB", (max(panel.width, sbs.width), panel.height + sbs.height))
            p2.paste(sbs, (0, 0))
            p2.paste(panel, (0, sbs.height))
            panel = p2
        panel.save(os.path.join(rd, f"compare_{vid}.png"))
        sw = 640
        row = Image.new("RGB", (sw * 3, int(Hh * sw / W)))
        for i, im in enumerate((ren, over, diffim)):
            row.paste(im.resize((sw, row.height), Image.LANCZOS), (i * sw, 0))
        sheet_rows.append(row)
        results[vid] = res

    sheet = Image.new("RGB", (sheet_rows[0].width, sum(r.height for r in sheet_rows) + 40), (0, 0, 0))
    dr = ImageDraw.Draw(sheet)
    mode = "reference photos" if any(r["mode"] == "reference" for r in results.values()) else \
        "design-based (no reference photos available: refs/ref_*.jpg missing)"
    dr.text((10, 8), f"Round {a.round} contact sheet  |  mode: {mode}  |  columns: render / overlay / mask diff",
            fill=(255, 255, 255), font=font(20))
    y = 40
    for r in sheet_rows:
        sheet.paste(r, (0, y))
        y += r.height
    sheet.save(os.path.join(rd, "contact_sheet.png"))

    # ---- 점수 ----
    scores = {"round": a.round, "mode": mode, "weights": WEIGHTS, "render": {k: meta[k] for k in ("engine", "samples", "res", "quality")},
              "render_time_sec": {v: meta["views"][v]["render_sec"] for v in order}, "design_checks": design_checks(d),
              "views": {}, "notes": "점수 출처: [정량]=마스크 IoU/bbox 계산, [주관]=렌더 육안 평가(assessment.json). 같은 축에 둘 다 있으면 평균."}
    if assess is None:
        tmpl = {"views": {v: {ax: {"score": None, "why": ""} for ax in AXES} for v in order}, "fixlist": []}
        with open(os.path.join(rd, "assessment_template.json"), "w", encoding="utf-8") as f:
            json.dump(tmpl, f, ensure_ascii=False, indent=1)
    tot_all = []
    for vid in order:
        r = results[vid]
        av = (assess or {}).get("views", {}).get(vid, {})
        axes = {}
        for ax in AXES:
            q = r["quant"].get(ax)
            s = av.get(ax, {}).get("score")
            axes[ax] = {"score": composite_score(q, s), "quant": q, "subjective": s,
                        "basis": ("[정량] " + ("IoU body %.3f / dragon %.3f" % (r["iou"]["body"], r["iou"]["dragon"]) if ax == "silhouette"
                                              else "bbox 일치·잘림·채움율 %s" % r["framing"]) if q is not None else "")
                        + ((" | [주관] " + av[ax].get("why", "")) if s is not None else "")}
        have = [(WEIGHTS[k], v["score"]) for k, v in axes.items() if v["score"] is not None]
        tot = round(sum(w * s for w, s in have) / sum(w for w, _ in have), 1) if have else None
        tot_all.append(tot)
        scores["views"][vid] = {"axes": axes, "weighted_total": tot, "iou": r["iou"], "framing": r["framing"],
                                "area_px": r["area_px"], "projection_check_px": r["projection_check_px"],
                                **({"ref_metrics": r["ref_metrics"]} if "ref_metrics" in r else {})}
    vals = [t for t in tot_all if t is not None]
    scores["overall_weighted_total"] = round(sum(vals) / len(vals), 1) if vals else None
    with open(os.path.join(rd, "scores.json"), "w", encoding="utf-8") as f:
        json.dump(scores, f, ensure_ascii=False, indent=1)

    # ---- fixlist.md ----
    L = [f"# Round {a.round} 수정목록", "",
         f"모드: {mode}. 총점(가중 평균) **{scores['overall_weighted_total']}** / 100. "
         "형식: `[ID] [담당] [우선순위] 문제 → 수정 지시 → 기대 효과`. 렌더 시간 대비 효과 큰 순.", "",
         "| 뷰 | " + " | ".join(AXES) + " | 총점 |", "|---|" + "---|" * (len(AXES) + 1)]
    for vid in order:
        ax = scores["views"][vid]["axes"]
        L.append(f"| {vid} | " + " | ".join(str(ax[k]["score"]) for k in AXES) + f" | {scores['views'][vid]['weighted_total']} |")
    L += ["", "IoU(렌더 마스크 vs 설계 투영): " + ", ".join(f"{v} body {results[v]['iou']['body']:.3f}/dragon {results[v]['iou']['dragon']:.3f}" for v in order), ""]
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
        print(f"[compare] {vid}: IoU {results[vid]['iou']}  quant {results[vid]['quant']}  proj_err {results[vid]['projection_check_px']} px")
    print("[compare] overall", scores["overall_weighted_total"], "->", rd)


if __name__ == "__main__":
    main()
