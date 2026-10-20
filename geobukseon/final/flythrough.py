"""EEVEE 24초 카메라 플라이스루 → out/frames/fly_####.png (설계 JSON flythrough 키프레임 사용)
실행: EGL_PLATFORM=surfaceless /opt/bvenv/bin/python final/flythrough.py [--res 960x540] [--samples 8] [--start 1 --end 576] [--step 1]
이미 렌더된 프레임은 건너뜀(중단 후 재실행 가능).
"""
import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "modeling"), os.path.join(ROOT, "materials"), os.path.join(ROOT, "design")]

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
import build_scene  # noqa: E402
from gen_drawings import interp_flythrough  # 설계 충돌검사와 동일 경로  # noqa: E402
import world  # noqa: E402

DESIGN = os.path.join(ROOT, "design", "geobukseon_design.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", default="960x540")
    ap.add_argument("--samples", type=int, default=8)
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--end", type=int, default=0)
    ap.add_argument("--step", type=int, default=1)
    a = ap.parse_args()
    d = json.load(open(DESIGN))
    fly = d["flythrough"]
    fps, n = fly["fps"], int(fly["fps"] * fly["seconds"])
    keys = sorted(fly["keys"], key=lambda k: k["t"])
    scene = build_scene.build(DESIGN, "preview")
    world.setup_render(scene, "BLENDER_EEVEE", "final")
    w, h = map(int, a.res.split("x"))
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    scene.eevee.taa_render_samples = a.samples
    scene.render.fps = fps
    cam_data = bpy.data.cameras.new("CAM_fly")
    cam = bpy.data.objects.new("CAM_fly", cam_data)
    scene.collection.objects.link(cam)
    cam_data.clip_start, cam_data.clip_end = 0.1, 3000
    scene.camera = cam
    outdir = os.path.join(ROOT, "out", "frames")
    os.makedirs(outdir, exist_ok=True)
    end = a.end or n
    for f in range(a.start, end + 1, a.step):
        path = os.path.join(outdir, f"fly_{f:04d}.png")
        if os.path.exists(path):
            continue
        t = (f - 1) / fps
        p = interp_flythrough(keys, t)
        loc, tgt = Vector(p["cam"]), Vector(p["look_at"])
        cam.location = loc
        cam.rotation_euler = (tgt - loc).to_track_quat("-Z", "Y").to_euler()
        cam_data.lens = float(p["lens_mm"])
        scene.frame_set(f)
        scene.render.filepath = path
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"[fly] {f}/{end} {time.time() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
