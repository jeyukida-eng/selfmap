"""검증 렌더: design views 4개 카메라로 최종 렌더 + 클래스 마스크 렌더 → validation/round<N>/render_<id>.png, mask_<id>.png, render_meta.json
실행: /opt/bvenv/bin/python validation/render_views.py --round 2|round2_final [--engine CYCLES] [--samples 64] [--long 960] [--res 960x540] [--quality preview] [--views bow34,side]

해상도: 카메라 custom property `ref_aspect`(= 참고 사진 가로/세로)가 있으면 긴 변 --long(기본 960) 으로 그 비율,
없으면 --res. 뷰에 'sun': {azimuth_deg, elevation_deg} 가 있으면 그 뷰 렌더 직전 world.setup_world 재호출(SUN_Key 재사용).
--round 는 정수(→ round<N>/) 또는 디렉터리 이름(예: round2_final). 최종 렌더 시 Diffuse Color(알베도) 패스도 albedo_<id>.npy(float16, 선형 RGB)로 저장 → compare.py 고유색 비교.

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
# 선형값 0/0.5/1 → Standard 뷰 변환 sRGB 0/188/255. compare.py 는 최근접 팔레트로 분류.
CLASS_COLORS = {
    "hull": (1, 0, 0),
    "wall": (0, 1, 0),       # 상장 벽(방패판·원형 문양·포혈 틀·띠)
    "roof": (0.5, 1, 0),     # 개판 + 철첨 + 통로/해치
    "dragon": (0, 0, 1),
    "ghost": (1, 1, 0),
    "oars": (1, 0, 1),
    "rigging": (0, 1, 1),    # 돛대·삭구·깃발
    "sail": (1, 0.5, 0),     # 돛 + 활대(batten)
    "other": (1, 1, 1),      # 키, 통, 닻 등
}
ROOF_NAMES = ("Roof", "Walkways", "Hatches", "Spikes")


def classify(ob):
    n = ob.name
    cols = {c.name for c in ob.users_collection}
    if "Site" in cols or "Cameras" in cols:
        return None
    if "Hull" in cols:
        return "hull"
    if "Superstructure" in cols:
        return "roof" if n.startswith(ROOF_NAMES) else "wall"
    if n.startswith("Dragon"):
        return "dragon"
    if n.startswith("GhostFace"):
        return "ghost"
    if n.startswith("Oar"):
        return "oars"
    if "Rigging" in cols:
        return "sail" if n.startswith("Sail") else "rigging"
    return "other"


def cam_meta(sc, cam):
    """compare.py 용 카메라 행렬(월드→카메라, 내부 파라미터)."""
    cd = cam.data
    w, h = sc.render.resolution_x, sc.render.resolution_y
    fit = cd.sensor_fit
    if fit == "AUTO":
        fit = "HORIZONTAL" if w >= h else "VERTICAL"
    if fit == "HORIZONTAL":
        S = w
        fx = cd.lens / cd.sensor_width * w
    else:
        S = h
        fx = cd.lens / cd.sensor_height * h
    cx = w / 2 - cd.shift_x * S
    cy = h / 2 + cd.shift_y * S
    m = cam.matrix_world.inverted()
    # 자기검증용 점: 원점·용두 기준점 투영(Blender 계산)
    from bpy_extras.object_utils import world_to_camera_view
    probes = {}
    for k, p in PROBES.items():
        v = world_to_camera_view(sc, cam, Vector(p))
        probes[k] = [v.x * w, (1 - v.y) * h, v.z]
    return {"world_to_cam": [list(r) for r in m], "fx": fx, "fy": fx, "cx": cx, "cy": cy,
            "width": w, "height": h, "lens_mm": cd.lens, "sensor_mm": cd.sensor_width, "probes_px": probes}


PROBES = {"origin": (0, 0, 0), "bow_top": (0, 12.8, 2.45), "stern_top": (0, -12.8, 2.7),
          "port_mid": (-4.3, 0, 2.7), "stbd_mid": (4.3, 0, 2.7), "ridge": (0, 3, 4.6)}


def view_res(cam, long_side, default):
    asp = cam.get("ref_aspect") or cam.data.get("ref_aspect")
    if not asp:
        return default
    asp = float(asp)
    if asp >= 1:
        return long_side, int(round(long_side / asp / 2)) * 2
    return int(round(long_side * asp / 2)) * 2, long_side


def setup_albedo_output(sc, outdir):
    """컴포지터 File Output 으로 DiffCol 패스를 EXR 로 저장(bpy 5.x API)."""
    sc.view_layers[0].use_pass_diffuse_color = True
    ng = bpy.data.node_groups.new("VAL_Comp", "CompositorNodeTree")
    sc.compositing_node_group = ng
    rl = ng.nodes.new("CompositorNodeRLayers")
    fo = ng.nodes.new("CompositorNodeOutputFile")
    fo.directory = os.path.join(outdir, "_passes") + os.sep
    fo.format.media_type = "IMAGE"
    fo.format.file_format = "OPEN_EXR"
    fo.format.color_depth = "16"
    fo.file_output_items.new("RGBA", "DiffCol")
    src = [o for o in rl.outputs if "Diff" in o.name and "Col" in o.name][0]
    ng.links.new(src, fo.inputs["DiffCol"])
    # 컴포지터 결과(Combined)는 그대로 통과시켜야 렌더 PNG 가 정상
    try:
        go = ng.nodes.new("NodeGroupOutput")
        ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        ng.links.new(rl.outputs["Image"], go.inputs[0])
    except Exception as ex:  # noqa
        print("[render_views] compositor passthrough warning", ex)
    sc.render.use_compositing = True
    return fo


def save_albedo(fo, outdir, vid, w, h):
    import numpy as np
    d = fo.directory
    cand = [f for f in os.listdir(d) if f.endswith(".exr")]
    if not cand:
        print("[render_views] WARNING: albedo EXR 없음")
        return None
    p = os.path.join(d, sorted(cand, key=lambda f: os.path.getmtime(os.path.join(d, f)))[-1])
    im = bpy.data.images.load(p)
    a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1, :, :3]
    bpy.data.images.remove(im)
    out = os.path.join(outdir, f"albedo_{vid}.npy")
    np.save(out, a.astype(np.float16))
    os.remove(p)
    return out


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
    sc.render.use_compositing = False
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", required=True, help="정수 N → round<N>, 또는 디렉터리 이름")
    ap.add_argument("--engine", default="CYCLES", choices=["CYCLES", "EEVEE"])
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--res", default="960x540", help="ref_aspect 없는 카메라용")
    ap.add_argument("--long", type=int, default=960, help="ref_aspect 있을 때 긴 변 px")
    ap.add_argument("--no-albedo", action="store_true")
    ap.add_argument("--quality", default="preview", choices=["preview", "final"])
    ap.add_argument("--views", default="")
    ap.add_argument("--no-mask", action="store_true")
    a = ap.parse_args()
    w, h = (int(v) for v in a.res.lower().split("x"))
    rname = f"round{a.round}" if str(a.round).isdigit() else str(a.round)
    outdir = os.path.join(HERE, rname)
    os.makedirs(outdir, exist_ok=True)

    import build_scene
    t0 = time.time()
    sc = build_scene.build(DESIGN, a.quality)
    t_build = time.time() - t0
    setup_beauty(sc, a.engine, a.samples, w, h)
    want = [v for v in a.views.split(",") if v] or ORDER
    with open(DESIGN, encoding="utf-8") as f:
        dsg = json.load(f)
    vdict = {v["id"]: v for v in dsg["views"]}
    views = [v["id"] for v in dsg["views"]]
    sys.path.insert(0, os.path.join(ROOT, "materials"))
    import world

    def apply_sun(vid, keep_view=None):
        sun = vdict[vid].get("sun") or {"azimuth_deg": dsg["sun"]["azimuth_deg"], "elevation_deg": dsg["sun"]["elevation_deg"]}
        world.setup_world(sc, sun["azimuth_deg"], sun["elevation_deg"])
        if keep_view:  # 마스크 렌더: 노출/뷰 변환 고정
            for k, v in keep_view.items():
                setattr(sc.view_settings, k, v)
        return [sun["azimuth_deg"], sun["elevation_deg"]]
    views = [v for v in views if v in want]

    meta = {"round": rname, "engine": sc.render.engine, "samples": a.samples, "res": [w, h], "long_side": a.long,
            "quality": a.quality, "build_sec": round(t_build, 1), "views": {}}
    metap = os.path.join(outdir, "render_meta.json")
    if os.path.exists(metap):  # 일부 뷰만 재렌더 시 기존 기록 보존
        with open(metap) as f:
            old = json.load(f)
        meta["views"] = old.get("views", {})
    fo = None if a.no_albedo or a.engine != "CYCLES" else setup_albedo_output(sc, outdir)
    res_of = {}
    for vid in views:
        cam = sc.objects["CAM_" + vid]
        sc.camera = cam
        vw, vh = view_res(cam, a.long, (w, h))
        res_of[vid] = (vw, vh)
        sc.render.resolution_x, sc.render.resolution_y = vw, vh
        sc.render.filepath = os.path.join(outdir, f"render_{vid}.png")
        sun_used = apply_sun(vid)
        t = time.time()
        bpy.ops.render.render(write_still=True)
        dt = time.time() - t
        meta["views"][vid] = {"render_sec": round(dt, 1), "sun": sun_used, "exposure": round(sc.view_settings.exposure, 3), **cam_meta(sc, cam)}
        if fo is not None:
            meta["views"][vid]["albedo"] = save_albedo(fo, outdir, vid, vw, vh)
        print(f"[render_views] {vid}: {dt:.1f} s -> {sc.render.filepath}", flush=True)

    if not a.no_mask:
        counts = setup_mask(sc)
        meta["mask_class_counts"] = counts
        for vid in views:
            sc.camera = sc.objects["CAM_" + vid]
            sc.render.resolution_x, sc.render.resolution_y = res_of[vid]
            apply_sun(vid, keep_view={"view_transform": "Standard", "exposure": 0.0, "gamma": 1.0})
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
