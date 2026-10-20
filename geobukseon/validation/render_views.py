"""검증 렌더: design views 4개 카메라로 최종 렌더 + 클래스 마스크 렌더 → validation/round<N>/render_<id>.png, mask_<id>.png, render_meta.json
실행: /opt/bvenv/bin/python validation/render_views.py --round 1 [--engine CYCLES] [--samples 64] [--res 960x540] [--quality preview] [--views bow34,side]

마스크 렌더(mask_<id>.png): 같은 카메라, 1 spp, 재질 오버라이드(Object Info Color → Emission),
Site 컬렉션(부두·물·땅·산)은 holdout → 알파=0. 즉 '물 위로 보이고 부두에 가려지지 않은' 배 부분만 남는다.
RGB = 클래스 색(CLASS_COLORS), 알파 = 커버리지. compare.py 가 이를 설계 투영 마스크와 IoU 비교한다.
"""
import argparse
import json
import os
import sys
import time

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "modeling"))
DESIGN = os.path.join(ROOT, "design", "geobukseon_design.json")
ORDER = ["bow34", "side", "stern34", "aerial"]

# 클래스 → (RGB 0/1 조합). compare.py 와 동일해야 함.
CLASS_COLORS = {
    "hull": (1, 0, 0),
    "super": (0, 1, 0),      # 상장 벽 + 개판 지붕 + 철첨 + 통로/해치
    "dragon": (0, 0, 1),
    "ghost": (1, 1, 0),
    "oars": (1, 0, 1),
    "rigging": (0, 1, 1),
    "other": (1, 1, 1),      # 키, 통, 닻 등
}


def classify(ob):
    n = ob.name
    cols = {c.name for c in ob.users_collection}
    if "Site" in cols or "Cameras" in cols:
        return None
    if "Hull" in cols:
        return "hull"
    if "Superstructure" in cols:
        return "super"
    if n.startswith("Dragon"):
        return "dragon"
    if n.startswith("GhostFace"):
        return "ghost"
    if n.startswith("Oar"):
        return "oars"
    if "Rigging" in cols:
        return "rigging"
    return "other"


def cam_meta(sc, cam):
    """compare.py 용 카메라 행렬(월드→카메라, 내부 파라미터)."""
    cd = cam.data
    w, h = sc.render.resolution_x, sc.render.resolution_y
    fx = cd.lens / cd.sensor_width * w  # sensor_fit HORIZONTAL
    m = cam.matrix_world.inverted()
    # 자기검증용 점: 원점·용두 기준점 투영(Blender 계산)
    from bpy_extras.object_utils import world_to_camera_view
    probes = {}
    for k, p in {"origin": (0, 0, 0), "bow_top": (0, 12.8, 2.45), "stern_top": (0, -12.8, 2.7)}.items():
        v = world_to_camera_view(sc, cam, Vector(p))
        probes[k] = [v.x * w, (1 - v.y) * h, v.z]
    return {"world_to_cam": [list(r) for r in m], "fx": fx, "fy": fx, "cx": w / 2, "cy": h / 2,
            "width": w, "height": h, "lens_mm": cd.lens, "sensor_mm": cd.sensor_width, "probes_px": probes}


