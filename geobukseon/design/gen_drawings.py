"""Generate plan / elevation drawings + flythrough clearance check from design/geobukseon_design.json.
Run: /opt/bvenv/bin/python design/gen_drawings.py   (writes design/plan.png, elevation.png, views_check.png; copies to out/)
"""
import json
import math
import os
import shutil
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Polygon, Rectangle, FancyArrow, Wedge  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DESIGN = os.path.join(HERE, "geobukseon_design.json")
OUT = os.path.join(ROOT, "out")

C_HULL = "#b07a3c"
C_WALL = "#a0522d"
C_ROOF = "#3b2a20"
C_WATER = "#cfe3f0"
C_PIER = "#b9b2a5"
C_SHORE = "#d9d2b8"
C_DIM = "#1f4e9c"
C_TAG = "#666666"


# ----------------------------------------------------------------------------- geometry helpers
def load(path=DESIGN):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def st_arrays(stations, keys):
    s = sorted(stations, key=lambda r: r["y"])
    return [np.array([r[k] for r in s], float) for k in ["y"] + keys]


def interp_station(stations, key, y):
    ys, v = st_arrays(stations, [key])
    return float(np.interp(y, ys, v))


def roof_profile(half, eave, ridge, p, n=60):
    x = np.linspace(-half, half, n)
    z = eave + (ridge - eave) * np.clip(1 - np.abs(x / half) ** p, 0, 1) ** (1.0 / p)
    return x, z


def dragon_local_pts(dh):
    """Head silhouette in local (u forward, v up) coords, origin = head_base."""
    L, H, m = dh["length"], dh["height"], dh["mouth_open"]
    return [(0, -H * 0.45), (L * 0.55, -H * 0.30), (L * 0.98, -m * 0.5 - 0.05), (L * 0.62, -0.02),
            (L * 1.0, m * 0.5), (L * 0.85, H * 0.32), (L * 0.55, H * 0.55), (L * 0.35, H * 0.50),
            (L * 0.2, H * 0.62), (0, H * 0.45)]


def dragon_head_base(dh):
    return dh.get("head_base", dh["base"])


def dragon_polygon_side(dh):
    """Side (YZ) silhouette of dragon head (pitched), placed at head_base."""
    _, by, bz = dragon_head_base(dh)
    a = math.radians(dh["pitch_deg"])
    return [(by + u * math.cos(a) - v * math.sin(a), bz + u * math.sin(a) + v * math.cos(a))
            for u, v in dragon_local_pts(dh)]


def dragon_neck_side(dh):
    """Side (YZ) polygon of the neck from base to head_base (lean forward)."""
    if "neck_height" not in dh:
        return None
    _, y0, z0 = dh["base"]
    _, y1, z1 = dragon_head_base(dh)
    r = dh["neck_radius"]
    return [(y0 - r, z0), (y0 + r, z0), (y1 + r, z1), (y1 - r, z1)]


def dragon_extent(dh):
    pts = dragon_polygon_side(dh)
    ys, zs = [p[0] for p in pts], [p[1] for p in pts]
    top = max(zs) + dh.get("horns", {}).get("length", 0) * 0.8
    return max(ys), top


def stern_ext_curve(d, n=24):
    """(y, z) points of each stern_extension rail (quadratic Bezier)."""
    se = d["hull"].get("stern_extension")
    if not se:
        return None
    p0, c, p1 = np.array(se["start"]), np.array(se["ctrl"]), np.array(se["end"])
    t = np.linspace(0, 1, n)[:, None]
    return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * c + t ** 2 * p1


def sail_rect(m):
    """3D corners of a raised sail (list of 4 xyz), or None."""
    sl = m["sail"]
    if sl.get("state") != "raised":
        return None
    yaw = math.radians(sl.get("yaw_deg", 90))
    # unit vector along sail width: yaw 0 = fore-aft (+Y), 90 = athwartships (+X)
    ux, uy = math.sin(yaw), math.cos(yaw)
    a = -sl.get("mast_offset_frac", 0.5) * sl["w"]
    b = a + sl["w"]
    z0, z1 = sl["bottom_z"], sl["bottom_z"] + sl["h"]
    return [(a * ux, m["y"] + a * uy, z0), (b * ux, m["y"] + b * uy, z0),
            (b * ux, m["y"] + b * uy, z1), (a * ux, m["y"] + a * uy, z1)]


def hull_bbox(d, include_oars=True):
    """Axis-aligned boxes (xmin,xmax,ymin,ymax,zmin,zmax) of obstacles."""
    hs = d["hull"]["stations"]
    roof = d["superstructure"]["roof"]["stations"]
    dh = d["dragon_head"]
    xmax = max(max(r["sheer_half"] for r in hs), max(r["half"] for r in roof))
    if "beam_heads" in d["hull"]:
        xmax = max(xmax, max(r["half"] for r in d["superstructure"]["wall"]["stations"])
                   + d["hull"]["beam_heads"]["protrude_beyond_wall"])
    ymin = min(r["y"] for r in hs)
    dy, dz = dragon_extent(dh)
    ymax = max(max(r["y"] for r in hs), dy)
    zmin = min(r["keel_z"] for r in hs)
    zmax = max(max(r["ridge_z"] for r in roof), dz)
    boxes = {"hull": (-xmax, xmax, ymin, ymax, zmin, zmax)}
    se = stern_ext_curve(d)
    if se is not None:
        xs = d["hull"]["stern_extension"]["x"]
        boxes["stern_ext"] = (min(xs) - 0.3, max(xs) + 0.3, se[:, 0].min(), ymin, se[:, 1].min() - 0.3,
                              se[:, 1].max() + 0.3)
    if include_oars:
        o = d["oars"]
        reach = max(r["half"] for r in d["superstructure"]["wall"]["stations"]) + \
            o["length"] * (1 - o["inboard_fraction"]) * math.cos(math.radians(o["angle_deg"]))
        boxes["oars"] = (-reach, reach, min(o["y"]) - o["blade_width"] - 0.5, max(o["y"]) + o["blade_width"] + 0.5,
                         -0.6, o["port_z"] + 0.2)
    for i, m in enumerate(d["masts"]):
        r = 0.5
        boxes[f"mast{i}"] = (-r, r, m["y"] - r, m["y"] + r, m["base_z"], m["base_z"] + m["height"] + 1.0)
        sr = sail_rect(m)
        if sr:
            a = np.array(sr)
            boxes[f"sail{i}"] = (a[:, 0].min() - 0.3, a[:, 0].max() + 0.3, a[:, 1].min() - 0.3, a[:, 1].max() + 0.3,
                                 a[:, 2].min(), a[:, 2].max())
    p = d["site"].get("pier")
    if p:
        boxes["pier"] = (p["x_min"], p["x_max"], p["y_min"], p["y_max"], p["bottom_z"], p["top_z"])
    s = d["site"].get("shore")
    if s:
        boxes["shore"] = (s["x_min"], s["x_max"], s["y_min"], s["y_max"], -5, s["z"])
    return boxes


