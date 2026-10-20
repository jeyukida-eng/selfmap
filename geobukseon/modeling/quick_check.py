"""모델링 자체 확인용 저샘플 렌더: views 4개 카메라 → modeling/check_<id>.png
실행: /opt/bvenv/bin/python modeling/quick_check.py [--blend modeling/geobukseon.blend | --build] [--samples 32] [--res auto|WxH] [--views bow34,side]
"""
import argparse
import os
import sys
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", default=os.path.join(HERE, "geobukseon.blend"))
    ap.add_argument("--build", action="store_true", help="blend 대신 build_scene.build() 로 새로 구성")
    ap.add_argument("--quality", default="preview")
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--res", default="auto", help="WxH 또는 auto(카메라 ref_aspect, 긴 변 --long)")
    ap.add_argument("--long", type=int, default=640)
    ap.add_argument("--views", default="")
    ap.add_argument("--prefix", default="check_")
    a = ap.parse_args()
    if a.build:
        sys.path.insert(0, HERE)
        import build_scene
        sc = build_scene.build(build_scene.DEFAULT_DESIGN, a.quality)
    else:
        bpy.ops.wm.open_mainfile(filepath=os.path.abspath(a.blend))
        sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = a.samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.use_denoising = True
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    want = [v for v in a.views.split(",") if v]
    cams = sorted([o for o in sc.objects if o.type == "CAMERA" and o.name.startswith("CAM_")], key=lambda o: o.name)
    order = ["bow34", "side", "stern34", "aerial"]
    cams.sort(key=lambda o: order.index(o.name[4:]) if o.name[4:] in order else 99)
    total = 0.0
    for cam in cams:
        vid = cam.name[4:]
        if want and vid not in want:
            continue
        sc.camera = cam
        if a.res == "auto":
            asp = float(cam.get("ref_aspect", 16 / 9))
            w, h = (a.long, round(a.long / asp)) if asp >= 1 else (round(a.long * asp), a.long)
        else:
            w, h = (int(v) for v in a.res.lower().split("x"))
        sc.render.resolution_x, sc.render.resolution_y = w, h
        out = os.path.join(HERE, f"{a.prefix}{vid}.png")
        sc.render.filepath = out
        t = time.time()
        bpy.ops.render.render(write_still=True)
        dt = time.time() - t
        total += dt
        print(f"[quick_check] {vid}: {dt:.1f} s -> {out}")
    print(f"[quick_check] total render {total:.1f} s ({a.samples} spp, res {a.res})")


if __name__ == "__main__":
    main()