def setup_beauty(sc, engine, samples, w, h):
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    if engine == "CYCLES":
        sc.render.engine = "CYCLES"
        sc.cycles.device = "CPU"
        sc.cycles.samples = samples
        sc.cycles.use_adaptive_sampling = True
        sc.cycles.use_denoising = True
        sc.cycles.seed = 0
    else:
        os.environ.setdefault("EGL_PLATFORM", "surfaceless")
        sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [
            e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
        sc.eevee.taa_render_samples = samples


def setup_mask(sc):
    mat = bpy.data.materials.new("VAL_MaskOverride")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    oi = nt.nodes.new("ShaderNodeObjectInfo")
    em = nt.nodes.new("ShaderNodeEmission")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(oi.outputs["Color"], em.inputs["Color"])
    em.inputs["Strength"].default_value = 1.0
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    counts = {}
    for ob in sc.objects:
        if ob.type not in ("MESH", "CURVE", "SURFACE", "META", "FONT", "CURVES", "POINTCLOUD", "VOLUME"):
            continue
        k = classify(ob)
        if k is None:
            if "Site" in {c.name for c in ob.users_collection}:
                ob.is_holdout = True
            continue
        ob.color = (*CLASS_COLORS[k], 1.0)
        counts[k] = counts.get(k, 0) + 1
    vl = sc.view_layers[0]
    vl.material_override = mat
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 1
    sc.cycles.use_adaptive_sampling = False
    sc.cycles.use_denoising = False
    sc.cycles.max_bounces = 0
    sc.cycles.filter_width = 0.01
    sc.render.film_transparent = True
    sc.view_settings.view_transform = "Standard"
    try:
        sc.view_settings.look = "None"
    except TypeError:
        pass
    sc.view_settings.exposure = 0.0
    sc.view_settings.gamma = 1.0
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--engine", default="CYCLES", choices=["CYCLES", "EEVEE"])
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--res", default="960x540")
    ap.add_argument("--quality", default="preview", choices=["preview", "final"])
    ap.add_argument("--views", default="")
    ap.add_argument("--no-mask", action="store_true")
    a = ap.parse_args()
    w, h = (int(v) for v in a.res.lower().split("x"))
    outdir = os.path.join(HERE, f"round{a.round}")
    os.makedirs(outdir, exist_ok=True)

    import build_scene
    t0 = time.time()
    sc = build_scene.build(DESIGN, a.quality)
    t_build = time.time() - t0
    setup_beauty(sc, a.engine, a.samples, w, h)
    want = [v for v in a.views.split(",") if v] or ORDER
    with open(DESIGN, encoding="utf-8") as f:
        views = [v["id"] for v in json.load(f)["views"]]
    views = [v for v in views if v in want]

    meta = {"round": a.round, "engine": sc.render.engine, "samples": a.samples, "res": [w, h],
            "quality": a.quality, "build_sec": round(t_build, 1), "views": {}}
    metap = os.path.join(outdir, "render_meta.json")
    if os.path.exists(metap):  # 일부 뷰만 재렌더 시 기존 기록 보존
        with open(metap) as f:
            old = json.load(f)
        meta["views"] = old.get("views", {})
    for vid in views:
        cam = sc.objects["CAM_" + vid]
        sc.camera = cam
        sc.render.filepath = os.path.join(outdir, f"render_{vid}.png")
        t = time.time()
        bpy.ops.render.render(write_still=True)
        dt = time.time() - t
        meta["views"][vid] = {"render_sec": round(dt, 1), **cam_meta(sc, cam)}
        print(f"[render_views] {vid}: {dt:.1f} s -> {sc.render.filepath}", flush=True)

    if not a.no_mask:
        counts = setup_mask(sc)
        meta["mask_class_counts"] = counts
        for vid in views:
            sc.camera = sc.objects["CAM_" + vid]
            sc.render.filepath = os.path.join(outdir, f"mask_{vid}.png")
            t = time.time()
            bpy.ops.render.render(write_still=True)
            meta["views"][vid]["mask_sec"] = round(time.time() - t, 1)
            print(f"[render_views] mask {vid} -> {sc.render.filepath}", flush=True)
    meta["class_colors"] = CLASS_COLORS
    meta["total_render_sec"] = round(sum(v.get("render_sec", 0) for v in meta["views"].values()), 1)
    with open(metap, "w") as f:
        json.dump(meta, f, indent=1)
    print(f"[render_views] build {t_build:.1f} s, beauty total {meta['total_render_sec']} s -> {metap}")


if __name__ == "__main__":
    main()