def wireframe(d):
    """3D polylines (list of (N,3) arrays, color) of the design, for perspective view checks."""
    L = []
    hs = sorted(d["hull"]["stations"], key=lambda r: r["y"])
    wall = sorted(d["superstructure"]["wall"]["stations"], key=lambda r: r["y"])
    rf = d["superstructure"]["roof"]
    roof = sorted(rf["stations"], key=lambda r: r["y"])
    C_H, C_W, C_R = "#8a5a2b", "#b5651d", "#333333"
    for s in (-1, 1):
        L.append((np.array([[s * r["sheer_half"], r["y"], r["sheer_z"]] for r in hs]), C_H))
        L.append((np.array([[s * r["bottom_half"], r["y"], r["keel_z"]] for r in hs]), C_H))
        L.append((np.array([[s * r["half"], r["y"], r["top_z"]] for r in wall]), C_W))
        L.append((np.array([[s * r["half"], r["y"], interp_station(hs, "sheer_z", r["y"])] for r in wall]), C_W))
        L.append((np.array([[s * r["half"], r["y"], r["eave_z"]] for r in roof]), C_R))
    for r in hs:
        L.append((np.array([[-r["bottom_half"], r["y"], r["keel_z"]], [-r["sheer_half"], r["y"], r["sheer_z"]],
                            [r["sheer_half"], r["y"], r["sheer_z"]], [r["bottom_half"], r["y"], r["keel_z"]],
                            [-r["bottom_half"], r["y"], r["keel_z"]]]), C_H))
    for r in roof:
        x, z = roof_profile(r["half"], r["eave_z"], r["ridge_z"], rf["profile_exponent"], 24)
        L.append((np.c_[x, np.full_like(x, r["y"]), z], C_R))
    L.append((np.array([[0, r["y"], r["ridge_z"]] for r in roof]), C_R))
    for r in (wall[0], wall[-1]):
        sz = interp_station(hs, "sheer_z", r["y"])
        L.append((np.array([[-r["half"], r["y"], sz], [-r["half"], r["y"], r["top_z"]], [r["half"], r["y"], r["top_z"]],
                            [r["half"], r["y"], sz], [-r["half"], r["y"], sz]]), C_W))
    # gun ports (as small squares)
    g = d["gun_ports"]
    for p in g["side"]:
        wh = interp_station(wall, "half", p["y"])
        for s in (-1, 1):
            q = g["size"] / 2
            L.append((np.array([[s * wh, p["y"] - q, p["z"] - q], [s * wh, p["y"] + q, p["z"] - q],
                                [s * wh, p["y"] + q, p["z"] + q], [s * wh, p["y"] - q, p["z"] + q],
                                [s * wh, p["y"] - q, p["z"] - q]]), "black"))
    # oars
    o = d["oars"]
    a = math.radians(o["angle_deg"])
    Lo = o["length"] * (1 - o["inboard_fraction"])
    for y in o["y"]:
        sh = interp_station(hs, "sheer_half", y)
        for s in (-1, 1):
            L.append((np.array([[s * sh, y, o["port_z"]], [s * (sh + Lo * math.cos(a)), y - 0.6, o["port_z"] - Lo * math.sin(a)]]),
                      "#d2a86a"))
    # dragon head
    dh = d["dragon_head"]
    hb = dragon_head_base(dh)
    for xx in (-dh["width"] / 2, dh["width"] / 2):
        L.append((np.array([[xx, y, z] for y, z in dragon_polygon_side(dh) + dragon_polygon_side(dh)[:1]]), "#2e7d4f"))
    if "neck_height" in dh:
        L.append((np.array([dh["base"], hb]), "#2e7d4f"))
    # masts & sails
    for m in d["masts"]:
        L.append((np.array([[0, m["y"], m["base_z"]], [0, m["y"], m["base_z"] + m["height"]]]), "#8b5a2b"))
        sr = sail_rect(m)
        if sr:
            L.append((np.array(sr + sr[:1]), "#c8a46e"))
            n = m["sail"].get("battens", 0)
            for k in range(1, n):
                f = k / n
                p0 = np.array(sr[0]) + (np.array(sr[3]) - np.array(sr[0])) * f
                p1 = np.array(sr[1]) + (np.array(sr[2]) - np.array(sr[1])) * f
                L.append((np.array([p0, p1]), "#a07a40"))
    # stern extension
    se = stern_ext_curve(d)
    if se is not None:
        for xx in d["hull"]["stern_extension"]["x"]:
            L.append((np.c_[np.full(len(se), xx), se[:, 0], se[:, 1]], C_H))
    # rudder
    r = d["rudder"]
    L.append((np.array([[0, r["y"], r["top_z"]], [0, r["y"], r["top_z"] - r["depth"]],
                        [0, r["y"] - r["width"], r["top_z"] - r["depth"]], [0, r["y"] - r["width"], r["top_z"] - r["depth"] * 0.55],
                        [0, r["y"], r["top_z"] - r["depth"] * 0.55]]), "#4a3420"))
    return L


def site_wireframe(d):
    L = []
    p = d["site"].get("pier")
    if p:
        for z in (p["top_z"], 0.0):
            L.append((np.array([[p["x_max"], p["y_min"], z], [p["x_max"], p["y_max"], z]]), "#777777"))
        for y in np.arange(p["y_min"], p["y_max"] + 0.1, 5):
            L.append((np.array([[p["x_max"], y, 0], [p["x_max"], y, p["top_z"]], [p["x_min"], y, p["top_z"]]]), "#999999"))
    # water grid
    for v in np.arange(-60, 61, 10):
        L.append((np.array([[v, -60, 0], [v, 60, 0]]), "#9ec5e0"))
        L.append((np.array([[-60, v, 0], [60, v, 0]]), "#9ec5e0"))
    return L


def project(view, pts, aspect):
    """Pinhole projection, sensor width fits image width. Returns (u,v) in [0,1] (v from top) and depth."""
    c = np.array(view["cam"], float)
    f = np.array(view["look_at"], float) - c
    f /= np.linalg.norm(f)
    r = np.cross(f, [0, 0, 1.0])
    r /= np.linalg.norm(r)
    up = np.cross(r, f)
    roll = math.radians(view.get("roll_deg", 0))
    r, up = r * math.cos(roll) + up * math.sin(roll), up * math.cos(roll) - r * math.sin(roll)
    dpt = pts - c
    X, Y, Z = dpt @ r, dpt @ up, dpt @ f
    k = view["lens_mm"] / view.get("sensor_mm", 36)
    sx, sy = view.get("shift_x", 0.0), view.get("shift_y", 0.0)
    big = max(1.0, 1.0 / aspect)  # blender shift is in units of the larger image dimension (width = 1)
    u = 0.5 + k * X / Z - sx * big
    v = 0.5 - (k * Y / Z) * aspect + sy * max(1.0, aspect)
    return u, v, Z


