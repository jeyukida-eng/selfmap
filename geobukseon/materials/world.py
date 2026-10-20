"""거북선 프로젝트 — 하늘(물리 대기) + 태양광 + 렌더 설정 (Blender 5.2, Cycles/EEVEE 공용).

사용:  import world; world.setup_world(scene, sun_azimuth_deg=135, sun_elevation_deg=35)
       world.setup_render(scene, "CYCLES", "preview")
단독 확인: /opt/bvenv/bin/python materials/world.py   (오류 없이 설정만 검사)

좌표 규약(SPEC §1): +X 동, +Y 북, +Z 위. 방위각 북=0°, 동=90°(시계방향).
Blender 5.x: 구 'NISHITA' sky_type 은 'MULTIPLE_SCATTERING'(기본) / 'SINGLE_SCATTERING' 로 바뀜.
Sky 노드 sun_rotation = 방위각(rad) 그대로 (실측 확인: 그림자 방향 검증).

조명 단위는 물리값 그대로(태양 법선조도 ~150 W/m² 상당) 두고, 노출(view_settings.exposure)을
자동 계산해 흰 램버트 면이 ~1.0 근처가 되도록 맞춘다. (auto_exposure=False 로 끌 수 있음)
하늘의 태양 원반은 카메라 광선에만 보이고, 실제 직사광은 Sun 라이트가 담당 → 이중 조명 없음.
"""
import math
import bpy
from mathutils import Vector

SUN_NAME = "SUN_Key"
WORLD_NAME = "WORLD_Sky"

# 실측 보정표 (Cycles, MULTIPLE_SCATTERING, air/aerosol/ozone=1, altitude=0):
# 고도각(deg) -> 태양 원반의 법선 조도 RGB (W/m² 상당), 하늘만의 흰 수평면 휘도 RGB
_SUN_TABLE = [
    (-1.0, (0.0, 0.0, 0.0), (0.25, 0.30, 0.40)),
    (3.0, (47.17, 18.48, 1.64), (0.80, 1.06, 1.49)),
    (6.0, (79.56, 44.08, 12.64), (1.12, 1.67, 2.53)),
    (10.0, (105.45, 70.43, 31.75), (1.41, 2.27, 3.71)),
    (15.0, (123.48, 91.28, 51.65), (1.67, 2.77, 4.70)),
    (25.0, (141.03, 113.31, 77.06), (2.01, 3.41, 5.91)),
    (40.0, (151.76, 127.60, 95.91), (2.34, 4.03, 7.08)),
    (60.0, (157.45, 135.40, 106.99), (2.63, 4.56, 8.09)),
    (90.0, (159.61, 138.42, 111.43), (2.79, 4.87, 8.67)),
]


def _lerp_table(el):
    t = _SUN_TABLE
    if el <= t[0][0]:
        return t[0][1], t[0][2]
    for (e0, s0, k0), (e1, s1, k1) in zip(t, t[1:]):
        if el <= e1:
            f = (el - e0) / (e1 - e0)
            return (tuple(a + (b - a) * f for a, b in zip(s0, s1)),
                    tuple(a + (b - a) * f for a, b in zip(k0, k1)))
    return t[-1][1], t[-1][2]


def sun_direction(sun_azimuth_deg, sun_elevation_deg):
    """태양을 향하는 단위벡터 (월드)."""
    az, el = math.radians(sun_azimuth_deg), math.radians(sun_elevation_deg)
    return Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))


def _sock(sockets, key):
    for s in sockets:
        if s.identifier == key and s.enabled:
            return s
    c = [s for s in sockets if s.name == key and s.enabled]
    if len(c) != 1:
        raise KeyError(f"socket '{key}' not found/ambiguous in {[s.identifier for s in sockets]}")
    return c[0]


