"""Generate plan / elevation drawings + flythrough clearance check from design/geobukseon_design.json.
Run: /opt/bvenv/bin/python design/gen_drawings.py   (writes design/plan.png, design/elevation.png, copies to out/)
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

C_HULL = "#7a5230"
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


def dragon_polygon_side(dh):
    """Side (YZ) silhouette of dragon head: simple neck+head wedge, pitched."""
    bx, by, bz = dh["base"]
    L, H = dh["length"], dh["height"]
    m = dh["mouth_open"]
    a = math.radians(dh["pitch_deg"])
    # local coords (u forward, v up)
    pts = [(0, -H * 0.45), (L * 0.55, -H * 0.30), (L * 0.98, -m * 0.5 - 0.05), (L * 0.62, -0.02),
           (L * 1.0, m * 0.5), (L * 0.85, H * 0.32), (L * 0.55, H * 0.55), (L * 0.35, H * 0.50),
           (L * 0.2, H * 0.62), (0, H * 0.45)]
    out = []
    for u, v in pts:
        out.append((by + u * math.cos(a) - v * math.sin(a), bz + u * math.sin(a) + v * math.cos(a)))
    return out


def hull_bbox(d, include_oars=True):
    """Axis-aligned boxes (xmin,xmax,ymin,ymax,zmin,zmax) of obstacles."""
    hs = d["hull"]["stations"]
    roof = d["superstructure"]["roof"]["stations"]
    dh = d["dragon_head"]
    xmax = max(max(r["sheer_half"] for r in hs), max(r["half"] for r in roof))
    ymin = min(r["y"] for r in hs)
    ymax = max(max(r["y"] for r in hs), dh["base"][1] + dh["length"] * math.cos(math.radians(dh["pitch_deg"])))
    zmin = min(r["keel_z"] for r in hs)
    zmax = max(r["ridge_z"] for r in roof)
    zmax = max(zmax, dh["base"][2] + dh["length"] * math.sin(math.radians(dh["pitch_deg"])) + dh["height"] * 0.6)
    boxes = {"hull": (-xmax, xmax, ymin, ymax, zmin, zmax)}
    if include_oars:
        o = d["oars"]
        reach = max(r["half"] for r in d["superstructure"]["wall"]["stations"]) + \
            o["length"] * (1 - o["inboard_fraction"]) * math.cos(math.radians(o["angle_deg"]))
        boxes["oars"] = (-reach, reach, min(o["y"]) - o["blade_width"] - 0.5, max(o["y"]) + o["blade_width"] + 0.5,
                         -0.3, o["port_z"] + 0.2)
    for i, m in enumerate(d["masts"]):
        r = 0.5
        boxes[f"mast{i}"] = (-r, r, m["y"] - r, m["y"] + r, m["base_z"], m["base_z"] + m["height"] + 1.0)
    p = d["site"].get("pier")
    if p:
        boxes["pier"] = (p["x_min"], p["x_max"], p["y_min"], p["y_max"], p["bottom_z"], p["top_z"])
    s = d["site"].get("shore")
    if s:
        boxes["shore"] = (s["x_min"], s["x_max"], s["y_min"], s["y_max"], -5, s["z"])
    return boxes


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
        w = interp_station(d["superstructure"]["wall"]["stations"], "half", yy)
        for s in (-1, 1):
            ax.plot([s * w, s * (w + out_len)], [yy, yy - 0.6], color="#d2a86a", lw=1.6, zorder=6)
    # dragon head
    dh = d["dragon_head"]
    L = dh["length"] * math.cos(math.radians(dh["pitch_deg"]))
    ax.add_patch(Polygon([(-dh["width"] / 2, dh["base"][1]), (dh["width"] / 2, dh["base"][1]),
                          (dh["width"] * 0.3, dh["base"][1] + L), (-dh["width"] * 0.3, dh["base"][1] + L)],
                         fc="#2e7d4f", ec="black", lw=0.8, zorder=10))
    ax.annotate("dragon head (yongdu)", (0, dh["base"][1] + L), (6, 17), fontsize=8,
                arrowprops=dict(arrowstyle="->", lw=0.7), zorder=11)
    for m in d["masts"]:
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
    # panels
    pw = d["superstructure"]["wall"]["panel_width"]
    for yy in np.arange(wys[0], wys[-1], pw):
        ax.plot([yy, yy], [np.interp(yy, ys, sz), np.interp(yy, wys, wtop)], color="#5a2e14", lw=0.4, zorder=4)
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
    # dragon head
    ax.add_patch(Polygon(dragon_polygon_side(d["dragon_head"]), closed=True, fc="#2e7d4f", ec="black", zorder=8))
    # ghost face
    gf = d["ghost_face"]
    ax.add_patch(Rectangle((gf["center"][1] - 0.15, gf["center"][2] - gf["height"] / 2), 0.3, gf["height"],
                           angle=0, fc="#c0392b", ec="black", zorder=8))
    ax.annotate("ghost face (gwimyeon)", (gf["center"][1], gf["center"][2]), (13.5, -1.2), fontsize=8,
                arrowprops=dict(arrowstyle="->", lw=0.7))
    ax.annotate("dragon head (yongdu)", (13.5, 3.9), (13.8, 6.2), fontsize=8, arrowprops=dict(arrowstyle="->", lw=0.7))
    # masts
    for m in d["masts"]:
        ax.add_patch(Rectangle((m["y"] - m["diameter"] / 2, m["base_z"]), m["diameter"], m["height"], fc="#c79a5b",
                               ec="black", lw=0.6, zorder=3.5))
        if m["sail"]["state"] == "furled":
            top = m["base_z"] + m["height"]
            ax.add_patch(Rectangle((m["y"] - m["sail"]["w"] / 2, top - 1.2), m["sail"]["w"], 0.35, fc="#e8dcc0",
                                   ec="black", lw=0.5, zorder=3.6))
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
    ax.set_xlim(-16, 17)
    ax.set_ylim(-3.2, 14.5)
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
    tipz = dh["base"][2] + dh["length"] * math.sin(math.radians(dh["pitch_deg"]))
    axf.add_patch(Polygon([(-dh["width"] / 2, dh["base"][2] - dh["height"] * 0.45),
                           (dh["width"] / 2, dh["base"][2] - dh["height"] * 0.45),
                           (dh["width"] / 2, tipz + dh["height"] * 0.5), (0, tipz + dh["height"] * 0.65),
                           (-dh["width"] / 2, tipz + dh["height"] * 0.5)], closed=True, fc="#2e7d4f", ec="black"))
    oa = math.radians(d["oars"]["angle_deg"])
    L = d["oars"]["length"] * (1 - d["oars"]["inboard_fraction"])
    for s in (-1, 1):
        axf.plot([s * sec["wh"], s * (sec["wh"] + L * math.cos(oa))],
                 [d["oars"]["port_z"], d["oars"]["port_z"] - L * math.sin(oa)], color="#d2a86a", lw=2)
    for m in d["masts"]:
        axf.add_patch(Rectangle((-m["diameter"] / 2, m["base_z"]), m["diameter"], 7.2 - m["base_z"], fc="#c79a5b",
                                ec="black", lw=0.5, zorder=0.5))
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
    oa_end = (sec0["wh"] + L * math.cos(oa))
    for s in (-1, 1):
        axm.plot([s * sec0["wh"], s * oa_end], [d["oars"]["port_z"], d["oars"]["port_z"] - L * math.sin(oa)],
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
    for fn, func in (("plan.png", draw_plan), ("elevation.png", draw_elevation)):
        p = func(d, os.path.join(HERE, fn))
        shutil.copy(p, os.path.join(OUT, fn))
        print("[write]", p, "-> out/")
    if problems or not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