# ----------------------------------------------------------------------------- flythrough
def interp_flythrough(keys, t):
    """Catmull-Rom (non-uniform t, finite-difference tangents) on cam and look_at; linear lens."""
    ts = np.array([k["t"] for k in keys], float)
    t = float(np.clip(t, ts[0], ts[-1]))
    i = int(np.clip(np.searchsorted(ts, t, side="right") - 1, 0, len(ts) - 2))
    t0, t1 = ts[i], ts[i + 1]
    s = (t - t0) / (t1 - t0)

    def tangent(arr, j):
        if j == 0:
            return (arr[1] - arr[0]) / (ts[1] - ts[0])
        if j == len(arr) - 1:
            return (arr[-1] - arr[-2]) / (ts[-1] - ts[-2])
        return (arr[j + 1] - arr[j - 1]) / (ts[j + 1] - ts[j - 1])

    res = {}
    for key in ("cam", "look_at"):
        arr = np.array([k[key] for k in keys], float)
        p0, p1 = arr[i], arr[i + 1]
        m0, m1 = tangent(arr, i) * (t1 - t0), tangent(arr, i + 1) * (t1 - t0)
        h00 = 2 * s ** 3 - 3 * s ** 2 + 1
        h10 = s ** 3 - 2 * s ** 2 + s
        h01 = -2 * s ** 3 + 3 * s ** 2
        h11 = s ** 3 - s ** 2
        res[key] = h00 * p0 + h10 * m0 + h01 * p1 + h11 * m1
    lens = [k["lens_mm"] for k in keys]
    res["lens_mm"] = lens[i] + (lens[i + 1] - lens[i]) * s
    return res


def box_dist(p, b):
    dx = max(b[0] - p[0], 0, p[0] - b[1])
    dy = max(b[2] - p[1], 0, p[1] - b[3])
    dz = max(b[4] - p[2], 0, p[2] - b[5])
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def check_cameras(d, margin=2.0, verbose=True):
    """Every flythrough frame + every view camera must be >= margin from all obstacle boxes
    Pier/shore: view cameras may stand on them (eye >= 1.4 m above top); flythrough frames over them
    need >= margin above the top; beside them >= 0.5 m. All cameras must be >= 0.8 m above water."""
    boxes = hull_bbox(d)
    fl = d["flythrough"]
    n = int(fl["fps"] * fl["seconds"])
    problems = []
    min_seen = {}

    def test(label, p, standing=False):
        if p[2] < 0.8:
            problems.append(f"{label}: z={p[2]:.2f} too close to water")
        for name, b in boxes.items():
            if name in ("pier", "shore"):
                inside_xy = b[0] <= p[0] <= b[1] and b[2] <= p[1] <= b[3]
                dist = (p[2] - b[5]) if inside_xy else box_dist(p, b)
                need = (1.4 if standing else margin) if inside_xy else 0.5
            else:
                dist, need = box_dist(p, b), margin
            min_seen[name] = min(min_seen.get(name, 1e9), dist)
            if dist < need:
                problems.append(f"{label}: {dist:.2f} m from {name} (< {need})")

    for f in range(n + 1):
        test(f"frame {f}", interp_flythrough(fl["keys"], f / fl["fps"])["cam"])
    for v in d["views"]:
        test(f"view {v['id']}", np.array(v["cam"], float), standing=True)
    if verbose:
        print("[check] min clearance per obstacle: " + ", ".join(f"{k}={v:.2f}" for k, v in min_seen.items()))
        if problems:
            print(f"[check] FAIL ({len(problems)}):")
            for p in problems[:30]:
                print("   ", p)
        else:
            print(f"[check] OK: {n + 1} flythrough frames + {len(d['views'])} views clear (margin {margin} m)")
    return problems


# ----------------------------------------------------------------------------- drawing helpers
def dim_line(ax, p0, p1, text, off=(0, 0), color=C_DIM, fs=8, rot=0):
    ax.annotate("", xy=p1, xytext=p0, arrowprops=dict(arrowstyle="<->", color=color, lw=0.9))
    mx, my = (p0[0] + p1[0]) / 2 + off[0], (p0[1] + p1[1]) / 2 + off[1]
    ax.text(mx, my, text, color=color, fontsize=fs, ha="center", va="center", rotation=rot,
            bbox=dict(fc="white", ec="none", pad=0.6, alpha=0.85))


def scale_bar(ax, x, y, length, label_every):
    for i in range(int(length / label_every)):
        ax.add_patch(Rectangle((x + i * label_every, y), label_every, length * 0.025,
                               fc="black" if i % 2 == 0 else "white", ec="black", lw=0.6))
    for i in range(int(length / label_every) + 1):
        ax.text(x + i * label_every, y - length * 0.03, f"{i * label_every:g}", ha="center", va="top", fontsize=7)
    ax.text(x + length + length * 0.03, y, "m", fontsize=7, va="bottom")


def north_arrow(ax, x, y, size):
    ax.add_patch(FancyArrow(x, y, 0, size, width=size * 0.12, head_width=size * 0.35, head_length=size * 0.35,
                            color="black"))
    ax.text(x, y + size * 1.45, "N", ha="center", va="bottom", fontsize=11, weight="bold")


def plan_outline(stations, half_key):
    ys, h = st_arrays(stations, [half_key])
    return np.concatenate([h, -h[::-1]]), np.concatenate([ys, ys[::-1]])


