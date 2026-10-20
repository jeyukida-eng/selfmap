"""Cycles 최종 스틸 렌더 → out/still_<view>.png (뷰별 ref_aspect 비율, 뷰별 태양 views[*].sun 있으면 적용)
실행: /opt/bvenv/bin/python final/render_still.py [--views bow34,side,stern34,aerial] [--long 1920] [--samples 256]
"""
import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "modeling"), os.path.join(ROOT, "materials")]

import bpy  # noqa: E402
import build_scene  # noqa: E402
import world  # noqa: E402

DESIGN = os.path.join(ROOT, "design", "geobukseon_design.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--views", default="bow34,side,stern34,aerial")
    ap.add_argument("--long", type=int, default=1920, help="긴 변 픽셀")
    ap.add_argument("--samples", type=int, default=256)
    a = ap.parse_args()
    d = json.load(open(DESIGN))
    views = {v["id"]: v for v in d["views"]}
    scene = build_scene.build(DESIGN, "final")
    world.setup_render(scene, "CYCLES", "final")
    scene.cycles.samples = a.samples
    for vid in a.views.split(","):
        v = views[vid]
        sun = v.get("sun") or d["sun"]
        world.setup_world(scene, sun["azimuth_deg"], sun["elevation_deg"])
        aspect = float(v.get("ref_aspect", 16 / 9))
        w, h = (a.long, round(a.long / aspect)) if aspect >= 1 else (round(a.long * aspect), a.long)
        scene.render.resolution_x, scene.render.resolution_y = w, h
        scene.camera = bpy.data.objects[f"CAM_{vid}"]
        scene.render.filepath = os.path.join(ROOT, "out", f"still_{vid}.png")
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"[still] {vid} {w}x{h} sun={sun['azimuth_deg']}/{sun['elevation_deg']} "
              f"{time.time() - t:.0f}s -> {scene.render.filepath}", flush=True)


if __name__ == "__main__":
    main()
