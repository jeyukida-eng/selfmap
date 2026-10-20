"""재질 견본 씬 렌더 (Cycles 960x540 64spp → matlib_preview.png, EEVEE → matlib_preview_eevee.png).

실행: /opt/bvenv/bin/python materials/preview_matlib.py [--only cycles|eevee] [--samples 64] [--close --out /abs/path.png]
"""
import os
import sys
import math
import time

os.environ.setdefault("EGL_PLATFORM", "surfaceless")
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import matlib  # noqa: E402
import world  # noqa: E402


def box(name, mn, mx, mat, bevel=0.0):
    c = [(a + b) / 2 for a, b in zip(mn, mx)]
    s = [(b - a) for a, b in zip(mn, mx)]
    bpy.ops.mesh.primitive_cube_add(size=1, location=c)
    o = bpy.context.object
    o.name = name
    o.scale = s
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        m = o.modifiers.new("bev", "BEVEL")
        m.width = bevel
        m.segments = 2
    o.data.materials.append(mat)
    return o


def cyl(name, p0, p1, r, mat, verts=24):
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=d.length, location=(p0 + p1) / 2)
    o = bpy.context.object
    o.name = name
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = d.to_track_quat("Z", "Y")
    o.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    return o


def build_scene(M):
    sc = bpy.context.scene
    # 바다
    bpy.ops.mesh.primitive_plane_add(size=6000, location=(0, 0, 0))
    sea = bpy.context.object
    sea.name = "Sea"
    sea.data.materials.append(M["water"])
    # 선체 판재 블록 (+X 면이 카메라 쪽)
    box("HullLow", (-1.2, -9.5, -1.0), (0.02, -3.8, 0.35), M["hull_waterline"])
    box("HullUp", (-1.2, -9.5, 0.35), (0.0, -3.8, 1.9), M["hull_wood"])
    box("Wall", (-1.3, -9.5, 1.9), (-0.15, -3.8, 3.0), M["wall_panel"], bevel=0.02)
    # 노
    for i, yy in enumerate((-8.6, -6.6, -4.8)):
        cyl(f"Oar{i}", (-0.2, yy, 1.3), (3.2, yy - 0.6, -0.4), 0.06, M["oar_wood"])
    # 거북등 지붕 (반원통, 축=Y) + 철첨
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=2.3, depth=5.5, location=(-2.6, -0.6, 0.4))
    roof = bpy.context.object
    roof.name = "Roof"
    roof.rotation_euler = (math.radians(90), 0, 0)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    bpy.ops.object.shade_smooth()
    roof.data.materials.append(M["roof_shell"])
    for row in range(-2, 3):
        ang = math.radians(row * 22)
        for k in range(6):
            yy = -2.9 + k * 0.9 + (0.45 if row % 2 else 0)
            base = Vector((-2.6 + math.sin(ang) * 2.3, yy, 0.4 + math.cos(ang) * 2.3))
            n = Vector((math.sin(ang), 0, math.cos(ang)))
            bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=0.035, radius2=0.002, depth=0.22,
                                            location=base + n * 0.1)
            sp = bpy.context.object
            sp.rotation_mode = "QUATERNION"
            sp.rotation_quaternion = n.to_track_quat("Z", "Y")
            sp.data.materials.append(M["iron_spike"])
    # 부두 석축
    box("Pier", (-3.5, 2.6, -1.5), (1.4, 10.0, 0.7), M["stone"], bevel=0.03)
    # 귀면 (로컬 XZ 평면, 법선 -Y → Z축 90° 회전해 +X 향함)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0.6, 3.6, 1.35))
    gf = bpy.context.object
    gf.name = "GhostFace"
    gf.scale = (1.2, 1.0, 1.0)
    gf.rotation_euler = (math.radians(90), 0, 0)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)  # 메시를 로컬 XZ 평면으로
    gf.rotation_euler = (0, 0, math.radians(90))
    sol = gf.modifiers.new("sol", "SOLIDIFY")
    sol.thickness = 0.06
    gf.data.materials.append(M["ghost_face"])
    # 용두 (늘린 구, +Y 방향)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=1.0, location=(-0.6, 5.6, 1.6))
    dh = bpy.context.object
    dh.name = "DragonHead"
    dh.scale = (0.45, 1.3, 0.55)
    dh.rotation_euler = (math.radians(-15), 0, math.radians(-25))
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.shade_smooth()
    dh.data.materials.append(M["dragon_head"])
    # 돛대 + 돛 + 밧줄 + 깃발
    cyl("Mast", (-2.0, 8.0, 0.7), (-2.0, 8.0, 8.5), 0.14, M["mast_wood"])
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=20, y_subdivisions=20, size=1, location=(-1.9, 8.0, 4.6))
    sail = bpy.context.object
    sail.name = "Sail"
    sail.scale = (3.0, 5.0, 1)
    sail.rotation_euler = (math.radians(90), 0, math.radians(75))
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    sail.data.materials.append(M["sail_cloth"])
    cyl("Rope1", (-2.0, 8.0, 8.3), (1.2, 4.0, 0.7), 0.018, M["rope"], 12)
    cyl("Rope2", (-2.0, 8.0, 8.3), (1.2, 9.8, 0.7), 0.018, M["rope"], 12)
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=12, y_subdivisions=8, size=1, location=(-2.0, 8.65, 8.1))
    fl = bpy.context.object
    fl.name = "Flag"
    fl.scale = (1.2, 0.8, 1)
    fl.rotation_euler = (math.radians(90), 0, math.radians(80))
    fl.color = (0.6, 0.05, 0.03, 1.0)
    fl.data.materials.append(M["flag_cloth"])
    # 지면(해안 둔덕)
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=60, y_subdivisions=60, size=1, location=(-10, 9, 0))
    gr = bpy.context.object
    gr.name = "Ground"
    gr.scale = (16, 22, 1)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for v in gr.data.vertices:
        x, y = v.co.x, v.co.y
        v.co.z = 0.9 * (1 - math.exp(-max(0.0, (x + 4 + (y - 9) * 0.1) * -0.35))) + \
            0.25 * math.sin(x * 0.7) * math.cos(y * 0.5) - 0.3
    bpy.ops.object.shade_smooth()
    gr.data.materials.append(M["ground"])
    for i, (x, y, r) in enumerate(((-4.5, 11.0, 0.7), (-6.0, 12.5, 1.0), (-3.9, 13.0, 0.5))):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=r, location=(x, y, 0.2))
        rk = bpy.context.object
        rk.scale = (1.3, 1.0, 0.7)
        rk.data.materials.append(M["stone"])
    # 카메라 (동쪽에서 서쪽을 봄)
    cd = bpy.data.cameras.new("CAM")
    cd.lens = 26
    cam = bpy.data.objects.new("CAM", cd)
    sc.collection.objects.link(cam)
    if "--close" in sys.argv:
        cam.location = (7.0, -3.0, 2.4)
        d = Vector((-1.5, -1.2, 1.2)) - cam.location
        cd.lens = 35
    else:
        cam.location = (15.5, 0.5, 3.6)
        d = Vector((-1.5, 0.3, 1.6)) - cam.location
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = d.to_track_quat("-Z", "Y")
    sc.camera = cam
    return sc


def main():
    only = None
    samples = 64
    a = sys.argv[1:]
    if "--only" in a:
        only = a[a.index("--only") + 1]
    if "--samples" in a:
        samples = int(a[a.index("--samples") + 1])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    t0 = time.time()
    M = matlib.build_all(hex_cell=0.9)
    sc = build_scene(M)
    world.setup_world(sc, sun_azimuth_deg=125, sun_elevation_deg=28)
    print(f"build {time.time() - t0:.1f}s exposure {sc.view_settings.exposure:.2f}")
    res = (960, 540)
    if only in (None, "cycles"):
        world.setup_render(sc, "CYCLES", "preview", res)
        sc.cycles.samples = samples
        sc.render.filepath = (a[a.index("--out") + 1] if "--out" in a
                              else os.path.join(HERE, "matlib_preview.png"))
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"CYCLES render {time.time() - t:.1f}s -> {sc.render.filepath}")
    if only in (None, "eevee"):
        world.setup_render(sc, "BLENDER_EEVEE", "preview", res)
        sc.render.filepath = os.path.join(HERE, "matlib_preview_eevee.png")
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"EEVEE render {time.time() - t:.1f}s -> {sc.render.filepath}")


if __name__ == "__main__":
    main()