# ----------------------------------------------------------------------------- plan
def draw_plan(d, path):
    fig, ax = plt.subplots(figsize=(13, 13), dpi=110)
    site = d["site"]
    W = 60
    ax.add_patch(Rectangle((-W, -W), 2 * W, 2 * W, fc=C_WATER, ec="none", zorder=0))
    sh = site.get("shore")
    if sh:
        ax.add_patch(Rectangle((max(sh["x_min"], -W), max(sh["y_min"], -W)), sh["x_max"] - max(sh["x_min"], -W),
                               min(sh["y_max"], W) - max(sh["y_min"], -W), fc=C_SHORE, ec="#8a835f", lw=0.8, zorder=1))
        ax.text(-41, 45, "shore (flat ground, z=%.1f) [가정]".replace(" [가정]", " [assumed]") % sh["z"], fontsize=8,
                color="#5a5236")
    p = site.get("pier")
    if p:
        ax.add_patch(Rectangle((p["x_min"], p["y_min"]), p["x_max"] - p["x_min"], p["y_max"] - p["y_min"],
                               fc=C_PIER, ec="#55504a", lw=1.2, hatch="..", zorder=2))
        ax.text((p["x_min"] + p["x_max"]) / 2, p["y_max"] - 3, "stone quay\ntop z=%.1f\n[assumed]" % p["top_z"],
                ha="center", va="top", fontsize=8, zorder=3)
        for b in p.get("bollards", []):
            ax.add_patch(plt.Circle((b["x"], b["y"]), 0.35, fc="#333", zorder=4))
        for ml in p.get("mooring_lines", []):
            b = p["bollards"][ml["from_bollard"]]
            ax.plot([b["x"], ml["to"][0]], [b["y"], ml["to"][1]], color="#6b4f2a", lw=0.8, zorder=4)

    # hull, wall, roof outlines
    hx, hy = plan_outline(d["hull"]["stations"], "sheer_half")
    ax.add_patch(Polygon(np.c_[hx, hy], closed=True, fc=C_HULL, ec="black", lw=1, alpha=0.9, zorder=5,
                         label="hull sheer"))
    bx, by = plan_outline(d["hull"]["stations"], "bottom_half")
    ax.add_patch(Polygon(np.c_[bx, by], closed=True, fc="none", ec="#e0c090", lw=0.8, ls="--", zorder=6))
    rx, ry = plan_outline(d["superstructure"]["roof"]["stations"], "half")
    ax.add_patch(Polygon(np.c_[rx, ry], closed=True, fc=C_ROOF, ec="black", lw=1, zorder=7))
    rf = d["superstructure"]["roof"]
    # cross walkway
    ylo, yhi = min(r["y"] for r in rf["stations"]), max(r["y"] for r in rf["stations"])
    ax.add_patch(Rectangle((-rf["cross_walkway_width"] / 2, ylo), rf["cross_walkway_width"], yhi - ylo,
                           fc="#8b6b4a", ec="none", zorder=8))
    hw = interp_station(rf["stations"], "half", rf["cross_walkway_y"])
    ax.add_patch(Rectangle((-hw, rf["cross_walkway_y"] - rf["cross_walkway_width"] / 2), 2 * hw,
                           rf["cross_walkway_width"], fc="#8b6b4a", ec="none", zorder=8))
    # spikes (sparse dots for impression)
    sp = rf["spikes"]["spacing"] * 3
    for yy in np.arange(ylo + 0.4, yhi - 0.2, sp):
        h = interp_station(rf["stations"], "half", yy) - 0.25
        for xx in np.arange(-h, h, sp):
            if abs(xx) < rf["spikes"]["exclude_ridge_lane"] / 2 + 0.1 or \
                    abs(yy - rf["cross_walkway_y"]) < rf["cross_walkway_width"] / 2 + 0.1:
                continue
            ax.plot(xx, yy, ".", ms=1.2, color="#c9b9a0", zorder=9)
    # oars
    o = d["oars"]
    out_len = o["length"] * (1 - o["inboard_fraction"]) * math.cos(math.radians(o["angle_deg"]))
    for yy in o["y"]:
        w = interp_station(d["hull"]["stations"], "sheer_half", yy)
        for s in (-1, 1):
            ax.plot([s * w, s * (w + out_len)], [yy, yy - 0.6], color="#d2a86a", lw=1.6, zorder=6)
    # beam heads
    bh = d["hull"].get("beam_heads")
    if bh:
        for yy in bh["y"]:
            wh = interp_station(d["superstructure"]["wall"]["stations"], "half", yy) + bh["protrude_beyond_wall"]
            for s in (-1, 1):
                x0 = (wh - 0.35) if s > 0 else -wh
                ax.add_patch(Rectangle((x0, yy - bh["section"][1] / 2), 0.35, bh["section"][1], fc="#6b4520",
                                       zorder=6.5))
    # stern extension
    se = stern_ext_curve(d)
    if se is not None:
        for xx in d["hull"]["stern_extension"]["x"]:
            ax.plot([xx, xx], [se[0, 0], se[-1, 0]], color=C_HULL, lw=3, zorder=6, solid_capstyle="butt")
        ax.annotate("stern extension rails", (d["hull"]["stern_extension"]["x"][1], se[-1, 0]), (6, -20), fontsize=7,
                    arrowprops=dict(arrowstyle="->", lw=0.6))
    # dragon head
    dh = d["dragon_head"]
    hb = dragon_head_base(dh)
    L = dh["length"] * math.cos(math.radians(dh["pitch_deg"]))
    ax.add_patch(Polygon([(-dh["width"] / 2, hb[1]), (dh["width"] / 2, hb[1]),
                          (dh["width"] * 0.3, hb[1] + L), (-dh["width"] * 0.3, hb[1] + L)],
                         fc="#2e7d4f", ec="black", lw=0.8, zorder=10))
    if "neck_radius" in dh:
        ax.add_patch(plt.Circle((0, dh["base"][1]), dh["neck_radius"], fc="#2e7d4f", ec="black", zorder=10))
    ax.annotate("dragon head on neck (yongdu)", (0, hb[1] + L), (6, 17), fontsize=8,
                arrowprops=dict(arrowstyle="->", lw=0.7), zorder=11)
    for m in d["masts"]:
        sr = sail_rect(m)
        if sr:
            ax.plot([sr[0][0], sr[1][0]], [sr[0][1], sr[1][1]], color="#c8a46e", lw=4, alpha=0.85, zorder=11,
                    solid_capstyle="butt")
            ax.text(sr[1][0] + 0.3, sr[1][1], "sail (raised, yaw %d°)" % m["sail"]["yaw_deg"], fontsize=6.5, zorder=11)
        ax.add_patch(plt.Circle((0, m["y"]), m["diameter"] * 1.5, fc="#e8c48a", ec="black", zorder=11))
    ax.text(5.2, -12.6, "rudder", fontsize=7)
    ax.add_patch(Rectangle((-0.1, d["rudder"]["y"] - 0.7), 0.2, 1.4, fc="black", zorder=11))

    # dims
    ys = [r["y"] for r in d["hull"]["stations"]]
    dim_line(ax, (7.5, min(ys)), (7.5, max(ys)), "LOA %.1f %s (S1)" % (d["principal"]["loa"],
             d["principal"]["loa_tag"].replace("[확정]", "[confirmed]")), off=(1.8, 0), rot=90)
    dim_line(ax, (-d["principal"]["beam"] / 2, -15.5), (d["principal"]["beam"] / 2, -15.5),
             "beam %.2f [confirmed] (S1)" % d["principal"]["beam"], off=(0, -1.1))

    # flythrough path
    fl = d["flythrough"]
    tt = np.linspace(0, fl["seconds"], 400)
    pts = np.array([interp_flythrough(fl["keys"], t)["cam"] for t in tt])
    ax.plot(pts[:, 0], pts[:, 1], color="#d62728", lw=1.4, ls="-", zorder=12, label="flythrough path")
    for k in fl["keys"]:
        ax.plot(k["cam"][0], k["cam"][1], "o", color="#d62728", ms=4, zorder=13)
        ax.text(k["cam"][0] + 0.6, k["cam"][1] + 0.6, "t=%gs\nz=%.1f" % (k["t"], k["cam"][2]), fontsize=6.5,
                color="#a01010", zorder=13)
    for t in np.arange(0, fl["seconds"] + 0.01, 4):
        r = interp_flythrough(fl["keys"], t)
        c, la = r["cam"], r["look_at"]
        v = (la - c)[:2]
        v = v / (np.linalg.norm(v) + 1e-9) * 2.5
        ax.add_patch(FancyArrow(c[0], c[1], v[0], v[1], width=0.08, head_width=0.6, color="#d62728", alpha=0.6,
                                zorder=12))
    # views
    cols = {"bow34": "#9467bd", "side": "#2ca02c", "stern34": "#ff7f0e", "aerial": "#17becf"}
    for v in d["views"]:
        c, la = np.array(v["cam"]), np.array(v["look_at"])
        col = cols.get(v["id"], "k")
        hfov = 2 * math.degrees(math.atan(v.get("sensor_mm", 36) / 2 / v["lens_mm"]))
        head = math.degrees(math.atan2(la[1] - c[1], la[0] - c[0]))
        dist = np.linalg.norm((la - c)[:2])
        ax.add_patch(Wedge((c[0], c[1]), dist * 1.15, head - hfov / 2, head + hfov / 2, fc=col, alpha=0.10,
                           ec=col, lw=0.6, zorder=3))
        ax.plot([c[0], la[0]], [c[1], la[1]], color=col, lw=1.0, ls="--", zorder=14)
        ax.plot(c[0], c[1], "s", color=col, ms=8, mec="black", zorder=15)
        ax.text(c[0] + 0.8, c[1] - 1.8, "%s\n%dmm z=%.1f" % (v["id"], v["lens_mm"], c[2]), fontsize=8, color=col,
                weight="bold", zorder=15, bbox=dict(fc="white", ec="none", alpha=0.7, pad=0.5))
    # sun
    az = math.radians(d["sun"]["azimuth_deg"])
    sx, sy = 40 * math.sin(az), 40 * math.cos(az)
    ax.plot(sx, sy, "o", ms=16, color="#f4b400", mec="#c77800", zorder=15)
    ax.annotate("", xy=(0.45 * sx, 0.45 * sy), xytext=(0.9 * sx, 0.9 * sy),
                arrowprops=dict(arrowstyle="->", color="#c77800", lw=2), zorder=15)
    ax.text(sx, sy - 3.5, "sun az %d° el %d°" % (d["sun"]["azimuth_deg"], d["sun"]["elevation_deg"]),
            ha="center", fontsize=8, color="#8a5200", zorder=15)

    north_arrow(ax, 50, 42, 5)
    scale_bar(ax, 25, -55, 20, 5)
    ax.set_xlim(-W, W)
    ax.set_ylim(-W, W)
    ax.set_aspect("equal")
    ax.set_xlabel("X east (m)")
    ax.set_ylabel("Y north (m)")
    ax.grid(True, lw=0.3, alpha=0.5)
    ax.set_title("Geobukseon - site plan (origin: midship/centerline/waterline, bow = +Y north)\n"
                 "hull (brown), roof shell (dark), cross walkway, oars, cameras (squares) + FOV, flythrough (red)",
                 fontsize=10)
    ax.legend(loc="lower left", fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)

    # inset-zoomed second plan? keep single file; return path
    return path