def setup_world(scene, sun_azimuth_deg, sun_elevation_deg, strength=1.0,
                air=1.0, dust=1.6, ozone=1.0, altitude=0.0,
                auto_exposure=True, exposure_bias=0.0, sun_angle_deg=0.6):
    """물리 하늘 + 방향이 일치하는 Sun 라이트를 만든다(멱등). 반환: (world, sun_object)."""
    w = bpy.data.worlds.get(WORLD_NAME) or bpy.data.worlds.new(WORLD_NAME)
    if w.node_tree is None:
        w.use_nodes = True  # 5.x에선 기본 node_tree 존재. 없을 때만.
    scene.world = w
    nt = w.node_tree
    nt.nodes.clear()
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "MULTIPLE_SCATTERING"
    sky.sun_elevation = math.radians(sun_elevation_deg)
    sky.sun_rotation = math.radians(sun_azimuth_deg)
    sky.altitude = altitude
    sky.air_density = air
    sky.aerosol_density = dust
    sky.ozone_density = ozone
    sky.sun_size = math.radians(0.545)
    sky.sun_intensity = 1.0
    sky.sun_disc = False
    sky.location = (-600, 150)
    sky_disc = nt.nodes.new("ShaderNodeTexSky")
    for p in ("sky_type", "sun_elevation", "sun_rotation", "altitude", "air_density",
              "aerosol_density", "ozone_density", "sun_size", "sun_intensity"):
        setattr(sky_disc, p, getattr(sky, p))
    sky_disc.sun_disc = True
    sky_disc.location = (-600, -150)
    lp = nt.nodes.new("ShaderNodeLightPath")
    lp.location = (-600, 400)
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.location = (-300, 0)
    nt.links.new(_sock(lp.outputs, "Is Camera Ray"), _sock(mix.inputs, "Factor"))
    nt.links.new(_sock(sky.outputs, "Color"), _sock(mix.inputs, "A"))
    nt.links.new(_sock(sky_disc.outputs, "Color"), _sock(mix.inputs, "B"))
    # 수평선 아래(물리 하늘은 검정): 연무색으로 채움 (Sky 노드는 Vector 입력 비활성이라 방향 미러 불가)
    _, sky_l = _lerp_table(sun_elevation_deg)
    lum = 0.2126 * sky_l[0] + 0.7152 * sky_l[1] + 0.0722 * sky_l[2]
    haze = (lum * 0.80, lum * 0.92, lum * 1.05, 1.0)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-900, -400)
    sxyz = nt.nodes.new("ShaderNodeSeparateXYZ")
    sxyz.location = (-700, -400)
    nt.links.new(_sock(tc.outputs, "Generated"), _sock(sxyz.inputs, "Vector"))
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.location = (-500, -400)
    mr.interpolation_type = "SMOOTHSTEP"
    nt.links.new(_sock(sxyz.outputs, "Z"), _sock(mr.inputs, "Value"))
    _sock(mr.inputs, "From Min").default_value = 0.006
    _sock(mr.inputs, "From Max").default_value = -0.002
    mix2 = nt.nodes.new("ShaderNodeMix")
    mix2.data_type = "RGBA"
    mix2.location = (-250, -200)
    nt.links.new(_sock(mr.outputs, "Result"), _sock(mix2.inputs, "Factor"))
    nt.links.new(_sock(mix.outputs, "Result"), _sock(mix2.inputs, "A"))
    _sock(mix2.inputs, "B").default_value = haze
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.location = (-100, 0)
    _sock(bg.inputs, "Strength").default_value = strength
    nt.links.new(_sock(mix2.outputs, "Result"), _sock(bg.inputs, "Color"))
    out = nt.nodes.new("ShaderNodeOutputWorld")
    out.location = (100, 0)
    nt.links.new(_sock(bg.outputs, "Background"), _sock(out.inputs, "Surface"))
    # EEVEE: 월드에서 태양 추출 끔(직사광은 Sun 라이트가 담당)
    w.sun_threshold = 0.0

    # --- Sun 라이트 ---
    sun_irr, sky_lum = _lerp_table(sun_elevation_deg)
    peak = max(max(sun_irr), 1e-6)
    ld = bpy.data.lights.get(SUN_NAME) or bpy.data.lights.new(SUN_NAME, "SUN")
    ld.energy = peak * strength
    ld.color = tuple(c / peak for c in sun_irr) if peak > 1e-5 else (1, 1, 1)
    ld.angle = math.radians(sun_angle_deg)
    ld.use_shadow = True
    if hasattr(ld, "shadow_maximum_resolution"):
        ld.shadow_maximum_resolution = 0.001
    ob = bpy.data.objects.get(SUN_NAME)
    if ob is None:
        ob = bpy.data.objects.new(SUN_NAME, ld)
    if ob.name not in scene.collection.objects:
        scene.collection.objects.link(ob)
    d = sun_direction(sun_azimuth_deg, sun_elevation_deg)
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = d.to_track_quat("Z", "Y")  # 라이트 -Z 가 태양→지면 방향
    ob.location = d * 100.0

    if auto_exposure:
        el = math.radians(max(sun_elevation_deg, 0.0))
        lum = lambda c: 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
        white = (lum(sun_irr) * math.sin(el) / math.pi + lum(sky_lum)) * strength
        scene.view_settings.exposure = -math.log2(max(white, 1e-4)) - 0.45 + exposure_bias
    return w, ob


