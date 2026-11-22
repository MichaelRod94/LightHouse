"""C · Primer golpe (propuesta elegida) — construye la escena desde params.json + app.json y,
con --render, genera los cuadros, el preview y la tira.

Asset para la app: 16 cuadros del MISMO encuadre de la lente de un faro (Fresnel de vidrio con
anillos tallados para enfocar la lámpara), de "apagada" (lente_00) a "a tope" (lente_15). Es una
escala de brillo: la app elige el cuadro con la pista "nivel" del manifiesto (parpadeo autoral fijo,
definido en params.json; no depende del audio). Nombre y versión son textos de la app.

Render (Cycles en CPU, acotado): como la luz se suma linealmente, se renderizan solo DOS pases a
EXR en capas/ — "ambiente" (luces de estudio, lámpara apagada) y "lampara" (solo la lámpara, la
bruma y el haz) — y cada nivel i se compone como ambiente + k_i * lampara, con el resplandor
(Bloom / Fog Glow) aplicado por nivel en el compositor.

  & <blender.exe> --background --factory-startup --python build.py -- [--render] [--app X]
                  [--cuadro N | --preview-cuadro N] [--salida archivo.png] [--reusar-capas] [--muestras N]
"""
import math
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True                      # sin __pycache__ junto a comun.py
sys.path[:0] = [AQUI, os.path.dirname(AQUI)]        # comun.py al lado o en la carpeta de arriba
import bmesh  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
import comun as C  # noqa: E402


# ---------------------------------------------------------------- geometría

def pendiente(r, f, n):
    """dy/dr de la cara de Fresnel en el radio r: desvía un rayo paralelo al eje hacia el foco f."""
    t_out = math.atan(r / f)
    t_g = math.asin(math.sin(t_out) / n)
    return n * math.sin(t_g) / (n * math.cos(t_g) - 1)


def perfil_zonas(radios, f, n, pasos=10):
    """Frente tallado (y <= 0, hacia la cámara): una zona por par de radios, contrahuella recta al inicio."""
    pts = []
    for ra, rb in zip(radios, radios[1:]):
        rs = [ra + (rb - ra) * j / pasos for j in range(pasos + 1)]
        ys = [0.0] * len(rs)
        for j in range(len(rs) - 2, -1, -1):
            ys[j] = ys[j + 1] - pendiente((rs[j] + rs[j + 1]) / 2, f, n) * (rs[j + 1] - rs[j])
        pts += list(zip(rs, ys))
    return pts


def revolucion(nombre, perfil, segs, sc, mat, padre, cerrado=False, angulo_duro=30):
    """Malla de revolución alrededor del eje Y local a partir de un perfil [(r, y), ...]."""
    me = bpy.data.meshes.new(nombre)
    bm = bmesh.new()
    vs = [bm.verts.new((r, y, 0.0)) for r, y in perfil]
    es = [bm.edges.new((vs[i], vs[i + 1])) for i in range(len(vs) - 1)]
    if cerrado:
        es.append(bm.edges.new((vs[-1], vs[0])))
    bmesh.ops.spin(bm, geom=vs + es, cent=(0, 0, 0), axis=(0, 1, 0), angle=2 * math.pi, steps=segs, use_duplicate=False)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    try:
        me.shade_smooth()
        me.set_sharp_from_angle(angle=math.radians(angulo_duro))
    except AttributeError:
        pass
    ob = C.objeto_malla(nombre, me, sc, mat)
    ob.parent = padre
    return ob


def hijo(ob, padre, loc=(0, 0, 0), rot=(0, 0, 0), escala=None):
    ob.parent = padre
    ob.location = loc
    ob.rotation_euler = rot
    if escala:
        ob.scale = escala
    return ob


def prim(op, nombre, mat, padre, loc, rot=(0, 0, 0), **kw):
    op(**kw)
    ob = bpy.context.active_object
    ob.name = nombre
    ob.data.materials.append(mat)
    return hijo(ob, padre, loc, rot)


def pernos(nombre, n, radio, y, mat, padre, tam=0.022):
    for i in range(n):
        a = 2 * math.pi * (i + 0.5) / n
        prim(bpy.ops.mesh.primitive_cylinder_add, f"{nombre}{i}", mat, padre,
             (radio * math.cos(a), y, radio * math.sin(a)), (math.radians(90), 0, 0),
             vertices=6, radius=tam, depth=0.03)