# ----------------------------------------------------------------------------- elevation
def draw_elevation(d, path):
    fig = plt.figure(figsize=(18, 11), dpi=100)
    gs = fig.add_gridspec(2, 3, height_ratios=[1.15, 1], width_ratios=[2.2, 1, 1])
    ax = fig.add_subplot(gs[0, :])
    axf = fig.add_subplot(gs[1, 0])
    axm = fig.add_subplot(gs[1, 1])
    axb = fig.add_subplot(gs[1, 2])

    hs = d["hull"]["stations"]
    ys, kz, sz = st_arrays(hs, ["keel_z", "sheer_z"])
    wys, wtop = st_arrays(d["superstructure"]["wall"]["stations"], ["top_z"])
    rys, reave, rridge = st_arrays(d["superstructure"]["roof"]["stations"], ["eave_z", "ridge_z"])
    pr = d["principal"]

    # ------------- side elevation (looking from west / port side: +Y to the right)
    ax.axhspan(-2.5, 0, color=C_WATER, zorder=0)
    ax.axhline(0, color="#1f77b4", lw=1)
    ax.text(-15.5, 0.08, "WL z=0", color="#1f77b4", fontsize=8)
    ax.fill(np.r_[ys, ys[::-1]], np.r_[kz, sz[::-1]], fc=C_HULL, ec="black", lw=1, zorder=2)
    # waterline band
    band = d["hull"]["waterline_stain_band"]
    ax.fill_between(ys, np.maximum(kz, band[0]), np.full_like(ys, band[1]), where=kz < band[1], color="#4d6b3c",
                    alpha=0.6, zorder=3)
    swall_lo = np.interp(wys, ys, sz)
    ax.fill(np.r_[wys, wys[::-1]], np.r_[swall_lo, wtop[::-1]], fc=C_WALL, ec="black", lw=0.9, zorder=3)
    ax.fill(np.r_[rys, rys[::-1]], np.r_[reave, rridge[::-1]], fc=C_ROOF, ec="black", lw=1, zorder=4)
    # roof spikes impression
    for yy in np.arange(rys[0] + 0.3, rys[-1], 0.7):
        e, r = np.interp(yy, rys, reave), np.interp(yy, rys, rridge)
        for f in (0.35, 0.7, 0.95):
            z = e + (r - e) * f
            ax.plot([yy, yy], [z, z + 0.12], color="#bbb", lw=0.5, zorder=5)
    # wall panel pattern: roundels at gun ports, iron diamonds between, iron bands
    wp = d["superstructure"]["wall"].get("panel_pattern")
    gys = sorted(p["y"] for p in d["gun_ports"]["side"])
    if wp:
        for i, gy in enumerate(gys):
            lo, hi = np.interp(gy, ys, sz), np.interp(gy, wys, wtop)
            dia = min(wp["roundel_diameter_max"], (hi - lo) * wp["roundel_diameter_frac"])
            ax.add_patch(plt.Circle((gy, (lo + hi) / 2), dia / 2, fc="#c98a4a", ec="#2a1a10",
                                    lw=wp["roundel_ring_width"] * 20, zorder=4.5))
            if i < len(gys) - 1:
                my = (gy + gys[i + 1]) / 2
                lo2, hi2 = np.interp(my, ys, sz), np.interp(my, wys, wtop)
                hh = (hi2 - lo2) * wp["diamond_between"]["h_frac"] / 2
                ww = wp["diamond_between"]["w"] / 2
                mz = (lo2 + hi2) / 2
                ax.add_patch(Polygon([(my - ww, mz), (my, mz + hh), (my + ww, mz), (my, mz - hh)], fc="#1b1b1b",
                                     zorder=4.5))
        ax.plot(wys, wtop - 0.04, color="#1b1b1b", lw=2, zorder=4.6)
        ax.plot(wys, np.interp(wys, ys, sz) + 0.04, color="#1b1b1b", lw=2, zorder=4.6)
    # beam heads
    bh = d["hull"].get("beam_heads")
    if bh:
        for yy in bh["y"]:
            zc = np.interp(yy, ys, sz) - bh["z_below_sheer"]
            ax.add_patch(Rectangle((yy - bh["section"][0] / 2, zc - bh["section"][1] / 2), bh["section"][0],
                                   bh["section"][1], fc="#6b4520", ec="black", lw=0.4, zorder=6))
    # stern extension rails
    se = stern_ext_curve(d)
    if se is not None:
        ax.plot(se[:, 0], se[:, 1], color=C_HULL, lw=5, zorder=2.5, solid_capstyle="butt")
        ax.plot(se[:, 0], se[:, 1], color="black", lw=0.5, zorder=2.6)
        for t in d["hull"]["stern_extension"]["crossbars_t"]:
            k = int(round(t * (len(se) - 1)))
            ax.plot(se[k, 0], se[k, 1], "s", color="#6b4520", ms=4, zorder=2.7)
        ax.annotate("stern extension rails (R2,R3)", (se[-1, 0], se[-1, 1]), (-15.5, 7.5), fontsize=8,
                    arrowprops=dict(arrowstyle="->", lw=0.7))
    # gun ports & oar ports
    g = d["gun_ports"]
    for p in g["side"]:
        ax.add_patch(Rectangle((p["y"] - g["size"] / 2, p["z"] - g["size"] / 2), g["size"], g["size"], fc="black",
                               zorder=6))
    o = d["oars"]
    a = math.radians(o["angle_deg"])
    for yy in o["y"]:
        ax.add_patch(plt.Circle((yy, o["port_z"]), 0.09, fc="black", zorder=6))
        L = o["length"] * (1 - o["inboard_fraction"])
        # projected on side view: oar goes outward (toward viewer) and down, slight aft sweep
        ax.plot([yy, yy - 0.6], [o["port_z"], o["port_z"] - L * math.sin(a)], color="#d2a86a", lw=2.2, zorder=7)
    # dragon head (+neck)
    nk = dragon_neck_side(d["dragon_head"])
    if nk:
        ax.add_patch(Polygon(nk, closed=True, fc="#2e7d4f", ec="black", zorder=7.9))
    ax.add_patch(Polygon(dragon_polygon_side(d["dragon_head"]), closed=True, fc="#2e7d4f", ec="black", zorder=8))
    # ghost face
    gf = d["ghost_face"]
    ax.add_patch(Rectangle((gf["center"][1] - 0.15, gf["center"][2] - gf["height"] / 2), 0.3, gf["height"],
                           angle=0, fc="#c0392b", ec="black", zorder=8))
    ax.annotate("ghost face (gwimyeon)", (gf["center"][1], gf["center"][2]), (13.5, -1.2), fontsize=8,
                arrowprops=dict(arrowstyle="->", lw=0.7))
    _hb = dragon_head_base(d["dragon_head"])
    ax.annotate("dragon head on neck (yongdu)", (_hb[1] + 0.8, _hb[2] + 0.3), (12.0, 8.5), fontsize=8,
                arrowprops=dict(arrowstyle="->", lw=0.7))
    # masts
    for m in d["masts"]:
        ax.add_patch(Rectangle((m["y"] - m["diameter"] / 2, m["base_z"]), m["diameter"], m["height"], fc="#c79a5b",
                               ec="black", lw=0.6, zorder=3.5))
        if m["sail"]["state"] == "furled":
            top = m["base_z"] + m["height"]
            ax.add_patch(Rectangle((m["y"] - m["sail"]["w"] / 2, top - 1.2), m["sail"]["w"], 0.35, fc="#e8dcc0",
                                   ec="black", lw=0.5, zorder=3.6))
        sr = sail_rect(m)
        if sr:  # side view: project sail on YZ plane
            ys_ = [p_[1] for p_ in sr]
            y0, y1 = min(ys_), max(ys_)
            if y1 - y0 < 0.3:
                y0, y1 = m["y"] - 0.15, m["y"] + 0.15
            z0, z1 = sr[0][2], sr[2][2]
            ax.add_patch(Rectangle((y0, z0), y1 - y0, z1 - z0, fc="#c8a46e", ec="#6b4a20", lw=0.8, alpha=0.85,
                                   zorder=3.4))
            n = m["sail"].get("battens", 0)
            for k in range(n + 1):
                zz = z0 + (z1 - z0) * k / n
                ax.plot([y0, y1], [zz, zz], color="#6b4a20", lw=0.8, zorder=3.45)
    for f in d["flags"]:
        x, y, z = f["pos"]
        if x <= 0:
            ax.add_patch(Rectangle((y, z - f["size"][1]), f["size"][0] * 0.9, f["size"][1], fc=f["color"], ec="k",
                                   lw=0.4, zorder=3.7))
            if "pole_base_z" in f:
                ax.plot([y, y], [f["pole_base_z"], z + 0.2], color="#5a3b1d", lw=1.2, zorder=3.7)
    # rudder
    r = d["rudder"]
    ax.add_patch(Rectangle((r["y"] - r["width"], r["top_z"] - r["depth"]), r["width"], r["depth"] * 0.45,
                           fc="#4a3420", ec="black", zorder=1.5))
    ax.plot([r["y"], r["y"]], [r["top_z"] - r["depth"], r["top_z"]], color="#4a3420", lw=3, zorder=1.5)

    # dims
    zk = kz.min()
    zr = rridge.max()
    dim_line(ax, (ys.min(), -2.75), (ys.max(), -2.75), "LOA %.1f [confirmed] (S1)" % pr["loa"])
    dim_line(ax, (-14.6, zk), (-14.6, zr), "H %.2f [confirmed] (S1)" % pr["height_keel_to_roof"], off=(-0.45, 0), fs=7, rot=90)
    dim_line(ax, (-13.2, zk), (-13.2, 0), "draft %.1f\n[assumed]" % pr["draft"], off=(0.9, -0.2), fs=7)
    bl = pr["bottom_length"]
    yb0, yb1 = d["hull"]["stern_transom"]["y_bottom"], d["hull"]["bow_transom"]["y_bottom"]
    dim_line(ax, (yb0, zk - 0.35), (yb1, zk - 0.35), "bottom %.1f [est.] (S3: 64.8 cheok)" % (yb1 - yb0), fs=7)
    ax.text(0, 14.8, "", fontsize=1)
    ax.set_xlim(-17.5, 17)
    ax.set_ylim(-3.2, 16.5)
    ax.set_aspect("equal")
    ax.set_xlabel("Y (m)  <- stern | bow (north) ->")
    ax.set_ylabel("Z (m)")
    ax.grid(True, lw=0.3, alpha=0.5)
    ax.set_title("SIDE ELEVATION (port side, viewed from west).  ridge max z=%.2f at y=%.1f; tags: S-IDs in "
                 "design/sources.md" % (zr, rys[np.argmax(rridge)]), fontsize=10)

    # ------------- sections
    rf = d["superstructure"]["roof"]
    pexp = rf["profile_exponent"]

    def section(axs, y, title, lw=1.0, fill=True, alpha=1.0):
        bh = interp_station(hs, "bottom_half", y)
        shh = interp_station(hs, "sheer_half", y)
        k = interp_station(hs, "keel_z", y)
        s = interp_station(hs, "sheer_z", y)
        wh = interp_station(d["superstructure"]["wall"]["stations"], "half", y)
        wt = interp_station(d["superstructure"]["wall"]["stations"], "top_z", y)
        rh = interp_station(rf["stations"], "half", y)
        re_ = interp_station(rf["stations"], "eave_z", y)
        rr = interp_station(rf["stations"], "ridge_z", y)
        hull = [(-bh, k), (bh, k), (shh, s), (-shh, s)]
        wall = [(-wh, s), (wh, s), (wh, wt), (-wh, wt)]
        rx, rz = roof_profile(rh, re_, rr, pexp)
        kw = dict(lw=lw, alpha=alpha)
        axs.add_patch(Polygon(hull, closed=True, fc=C_HULL if fill else "none", ec="black", **kw))
        axs.add_patch(Polygon(wall, closed=True, fc=C_WALL if fill else "none", ec="black", **kw))
        axs.fill_between(rx, re_ - 0.0, rz, color=C_ROOF if fill else "none", ec="black", lw=lw, alpha=alpha)
        bmh = d["hull"].get("beam_heads")
        if bmh and fill:
            zc = s - bmh["z_below_sheer"]
            q = bmh["section"][1] / 2
            axs.add_patch(Rectangle((-wh - bmh["protrude_beyond_wall"], zc - q),
                                    2 * (wh + bmh["protrude_beyond_wall"]), 2 * q, fc="#6b4520", ec="black",
                                    lw=0.4, zorder=0.9))
        return dict(bh=bh, shh=shh, k=k, s=s, wh=wh, wt=wt, rh=rh, re=re_, rr=rr)

    def prep(axs, title):
        axs.axhspan(-2.5, 0, color=C_WATER, zorder=0)
        axs.axhline(0, color="#1f77b4", lw=1)
        axs.set_aspect("equal")
        axs.set_xlim(-6.5, 6.5)
        axs.set_ylim(-2.4, 7.2)
        axs.grid(True, lw=0.3, alpha=0.5)
        axs.set_title(title, fontsize=10)
        axs.set_xlabel("X (m)  <- port (west) | starboard (east) ->")

    # front view: envelope of all stations, then bow details
    prep(axf, "FRONT VIEW (from north, bow)")
    for st in sorted(d["superstructure"]["roof"]["stations"], key=lambda r: r["y"]):
        section(axf, st["y"], "", lw=0.4, fill=False, alpha=0.5)
    sec = section(axf, 4.0, "")
    # bow transom face
    bt = d["hull"]["bow_transom"]
    axf.add_patch(Polygon([(-bt["half_bottom"], bt["z_bottom"]), (bt["half_bottom"], bt["z_bottom"]),
                           (bt["half_top"], bt["z_top"]), (-bt["half_top"], bt["z_top"])], closed=True,
                          fc="#8a6038", ec="black", lw=1))
    gfc = d["ghost_face"]
    axf.add_patch(Rectangle((-gfc["width"] / 2, gfc["center"][2] - gfc["height"] / 2), gfc["width"], gfc["height"],
                            fc="#c0392b", ec="black"))
    axf.text(0, gfc["center"][2], "ghost\nface", ha="center", va="center", fontsize=7, color="white")
    for p in d["gun_ports"]["bow"]:
        axf.add_patch(Rectangle((p["x"] - 0.16, p["z"] - 0.16), 0.32, 0.32, fc="black"))
    dh = d["dragon_head"]
    hb = dragon_head_base(dh)
    tipz = hb[2] + dh["length"] * math.sin(math.radians(dh["pitch_deg"]))
    if "neck_radius" in dh:
        axf.add_patch(Rectangle((-dh["neck_radius"], dh["base"][2]), 2 * dh["neck_radius"], hb[2] - dh["base"][2],
                                fc="#2e7d4f", ec="black", zorder=3))
    hz = dh.get("horns", {}).get("length", 0)
    for sgn in (-1, 1):
        axf.plot([sgn * dh["width"] * 0.3, sgn * (dh["width"] * 0.3 + hz * 0.6)],
                 [tipz + dh["height"] * 0.5, tipz + dh["height"] * 0.5 + hz * 0.8], color="#2e7d4f", lw=2, zorder=3)
    axf.add_patch(Polygon([(-dh["width"] / 2, hb[2] - dh["height"] * 0.45),
                           (dh["width"] / 2, hb[2] - dh["height"] * 0.45),
                           (dh["width"] / 2, tipz + dh["height"] * 0.5), (0, tipz + dh["height"] * 0.65),
                           (-dh["width"] / 2, tipz + dh["height"] * 0.5)], closed=True, fc="#2e7d4f", ec="black",
                          zorder=3))
    oa = math.radians(d["oars"]["angle_deg"])
    L = d["oars"]["length"] * (1 - d["oars"]["inboard_fraction"])
    for s in (-1, 1):
        axf.plot([s * sec["shh"], s * (sec["shh"] + L * math.cos(oa))],
                 [d["oars"]["port_z"], d["oars"]["port_z"] - L * math.sin(oa)], color="#d2a86a", lw=2)
    for m in d["masts"]:
        axf.add_patch(Rectangle((-m["diameter"] / 2, m["base_z"]), m["diameter"], 7.2 - m["base_z"], fc="#c79a5b",
                                ec="black", lw=0.5, zorder=0.5))
        sr = sail_rect(m)
        if sr:
            xs_ = [p_[0] for p_ in sr]
            axf.add_patch(Rectangle((min(xs_), sr[0][2]), max(xs_) - min(xs_), 7.2 - sr[0][2], fc="#c8a46e",
                                    ec="#6b4a20", lw=0.6, alpha=0.5, zorder=0.4))
    axf.text(-6.3, 6.8, "sails above z=%.1f cropped (raised batten sails)" % min(m["sail"].get("bottom_z", 99)
             for m in d["masts"]), fontsize=7, color=C_TAG)
    dim_line(axf, (-pr["beam"] / 2, 6.0), (pr["beam"] / 2, 6.0), "beam %.2f [confirmed]" % pr["beam"], off=(0, 0.45),
             fs=7)

    # midship section
    prep(axm, "MIDSHIP SECTION  y=0")
    sec0 = section(axm, 0.0, "")
    dim_line(axm, (-sec0["wh"], -0.5 + sec0["k"] + 0.1), (sec0["wh"], -0.5 + sec0["k"] + 0.1),
             "wall %.2f [conf.]" % (2 * sec0["wh"]), off=(0, -0.4), fs=7)
    dim_line(axm, (-sec0["bh"], sec0["k"] + 0.35), (sec0["bh"], sec0["k"] + 0.35),
             "bottom %.2f [est.]" % (2 * sec0["bh"]), off=(0, 0.3), fs=7)
    dim_line(axm, (5.6, sec0["k"]), (5.6, sec0["rr"]), "%.2f" % (sec0["rr"] - sec0["k"]), off=(0.5, 0), fs=7, rot=90)
    dim_line(axm, (-5.4, 0), (-5.4, sec0["s"]), "fb %.2f" % sec0["s"], off=(-0.6, 0), fs=7, rot=90)
    axm.text(-6.3, 6.6, "roof: superellipse p=%.1f [assumed]\nwall top %.2f, ridge %.2f [est.]" %
             (pexp, sec0["wt"], sec0["rr"]), fontsize=7, color=C_TAG)
    oa_end = (sec0["shh"] + L * math.cos(oa))
    for s in (-1, 1):
        axm.plot([s * sec0["shh"], s * oa_end], [d["oars"]["port_z"], d["oars"]["port_z"] - L * math.sin(oa)],
                 color="#d2a86a", lw=2)
    for gp in d["gun_ports"]["side"][:1]:
        for s in (-1, 1):
            axm.add_patch(Rectangle((s * sec0["wh"] - 0.08, gp["z"] - 0.16), 0.16, 0.32, fc="black"))

    # stern view / aft section
    prep(axb, "AFT SECTION y=-8.5 + stern outline")
    for yy in (-8.5,):
        section(axb, yy, "")
    st = d["hull"]["stern_transom"]
    axb.add_patch(Polygon([(-st["half_bottom"], st["z_bottom"]), (st["half_bottom"], st["z_bottom"]),
                           (st["half_top"], st["z_top"]), (-st["half_top"], st["z_top"])], closed=True,
                          fc="none", ec="#ffd27f", lw=1.2, ls="--"))
    r = d["rudder"]
    axb.add_patch(Rectangle((-r["thickness"] / 2 - 0.05, r["top_z"] - r["depth"]), r["thickness"] + 0.1, r["depth"],
                            fc="#4a3420", ec="black"))
    for p in d["gun_ports"]["stern"]:
        axb.add_patch(Rectangle((p["x"] - 0.16, p["z"] - 0.16), 0.32, 0.32, fc="black"))
    axb.text(-6.3, 6.6, "dashed: stern transom; rudder depth %.1f [assumed]" % r["depth"], fontsize=7, color=C_TAG)

    fig.suptitle("Geobukseon design drawings (baseline: 2011 Gyeongnam 'Yi Sun-sin Project' replica 25.6 x 8.67 x 6.06 m;"
                 " proportions from Chungmugong Jeonseo 1795)", fontsize=12)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


