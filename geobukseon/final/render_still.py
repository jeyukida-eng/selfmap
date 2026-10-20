"""Cycles 최종 스틸 렌더 → out/still_<view>.png
실행: /opt/bvenv/bin/python final/render_still.py [--views bow34,aerial] [--res 1920x1080] [--samples 256]
"""
import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "modeling"), os.path.join(ROOT, "materials")]

import bpy  # noqa: E402
import build_scene  # noqa: E402
import world  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--views", default="bow34")
    ap.add_argument("--res", default="1920x1080")
    ap.add_argument("--samples", type=int, default=256)
    a = ap.parse_args()
    scene = build_scene.build(os.path.join(ROOT, "design", "geobukseon_design.json"), "final")
    world.setup_render(scene, "CYCLES", "final")
    w, h = map(int, a.res.split("x"))
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    scene.cycles.samples = a.samples
    for vid in a.views.split(","):
        scene.camera = bpy.data.objects[f"CAM_{vid}"]
        scene.render.filepath = os.path.join(ROOT, "out", f"still_{vid}.png")
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"[still] {vid} {time.time() - t:.0f}s -> {scene.render.filepath}")


if __name__ == "__main__":
    main()