# ---------------------------------------------------------------- materiales

def mat_vidrio(n):
    m = bpy.data.materials.new("Vidrio")
    nt = m.node_tree
    nt.nodes.clear()
    g = nt.nodes.new("ShaderNodeBsdfGlass")
    g.inputs["IOR"].default_value = n
    g.inputs["Roughness"].default_value = 0.0
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(g.outputs[0], out.inputs["Surface"])
    return m


def mat_metal(nombre, gris, rug):
    """Metal neutro con rugosidad irregular (reflejos menos "de plástico")."""
    m = C.material(nombre, base=(gris,) * 3, metal=1.0)
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    ruido = nt.nodes.new("ShaderNodeTexNoise")
    ruido.inputs["Scale"].default_value = 40.0
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = rug
    nt.links.new(ruido.outputs["Fac"], mr.inputs["Value"])
    nt.links.new(mr.outputs[0], b.inputs["Roughness"])
    return m


def mat_volumen(nombre, densidad, anis=0.3, halo=False):
    """Bruma. Devuelve (material, nodo Value de la densidad). Con halo=True la densidad cae
    suave hacia los bordes de la caja (en coordenadas del objeto) y hacia la cámara: sin bordes."""
    m = bpy.data.materials.new(nombre)
    nt = m.node_tree
    nt.nodes.remove(nt.nodes.get("Principled BSDF"))
    v = nt.nodes.new("ShaderNodeVolumeScatter")
    v.inputs["Anisotropy"].default_value = anis
    dens = nt.nodes.new("ShaderNodeValue")
    dens.outputs[0].default_value = densidad
    if halo:
        tc = nt.nodes.new("ShaderNodeTexCoord")
        sx = nt.nodes.new("ShaderNodeSeparateXYZ")
        cb = nt.nodes.new("ShaderNodeCombineXYZ")
        ln = nt.nodes.new("ShaderNodeVectorMath")
        ln.operation = "LENGTH"
        radial = nt.nodes.new("ShaderNodeMapRange")
        radial.interpolation_type = "SMOOTHSTEP"
        radial.inputs["From Min"].default_value, radial.inputs["From Max"].default_value = 0.0, 0.42
        radial.inputs["To Min"].default_value, radial.inputs["To Max"].default_value = 1.0, 0.0
        largo = nt.nodes.new("ShaderNodeMapRange")
        largo.inputs["From Min"].default_value, largo.inputs["From Max"].default_value = -0.5, 0.5
        m1 = nt.nodes.new("ShaderNodeMath")
        m1.operation = "MULTIPLY"
        m2 = nt.nodes.new("ShaderNodeMath")
        m2.operation = "MULTIPLY"
        nt.links.new(tc.outputs["Object"], sx.inputs[0])
        nt.links.new(sx.outputs["X"], cb.inputs["X"])
        nt.links.new(sx.outputs["Z"], cb.inputs["Z"])
        nt.links.new(cb.outputs[0], ln.inputs[0])
        nt.links.new(ln.outputs["Value"], radial.inputs["Value"])
        nt.links.new(sx.outputs["Y"], largo.inputs["Value"])
        nt.links.new(radial.outputs[0], m1.inputs[0])
        nt.links.new(largo.outputs[0], m1.inputs[1])
        nt.links.new(m1.outputs[0], m2.inputs[0])
        nt.links.new(dens.outputs[0], m2.inputs[1])
        nt.links.new(m2.outputs[0], v.inputs["Density"])
    else:
        nt.links.new(dens.outputs[0], v.inputs["Density"])
    nt.links.new(v.outputs[0], nt.nodes.get("Material Output").inputs["Volume"])
    return m, dens


def mat_bulbo(fuerza):
    """Bulbo esmerilado: deja ver el núcleo y brilla él mismo."""
    m = bpy.data.materials.new("Bulbo")
    nt = m.node_tree
    nt.nodes.clear()
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = fuerza
    mx = nt.nodes.new("ShaderNodeMixShader")
    mx.inputs["Fac"].default_value = 0.55
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tr.outputs[0], mx.inputs[1])
    nt.links.new(em.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs["Surface"])
    return m, em