# ----------------------------------------------------------------------------- view check sheet
def ref_aspect(d, v):
    path = os.path.join(ROOT, v["ref"])
    if os.path.exists(path):
        img = plt.imread(path)
        return img, img.shape[1] / img.shape[0]
    return None, v.get("ref_aspect", 16 / 9)


def draw_views_check(d, path, overlay=False):
    """Per view: reference photo | wireframe perspective of the design from that camera (same aspect).
    overlay=True draws the wireframe on top of the photo (local fitting aid only; refs are partly CC BY-NC-ND,
    so the published sheet keeps them side by side, unmodified)."""
    views = d["views"]
    fig, axes = plt.subplots(len(views), 1 if overlay else 2, figsize=(7 if overlay else 12, (6.5 if overlay else 4.6) * len(views)),
                             dpi=100, squeeze=False)
    geo = wireframe(d) + site_wireframe(d)
    for i, v in enumerate(views):
        img, asp = ref_aspect(d, v)
        a_ref = axes[i][0]
        a_wf = axes[i][0] if overlay else axes[i][1]
        if img is not None:
            a_ref.imshow(img, extent=(0, 1, 1, 0), aspect=1 / asp)
        else:
            a_ref.text(0.5, 0.5, "no ref image", ha="center")
        a_ref.set_title("%s  ref: %s" % (v["id"], v["ref"]), fontsize=9)
        for pts, col in geo:
            u, w, z = project(v, pts, asp)
            if np.all(z <= 0.1):
                continue
            u = np.where(z > 0.1, u, np.nan)
            a_wf.plot(u, w, color=col, lw=0.9 if overlay else 0.8, alpha=0.9)
        for ax_ in {id(a_ref): a_ref, id(a_wf): a_wf}.values():
            ax_.set_xlim(0, 1)
            ax_.set_ylim(1, 0)
            ax_.set_aspect(1 / asp)
            for t in (1 / 3, 2 / 3):
                ax_.axvline(t, color="#bbbbbb", lw=0.4)
                ax_.axhline(t, color="#bbbbbb", lw=0.4)
            ax_.set_xticks([])
            ax_.set_yticks([])
        if not overlay:
            a_wf.set_facecolor("#f4f8fb")
            a_wf.set_title("design wireframe  cam=(%.1f, %.1f, %.1f)  %gmm  shift=(%.2f, %.2f)" % (
                *v["cam"], v["lens_mm"], v.get("shift_x", 0), v.get("shift_y", 0)), fontsize=8)
    fig.suptitle("View check: reference photo vs design camera (sensor_fit HORIZONTAL, 36 mm)", fontsize=11)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