def setup_render(scene, engine="CYCLES", quality="preview", res=(1920, 1080)):
    """engine: 'CYCLES' | 'BLENDER_EEVEE'. quality: 'preview' | 'final'."""
    final = quality == "final"
    r = scene.render
    r.engine = engine
    r.resolution_x, r.resolution_y = res
    r.resolution_percentage = 100
    r.film_transparent = False
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGB"
    r.image_settings.color_depth = "8"
    vs = scene.view_settings
    vs.view_transform = "AgX"
    vs.look = "AgX - Medium High Contrast"
    vs.gamma = 1.0
    scene.display_settings.display_device = "sRGB"
    if engine == "CYCLES":
        c = scene.cycles
        c.device = "CPU"
        c.samples = 512 if final else 64
        c.use_adaptive_sampling = True
        c.adaptive_threshold = 0.01 if final else 0.03
        c.use_denoising = True
        c.denoiser = "OPENIMAGEDENOISE"
        c.denoising_input_passes = "RGB_ALBEDO_NORMAL"
        c.denoising_prefilter = "ACCURATE"
        c.max_bounces = 8 if final else 6
        c.diffuse_bounces = 3 if final else 2
        c.glossy_bounces = 4 if final else 3
        c.transmission_bounces = 8 if final else 6
        c.transparent_max_bounces = 8
        c.sample_clamp_indirect = 10.0
        c.caustics_reflective = False
        c.caustics_refractive = False
        c.blur_glossy = 1.0
        r.threads_mode = "AUTO"
    elif engine == "BLENDER_EEVEE":
        e = scene.eevee
        e.taa_render_samples = 64 if final else 16
        e.use_raytracing = True
        e.ray_tracing_method = "SCREEN"
        e.ray_tracing_options.resolution_scale = "2" if final else "4"
        e.ray_tracing_options.use_denoise = True
        e.use_shadows = True
        e.shadow_ray_count = 2 if final else 1
        e.shadow_step_count = 8 if final else 6
        e.use_fast_gi = True
        e.fast_gi_method = "GLOBAL_ILLUMINATION"
        e.fast_gi_distance = 4.0
        e.use_volumetric_shadows = False
        e.volumetric_end = 400.0
    else:
        raise ValueError(f"unknown engine {engine}")
    return scene


if __name__ == "__main__":
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    setup_world(sc, 135, 35)
    setup_render(sc, "CYCLES", "preview")
    setup_render(sc, "BLENDER_EEVEE", "preview")
    print("world.py OK, exposure", round(sc.view_settings.exposure, 2))