def area(nombre, sc, energia, tam, pos, objetivo):
    ld = bpy.data.lights.new(nombre, "AREA")
    ld.energy = energia
    ld.size = tam
    ob = bpy.data.objects.new(nombre, ld)
    sc.collection.objects.link(ob)
    ob.location = pos
    ob.rotation_euler = (Vector(objetivo) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    return ld


# ---------------------------------------------------------------- escena

def main():
    a = C.argumentos()
    p, app = C.cargar(AQUI, a.app)
    sc = C.preparar_escena(p)
    rp = p["render"]
    r = sc.render
    r.engine = "CYCLES"
    r.use_compositing = False                       # los pases se guardan crudos (lineales)
    r.threads_mode = "FIXED"
    r.threads = max(1, min(rp["hilos"], os.cpu_count() or 4))
    cy = sc.cycles
    cy.device = "CPU"
    cy.samples = a.muestras or rp["muestras"]
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = rp["umbral_ruido"]
    cy.use_denoising = True
    try:
        cy.denoiser = "OPENIMAGEDENOISE"
    except TypeError:
        pass
    cy.max_bounces = cy.transmission_bounces = rp["rebotes"]
    cy.glossy_bounces, cy.diffuse_bounces, cy.volume_bounces = 6, 2, 1
    cy.transparent_max_bounces = 8
    cy.caustics_reflective = cy.caustics_refractive = False
    cy.blur_glossy = 0.5
    cy.sample_clamp_indirect = 10.0

    # entorno: degradado que solo ven los reflejos (la cámara ve negro real)
    lu = p["luces"]
    w = C.mundo(sc)
    nt = w.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sz = nt.nodes.new("ShaderNodeSeparateXYZ")
    grad = nt.nodes.new("ShaderNodeMapRange")
    grad.inputs["From Min"].default_value, grad.inputs["From Max"].default_value = -0.2, 0.9
    grad.inputs["To Min"].default_value, grad.inputs["To Max"].default_value = lu["entorno"]
    lpath = nt.nodes.new("ShaderNodeLightPath")
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    fuerza_mundo = nt.nodes.new("ShaderNodeMath")
    fuerza_mundo.operation = "MULTIPLY"
    bgn = nt.nodes.get("Background")
    nt.links.new(tc.outputs["Generated"], sz.inputs[0])
    nt.links.new(sz.outputs["Z"], grad.inputs["Value"])
    nt.links.new(grad.outputs[0], bgn.inputs["Color"])
    nt.links.new(lpath.outputs["Is Camera Ray"], inv.inputs[1])
    nt.links.new(inv.outputs[0], fuerza_mundo.inputs[0])
    nt.links.new(fuerza_mundo.outputs[0], bgn.inputs["Strength"])

    # --- lente de Fresnel enfocada (todo cuelga de un vacío)
    L = p["lente"]
    f, n, g, segs = L["focal"], L["ior"], L["grosor"], L["segmentos"]
    vidrio = mat_vidrio(n)
    ca = p["carcasa"]
    bronce = mat_metal("Bronce", ca["metal_gris"], ca["rugosidad"])
    oscuro = mat_metal("MetalOscuro", ca["metal_gris"] * 0.45, [0.3, 0.5])
    raiz = bpy.data.objects.new("Lente", None)
    sc.collection.objects.link(raiz)

    r0, wz = L["domo_radio"], L["ancho_anillo"]
    radios = [0.0, r0] + [r0 + k * wz for k in range(1, L["anillos"] + 1)]
    r1 = radios[-1]
    frente = perfil_zonas(radios, f, n)
    revolucion("Ojo", frente + [(r1, g), (0.0, g)], segs, sc, vidrio, raiz)
    r2 = r1 + L["ancho_aro"]
    e = 0.005                                       # los aros muerden el vidrio: sin caras coincidentes
    revolucion("Aro", [(r1 - e, g + 0.04), (r1 - e, -0.14), (r1 + 0.012, -0.17), (r2 - 0.012, -0.17), (r2 + e, -0.14), (r2 + e, g + 0.04)],
               segs, sc, bronce, raiz, cerrado=True)
    pernos("PernoAro", L["pernos_aro"], (r1 + r2) / 2, -0.18, bronce, raiz)
    radios_ext = [r2 + k * L["ancho_ext"] for k in range(L["anillos_ext"] + 1)]
    r3 = radios_ext[-1]
    ext = perfil_zonas(radios_ext, f, n)
    alto_ext = -min(y for _, y in ext)
    revolucion("Prismas", ext + [(r3, g), (r2, g)], segs, sc, vidrio, raiz, cerrado=True)
    r4 = r3 + L["ancho_aro"] * 1.2
    revolucion("AroExt", [(r3 - e, g + 0.06), (r3 - e, -alto_ext - 0.05), (r3 + 0.015, -alto_ext - 0.09), (r4 - 0.015, -alto_ext - 0.09),
                          (r4, -alto_ext - 0.05), (r4, g + 0.06)], segs, sc, bronce, raiz, cerrado=True)
    pernos("PernoExt", L["pernos_ext"], (r3 + r4) / 2, -alto_ext - 0.1, bronce, raiz)
    for i in range(L["barras"]):
        ang = math.pi / 4 + i * 2 * math.pi / L["barras"]
        rm = (r2 + r3) / 2
        prim(bpy.ops.mesh.primitive_cube_add, f"Barra{i}", bronce, raiz,
             (rm * math.cos(ang), -alto_ext - 0.02, rm * math.sin(ang)), (0, -ang, 0), size=1)
        bpy.context.active_object.scale = (r3 - r2 + 0.04, 0.05, 0.035)

    # --- cámara y encuadre
    cam = C.camara(sc, lente_mm=p["camara"]["lente_mm"])
    en = p["encuadre"]
    wl, hl = p["lienzo"]
    alto_vis = 2 * r4 / en["alto_rel"]
    dist = alto_vis * (wl / hl) * cam.data.lens / cam.data.sensor_width
    cam.location = (0, -dist, 0)
    raiz.location = C.pantalla_a_mundo(cam, sc, en["centro"][0], en["centro"][1], dist)
    raiz.rotation_euler = [math.radians(x) for x in L["giro_grados"]]
    bpy.context.view_layer.update()

    # --- lámpara en el punto donde la lente enfoca los rayos que vienen de la cámara:
    #     así, encendida, la lente se ve LLENA de luz (lente de faro vista desde el haz)
    rot = raiz.matrix_world.to_3x3().normalized()
    d = rot.inverted() @ (raiz.location - cam.location)
    D = d.length
    d.normalize()
    v = f * D / (D - f)
    foco = Vector((0, g, 0)) + v * Vector((d.x / d.y, 1.0, d.z / d.y))
    lp = p["lampara"]
    m_nuc, em_nuc = C.material_emision("Nucleo", lp["emision_nucleo"])
    prim(bpy.ops.mesh.primitive_uv_sphere_add, "Nucleo", m_nuc, raiz, foco, radius=lp["radio_nucleo"], segments=24, ring_count=12)
    m_bul, em_bul = mat_bulbo(lp["emision_bulbo"])
    prim(bpy.ops.mesh.primitive_uv_sphere_add, "Bulbo", m_bul, raiz, foco, radius=lp["radio_bulbo"], segments=32, ring_count=16)
    pl = bpy.data.lights.new("LuzLampara", "POINT")
    pl.shadow_soft_size = lp["radio_bulbo"]
    hijo(bpy.data.objects.new("LuzLampara", pl), raiz, foco)
    sc.collection.objects.link(bpy.data.objects["LuzLampara"])

    # --- carcasa: tambor metálico detrás de la lente, con fondo
    y_fondo = foco.y + ca["largo_extra"]
    revolucion("Tambor", [(r4 - 0.06, g + 0.02), (r4, g + 0.02), (r4, y_fondo), (r4 - 0.06, y_fondo)], segs // 2, sc, oscuro, raiz, cerrado=True)
    revolucion("Fondo", [(0.0, y_fondo), (r4, y_fondo), (r4, y_fondo + 0.05), (0.0, y_fondo + 0.05)], segs // 2, sc, oscuro, raiz)

    # --- bruma: dentro del tambor (la llena la lámpara) y delante de la lente (la llena el haz)
    br = p["bruma"]
    m_in, vol_in = mat_volumen("BrumaInterior", br["interior"])
    revolucion("BrumaInterior", [(0.0, g + 0.03), (r4 - 0.08, g + 0.03), (r4 - 0.08, y_fondo - 0.02), (0.0, y_fondo - 0.02)],
               48, sc, m_in, raiz)
    m_ex, vol_ex = mat_volumen("BrumaExterior", br["exterior"], 0.5, halo=True)
    prim(bpy.ops.mesh.primitive_cube_add, "BrumaExterior", m_ex, raiz, (0, -alto_ext - 0.25 - 2.5, 0), size=1)
    bpy.context.active_object.scale = (6 * r4, 5.0, 6 * r4)
    haz = bpy.data.lights.new("Haz", "SPOT")
    haz.spot_size = math.radians(br["haz_grados"])
    haz.spot_blend = 1.0
    haz.shadow_soft_size = r1
    hz = bpy.data.objects.new("Haz", haz)
    sc.collection.objects.link(hz)
    hijo(hz, raiz, (0, -alto_ext - 0.2, 0), (math.radians(-90), 0, 0))

    # --- luces de estudio (solo en el pase "ambiente")
    centro = raiz.location
    clave = area("Clave", sc, lu["clave_w"], lu["clave_tam"], centro + Vector(lu["clave_pos"]), centro)
    contra = area("Contra", sc, lu["contra_w"], lu["clave_tam"], centro + Vector(lu["contra_pos"]), centro)

    def pase(nombre):
        amb = nombre == "ambiente"
        fuerza_mundo.inputs[1].default_value = 1.0 if amb else 0.0
        clave.energy, contra.energy = (lu["clave_w"], lu["contra_w"]) if amb else (0.0, 0.0)
        em_nuc.inputs["Strength"].default_value = 0.0 if amb else lp["emision_nucleo"]
        em_bul.inputs["Strength"].default_value = 0.0 if amb else lp["emision_bulbo"]
        pl.energy = 0.0 if amb else lp["luz_w"]
        haz.energy = 0.0 if amb else br["haz_w"]
        # la bruma solo existe en el pase de la lámpara: las luces de estudio no la "agrisan"
        vol_in.outputs[0].default_value = 0.0 if amb else br["interior"]
        vol_ex.outputs[0].default_value = 0.0 if amb else br["exterior"]

    pase("ambiente")                                 # estado guardado en escena.blend
    sc.frame_start = sc.frame_end = 0

    # --- composición de niveles: escena aparte, sin geometría, solo compositor
    asp = p["asset"]
    nn = asp["niveles"]
    niveles = bpy.data.scenes.new("Niveles")
    rn = niveles.render
    rn.engine = "BLENDER_EEVEE"
    rn.resolution_x, rn.resolution_y, rn.resolution_percentage = wl, hl, 100
    rn.dither_intensity = p.get("dither", 0.0)      # sin bandas en los degradados (PNG de 8 bits)
    rn.use_compositing = True
    C.sin_metadatos(rn)
    niveles.view_settings.view_transform = "Standard"
    niveles.view_settings.look = "None"
    cam_n = bpy.data.objects.new("CamNiveles", bpy.data.cameras.new("CamNiveles"))
    niveles.collection.objects.link(cam_n)
    niveles.camera = cam_n
    ims = rn.image_settings
    ims.media_type, ims.file_format, ims.color_mode, ims.color_depth, ims.compression = "IMAGE", "PNG", "BW", "8", 100
    img_nivel = bpy.data.images.new("Nivel", wl, hl, alpha=False, float_buffer=True)
    C.compositor(niveles, p["resplandor"], imagen=img_nivel)
    capas = os.path.join(AQUI, "capas")
    cache = {}

    def capa(nombre):
        if nombre not in cache:
            ruta = os.path.join(capas, nombre + ".exr")
            if not (a.reusar_capas and os.path.exists(ruta)):
                os.makedirs(capas, exist_ok=True)
                pase(nombre)
                e = r.image_settings
                e.media_type, e.file_format, e.color_mode, e.color_depth, e.exr_codec = "IMAGE", "OPEN_EXR", "RGB", "16", "ZIP"
                r.filepath = os.path.join(capas, nombre)
                bpy.ops.render.render(write_still=True)
                pase("ambiente")
                print(f"[intro] pase {nombre} -> {ruta}")
            im = bpy.data.images.load(ruta, check_existing=False)
            px = np.empty(wl * hl * 4, dtype=np.float32)
            im.pixels.foreach_get(px)
            bpy.data.images.remove(im)
            cache[nombre] = px
        return cache[nombre]

    # forma de la luz: centro caliente (cae hacia el borde del cristal) y caída radial suave hasta negro mucho
    # antes de los bordes del cuadro (sin recortes: ni la bruma ni el resplandor llegan a tocarlos)
    vl = p["velo"]

    def gauss(img, s):
        """Desenfoque gaussiano (FFT con margen de 4σ: sin recortes ni vueltas en los bordes)."""
        h, w = img.shape
        sh = (h + int(8 * s), w + int(8 * s))
        k = np.exp(-2 * (np.pi * s) ** 2 * (np.fft.fftfreq(sh[0])[:, None] ** 2 + np.fft.rfftfreq(sh[1])[None, :] ** 2))
        return np.fft.irfft2(np.fft.rfft2(img, s=sh) * k, s=sh)[:h, :w]

    def componer(i, salida):
        k = p["nivel_max"] * (i / (nn - 1)) ** asp["gamma"]
        px = capa("ambiente") + k * capa("lampara")
        # lente empañada (tipo Pro-Mist): las altas luces, desenfocadas en varias escalas, se suman de vuelta
        im = px.reshape(hl, wl, 4)
        luz = np.maximum(im[..., 0] - vl["umbral"], 0.0)
        velo = sum(c["fuerza"] * gauss(luz, c["sigma"]) for c in vl["capas"])
        im[..., :3] += velo[..., None].astype(np.float32)
        px[3::4] = 1.0
        img_nivel.pixels.foreach_set(px)
        img_nivel.update()
        rn.filepath = salida
        rn.use_file_extension = False
        bpy.ops.render.render(write_still=True, scene=niveles.name)

    def generar(cuadros_dir):
        os.makedirs(cuadros_dir, exist_ok=True)
        for x in os.listdir(cuadros_dir):
            if x.startswith(asp["prefijo"]) and x.endswith(".png"):
                os.remove(os.path.join(cuadros_dir, x))
        for i in range(nn):
            componer(i, os.path.join(cuadros_dir, f"{asp['prefijo']}{i:0{asp['digitos']}d}.png"))
        # franjas: cada cuadro, partido en N archivos que la app decodifica de a uno (un PNG grande tarda
        # demasiado en un solo tick); los cuadros completos se quedan en cuadros/ para el preview
        fdir = os.path.join(cuadros_dir, "franjas")
        os.makedirs(fdir, exist_ok=True)
        for i in range(nn):
            C.partir_png(os.path.join(cuadros_dir, f"{asp['prefijo']}{i:0{asp['digitos']}d}.png"),
                         os.path.join(fdir, f"{asp['prefijo']}{i:0{asp['digitos']}d}"), asp["franjas"])

    # --- preview: la lente sigue la pista "nivel" de params.json (parpadeo autoral fijo)
    pref, dig = asp["prefijo"], asp["digitos"]
    cuadros_dir = os.path.join(AQUI, "cuadros")
    fps = p["fps_preview"]
    nprev = C.cuadro(p["duracion_ms"], fps)
    archivos = []
    for fr in range(nprev):
        t = fr * 1000 / fps
        if t < p["lente_ms"]["aparece"]:
            archivos.append(None)
        else:
            idx = min(nn - 1, max(0, round(C.pista(p["parpadeo"], t) * (nn - 1))))
            archivos.append(os.path.join(cuadros_dir, f"{pref}{idx:0{dig}d}.png"))
    capas_prev = [{"tipo": "secuencia", "id": "lente", "archivos": archivos}]
    for tx in p["textos"]:
        capas_prev.append({"tipo": "texto", "id": tx["id"], "texto": C.texto(tx["texto"], app, p),
                           "fuente": C.fuente(p["fuente_nombre"] if tx.get("negrita") else p["fuente_texto"]),
                           "px": C.pt_a_px(tx["pt"]), "color": C.color(tx["color"], app, p), "pos": tx["pos"],
                           "tramos": [(C.cuadro(tx["desde_ms"], fps), nprev)]})
    prev = C.crear_preview(p, app, capas_prev)
    C.terminar(a, p, sc, prev, AQUI, pref, nn, dig, generar=generar, un_cuadro=componer)


main()