# ----------------------------------------------------------------------------- consistency report
def consistency(d):
    pr = d["principal"]
    hs = d["hull"]["stations"]
    roof = d["superstructure"]["roof"]["stations"]
    wall = d["superstructure"]["wall"]["stations"]
    ys = [r["y"] for r in hs]
    loa = max(ys) - min(ys)
    H = max(r["ridge_z"] for r in roof) - min(r["keel_z"] for r in hs)
    B = 2 * max(r["half"] for r in wall)
    dr = -min(r["keel_z"] for r in hs)
    msgs = [f"LOA stations {loa:.2f} vs principal {pr['loa']}",
            f"H keel->ridge {H:.2f} vs {pr['height_keel_to_roof']}",
            f"beam wall {B:.3f} vs {pr['beam']}",
            f"draft {dr:.2f} vs {pr['draft']}",
            f"hull stations {len(hs)}, wall {len(wall)}, roof {len(roof)}"]
    ok = abs(loa - pr["loa"]) < 0.05 and abs(H - pr["height_keel_to_roof"]) < 0.05 and abs(B - pr["beam"]) < 0.02 \
        and abs(dr - pr["draft"]) < 0.02 and len(hs) >= 11 and len(roof) >= 9
    ok = ok and all(hs[i]["y"] > hs[i + 1]["y"] for i in range(len(hs) - 1))
    print("[consistency] " + " | ".join(msgs) + (" -> OK" if ok else " -> MISMATCH"))
    return ok


def main():
    d = load()
    ok = consistency(d)
    problems = check_cameras(d)
    os.makedirs(OUT, exist_ok=True)
    if "--overlay" in sys.argv:  # local fitting aid, not published
        out = sys.argv[sys.argv.index("--overlay") + 1]
        print("[write]", draw_views_check(d, out, overlay=True))
        return
    for fn, func in (("plan.png", draw_plan), ("elevation.png", draw_elevation), ("views_check.png", draw_views_check)):
        p = func(d, os.path.join(HERE, fn))
        shutil.copy(p, os.path.join(OUT, fn))
        print("[write]", p, "-> out/")
    if problems or not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
