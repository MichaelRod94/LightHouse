"""Utilidades comunes de las propuestas de intro. Se ejecuta DENTRO de Blender (bpy + numpy).

Cada concepto (`A-faro`, `B-pulso`, `C-primer-golpe`) tiene un `build.py` que:
  1. lee su `params.json` y `../app.json` (o el que se pase con `--app`);
  2. construye la escena 3D desde cero (escena "Escena") y una escena "Preview" en el
     editor de video que simula cómo la compondrá la app (cuadros PNG + rectángulos de
     color + textos dibujados aparte);
  3. guarda `escena.blend` y, con `--render`, renderiza `cuadros/`, `preview.mp4` y `tira.png`.

Uso (PowerShell, desde la raíz del repo):
  & <blender.exe> --background --factory-startup --python fases\\intro-propuestas\\A-faro\\build.py -- --render
o, para los tres a la vez: .\\fases\\intro-propuestas\\generar.ps1
"""
import argparse
import json
import math
import os
import shutil
import sys
import tempfile
import time

import bpy
import numpy as np

RAIZ = os.path.dirname(os.path.abspath(__file__))
FUENTES_WIN = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")


# ---------------------------------------------------------------- argumentos y datos

def argumentos():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser(prog="build.py")
    p.add_argument("--render", action="store_true", help="renderiza cuadros/, preview.mp4 y tira.png")
    p.add_argument("--app", default=os.path.join(RAIZ, "app.json"), help="ruta de app.json (por defecto ../app.json)")
    p.add_argument("--cuadro", help="renderiza solo ese cuadro (o lista '3,10,20') del asset a --salida (prueba; no guarda)")
    p.add_argument("--preview-cuadro", help="igual que --cuadro, pero del preview")
    p.add_argument("--salida", help="PNG de salida (un cuadro) o carpeta (varios)")
    p.add_argument("--reusar-capas", action="store_true", help="C: reutiliza los pases EXR ya renderizados en capas/")
    p.add_argument("--muestras", type=int, help="pisa las muestras de render (pruebas rápidas)")
    return p.parse_args(argv)


def leer_json(ruta):
    with open(ruta, encoding="utf-8-sig") as fh:
        return json.load(fh)


def cargar(carpeta, ruta_app):
    return leer_json(os.path.join(carpeta, "params.json")), leer_json(ruta_app)


def hex_rgb(h):
    """'#RRGGBB' -> (r, g, b) en 0..1 (sRGB, como lo pinta Tk)."""
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def srgb_a_lineal(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def color(ref, app, p):
    """Resuelve 'look:N' (de app.json), 'token:X' (tema de muestra en params) o '#RRGGBB'."""
    if ref.startswith("look:"):
        return hex_rgb(app["looks"][ref[5:]][0])
    if ref.startswith("token:"):
        return hex_rgb(p["tema_muestra"][ref[6:]])
    return hex_rgb(ref)


def texto(plantilla, app, p):
    """Rellena {app}, {version}, {autor} y {dispositivo} como lo hará el reproductor."""
    return plantilla.format(app=app["app"], version=app["version"], autor=app["autor"],
                            dispositivo=p.get("dispositivo_muestra", ""))


def fuente(nombre):
    """Carga una fuente de Windows (C:\\Windows\\Fonts). Si no existe, usa la de Blender."""
    ruta = os.path.join(FUENTES_WIN, nombre)
    if os.path.exists(ruta):
        return bpy.data.fonts.load(ruta, check_existing=True)
    print(f"[intro] fuente {nombre} no encontrada; uso la de Blender")
    return None


def pt_a_px(pt):
    return round(pt * 96 / 72)


def cuadro(t_ms, fps):
    return int(round(t_ms * fps / 1000))


EASINGS = {
    "lineal": lambda s: s,
    "in_cubic": lambda s: s ** 3,
    "out_cubic": lambda s: 1 - (1 - s) ** 3,
    "in_out": lambda s: 4 * s ** 3 if s < 0.5 else 1 - (-2 * s + 2) ** 3 / 2,
}


def pista(puntos, t):
    """Valor de una pista del manifiesto [[t_ms, valor, easing?], ...] en t (ms), como lo hará el
    reproductor de la app: el easing de un punto rige el tramo que llega a él; "corte" salta de golpe
    al llegar. Antes del primer punto vale el primero; después del último, el último."""
    if t <= puntos[0][0]:
        return puntos[0][1]
    for (t0, v0, *_), (t1, v1, *e) in zip(puntos, puntos[1:]):
        if t < t1:
            modo = e[0] if e else "lineal"
            if modo == "corte" or t1 == t0:
                return v0
            return v0 + (v1 - v0) * EASINGS[modo]((t - t0) / (t1 - t0))
    return puntos[-1][1]


# ---------------------------------------------------------------- escena 3D

def sin_metadatos(r):
    """Sin metadatos (fecha, hora, render...) en los PNG: salida reproducible byte a byte."""
    for prop in r.bl_rna.properties:
        if prop.identifier.startswith("use_stamp") and not prop.is_readonly:
            setattr(r, prop.identifier, False)


def preparar_escena(p, nombre="Escena"):
    sc = bpy.context.scene
    sc.name = nombre
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for col in (bpy.data.meshes, bpy.data.lights, bpy.data.cameras, bpy.data.materials):
        for d in list(col):
            col.remove(d)
    w, h = p["lienzo"]
    r = sc.render
    r.engine = "BLENDER_EEVEE"
    r.resolution_x, r.resolution_y, r.resolution_percentage = w, h, 100
    r.fps = p.get("fps", 20)
    r.dither_intensity = 0.0          # sin ruido de tramado: PNG más chicos
    r.film_transparent = False
    r.use_compositing = True
    r.use_sequencer = False
    sin_metadatos(r)
    vs = sc.view_settings
    vs.view_transform = "Standard"    # luz neutra fiel: blanco = blanco, sin curva fílmica
    vs.look = "None"
    vs.exposure, vs.gamma = 0.0, 1.0
    sc.eevee.taa_render_samples = p.get("muestras", 16)
    ims = r.image_settings
    ims.media_type = "IMAGE"
    ims.file_format = "PNG"
    ims.color_mode = "BW"             # luz neutra -> PNG en escala de grises de 8 bits
    ims.color_depth = "8"
    ims.compression = 100
    r.use_file_extension = True
    bpy.context.preferences.filepaths.save_version = 0  # sin escena.blend1
    return sc


def mundo(sc, color_rgb=(0, 0, 0), fuerza=1.0):
    w = bpy.data.worlds.new("Mundo")
    sc.world = w
    nt = w.node_tree
    bg = nt.nodes.get("Background")
    bg.inputs["Color"].default_value = (*color_rgb, 1)
    bg.inputs["Strength"].default_value = fuerza
    return w


def camara(sc, nombre="Camara", lente_mm=50, orto=None):
    cd = bpy.data.cameras.new(nombre)
    if orto:
        cd.type = "ORTHO"
        cd.ortho_scale = orto
    else:
        cd.lens = lente_mm
    cd.sensor_fit = "HORIZONTAL"
    cd.sensor_width = 36
    cd.clip_start, cd.clip_end = 0.1, 200
    ob = bpy.data.objects.new(nombre, cd)
    sc.collection.objects.link(ob)
    ob.rotation_euler = (math.radians(90), 0, 0)  # mira hacia +Y
    sc.camera = ob
    return ob


def tam_visible(cam, sc, distancia):
    """Ancho y alto visibles (unidades) a una distancia de la cámara (perspectiva u orto)."""
    w, h = sc.render.resolution_x, sc.render.resolution_y
    cd = cam.data
    if cd.type == "ORTHO":
        ancho = cd.ortho_scale
    else:
        ancho = 2 * distancia * (cd.sensor_width / 2) / cd.lens
    return ancho, ancho * h / w


def pantalla_a_mundo(cam, sc, sx, sy, distancia):
    """(sx, sy) relativos al lienzo, sy desde ARRIBA -> punto 3D a `distancia` delante de la cámara (que mira a +Y)."""
    ancho, alto = tam_visible(cam, sc, distancia)
    c = cam.location
    return (c.x + (sx - 0.5) * ancho, c.y + distancia, c.z + (0.5 - sy) * alto)


def a_pantalla(sc, cam, punto):
    """Punto 3D -> (sx, sy) relativos, sy desde arriba."""
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector
    v = world_to_camera_view(sc, cam, Vector(punto))
    return v.x, 1 - v.y


def caja_en_pantalla(sc, cam, ob):
    """Caja (x0, y0, x1, y1) relativa al lienzo, y desde arriba, de un objeto ya evaluado."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    pts = [a_pantalla(sc, cam, ev.matrix_world @ v.co) for v in me.vertices]
    ev.to_mesh_clear()
    xs, ys = [q[0] for q in pts], [q[1] for q in pts]
    return min(xs), min(ys), max(xs), max(ys)


def encajar(sc, cam, ob, centro, ancho_rel, distancia):
    """Escala y mueve `ob` (de frente a la cámara) para que su caja en pantalla tenga ese
    ancho relativo y ese centro (y desde arriba). Devuelve la caja final."""
    bpy.context.view_layer.update()
    x0, y0, x1, y1 = caja_en_pantalla(sc, cam, ob)
    k = ancho_rel / (x1 - x0)
    ob.scale = [s * k for s in ob.scale]
    bpy.context.view_layer.update()
    x0, y0, x1, y1 = caja_en_pantalla(sc, cam, ob)
    ancho, alto = tam_visible(cam, sc, distancia)
    ob.location.x += (centro[0] - (x0 + x1) / 2) * ancho
    ob.location.z -= (centro[1] - (y0 + y1) / 2) * alto
    bpy.context.view_layer.update()
    return caja_en_pantalla(sc, cam, ob)


def material(nombre, base=(0.5, 0.5, 0.5), rugosidad=0.5, metal=0.0, emision=0.0, emision_color=(1, 1, 1)):
    m = bpy.data.materials.new(nombre)
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*base, 1)
    b.inputs["Roughness"].default_value = rugosidad
    b.inputs["Metallic"].default_value = metal
    b.inputs["Emission Color"].default_value = (*emision_color, 1)
    b.inputs["Emission Strength"].default_value = emision
    return m


def material_emision(nombre, fuerza=1.0, rgb=(1, 1, 1)):
    m = bpy.data.materials.new(nombre)
    nt = m.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*rgb, 1)
    em.inputs["Strength"].default_value = fuerza
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m, em


def objeto_malla(nombre, me, sc, mat=None):
    ob = bpy.data.objects.new(nombre, me)
    sc.collection.objects.link(ob)
    if mat:
        me.materials.append(mat)
    return ob


def texto_3d(sc, cuerpo, fnt, tam=1.0, extrusion=0.0, bisel=0.0, nombre="Nombre"):
    cu = bpy.data.curves.new(nombre, "FONT")
    cu.body = cuerpo
    if fnt:
        cu.font = fnt
    cu.size = tam
    cu.align_x, cu.align_y = "CENTER", "CENTER"
    cu.extrude = extrusion
    cu.bevel_depth = bisel
    cu.bevel_resolution = 2
    ob = bpy.data.objects.new(nombre, cu)
    sc.collection.objects.link(ob)
    ob.rotation_euler = (math.radians(90), 0, 0)   # de pie, mirando a la cámara (-Y)
    return ob


def texto_a_malla(sc, ob):
    """Convierte un objeto de texto en malla (sin operadores) y devuelve el nuevo objeto."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    nuevo = bpy.data.objects.new(ob.name + "_malla", me)
    sc.collection.objects.link(nuevo)
    nuevo.matrix_world = ob.matrix_world.copy()
    bpy.data.objects.remove(ob, do_unlink=True)
    return nuevo


def piezas_por_letra(me):
    """Agrupa las piezas conectadas de una malla de texto en letras (por solape en X).
    Devuelve una lista (ordenada de izquierda a derecha) de listas de índices de polígonos."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    visto, piezas = set(), []
    for f in bm.faces:
        if f.index in visto:
            continue
        pila, pieza = [f], []
        visto.add(f.index)
        while pila:
            g = pila.pop()
            pieza.append(g.index)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in visto:
                        visto.add(h.index)
                        pila.append(h)
        xs = [v.co.x for i in pieza for v in bm.faces[i].verts]
        piezas.append([min(xs), max(xs), pieza])
    bm.free()
    piezas.sort(key=lambda q: q[0])
    letras = []
    for x0, x1, caras in piezas:
        if letras and x0 < letras[-1][1] - 0.15 * (x1 - x0):   # se solapa con la anterior (p. ej. el punto de la i)
            letras[-1][1] = max(letras[-1][1], x1)
            letras[-1][2].extend(caras)
        else:
            letras.append([x0, x1, list(caras)])
    return [q[2] for q in letras]


def hornear(cosa, ruta, valores, indice=-1):
    """Inserta un keyframe por cuadro: valores = {cuadro: valor}. Interpolación constante."""
    for f, val in valores.items():
        if indice >= 0:
            getattr(cosa, ruta)[indice] = val
            cosa.keyframe_insert(ruta, index=indice, frame=f)
        else:
            setattr(cosa, ruta, val)
            cosa.keyframe_insert(ruta, frame=f)


def constante(id_data):
    ad = id_data.animation_data
    if not ad or not ad.action:
        return
    for fc in fcurvas(ad):
        for k in fc.keyframe_points:
            k.interpolation = "CONSTANT"


def fcurvas(ad):
    act = ad.action
    if hasattr(act, "fcurves") and len(getattr(act, "fcurves", [])):
        return list(act.fcurves)
    # acciones por capas (Blender 4.4+ / 5.x)
    out = []
    for layer in getattr(act, "layers", []):
        for strip in layer.strips:
            for bag in strip.channelbags:
                out.extend(bag.fcurves)
    return out


# ---------------------------------------------------------------- composición (brillo)

GLARE = {"umbral": "Highlights Threshold", "suavidad": "Highlights Smoothness", "fuerza": "Strength",
         "tamano": "Size", "rayos": "Streaks", "angulo": "Streaks Angle", "iteraciones": "Iterations",
         "desvanecer": "Fade", "calidad": "Quality", "saturacion": "Saturation"}


def compositor(sc, etapas, imagen=None):
    """Cadena de nodos Glare sobre el render (o sobre `imagen`, una imagen de bpy).
    etapas = [{"tipo": "Fog Glow", "umbral": 1, ...}, ...]."""
    ng = bpy.data.node_groups.new("Composicion", "CompositorNodeTree")
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    if imagen is None:
        prev = ng.nodes.new("CompositorNodeRLayers").outputs["Image"]
    else:
        nodo = ng.nodes.new("CompositorNodeImage")
        nodo.image = imagen
        prev = nodo.outputs["Image"]
    nodos = []
    for e in etapas:
        g = ng.nodes.new("CompositorNodeGlare")
        g.inputs["Type"].default_value = e["tipo"]
        for k, val in e.items():
            if k != "tipo":
                g.inputs[GLARE[k]].default_value = val
        ng.links.new(prev, g.inputs["Image"])
        prev = g.outputs["Image"]
        nodos.append(g)
    out = ng.nodes.new("NodeGroupOutput")
    ng.links.new(prev, out.inputs[0])
    sc.compositing_node_group = ng
    return ng, nodos


# ---------------------------------------------------------------- preview (editor de video)

def crear_preview(p, app, capas, nombre="Preview"):
    """Escena de editor de video que simula el reproductor de la app.
    capas: lista de dicts en orden de abajo hacia arriba:
      {"tipo": "secuencia", "id", "archivos": [ruta o None por cuadro]}
      {"tipo": "color", "id", "color": (r,g,b), "rect": [x0,y0,x1,y1], "tramos": [(f0, f1), ...]}
      {"tipo": "texto", "id", "texto", "fuente", "px", "color": (r,g,b), "pos": [x, y], "tramos": [(f0, f1)]}
    """
    fps = p.get("fps_preview", p.get("fps", 20))
    w, h = p["lienzo"]
    n = cuadro(p["duracion_ms"], fps)
    v = bpy.data.scenes.new(nombre)
    r = v.render
    r.resolution_x, r.resolution_y, r.resolution_percentage = w, h, 100
    r.fps = fps
    r.dither_intensity = 0.0
    r.use_sequencer = True
    r.use_compositing = False
    v.view_settings.view_transform = "Standard"
    v.view_settings.look = "None"
    v.frame_start, v.frame_end = 0, n - 1
    se = v.sequence_editor_create()
    canal = 1
    fondo = se.strips.new_effect("fondo", "COLOR", canal, 0, length=n)
    fondo.color = color(p.get("fondo", "token:intro_bg"), app, p)
    for c in capas:
        canal += 1
        if c["tipo"] == "secuencia":
            f = 0
            arch = c["archivos"]
            while f < len(arch):
                if arch[f] is None:
                    f += 1
                    continue
                g = f
                while g < len(arch) and arch[g] is not None:
                    g += 1
                st = se.strips.new_image(f"{c['id']}_{f}", arch[f], canal, f, fit_method="ORIGINAL")
                for a in arch[f + 1:g]:
                    st.elements.append(os.path.basename(a))
                f = g
        elif c["tipo"] == "color":
            x0, y0, x1, y1 = c["rect"]
            for i, (f0, f1) in enumerate(c["tramos"]):
                st = se.strips.new_effect(f"{c['id']}_{i}", "COLOR", canal, f0, length=max(1, f1 - f0))
                st.color = c["color"]
                t = st.transform
                t.scale_x, t.scale_y = x1 - x0, y1 - y0
                t.offset_x = ((x0 + x1) / 2 - 0.5) * w
                t.offset_y = (0.5 - (y0 + y1) / 2) * h
        elif c["tipo"] == "texto":
            for i, (f0, f1) in enumerate(c["tramos"]):
                st = se.strips.new_effect(f"{c['id']}_{i}", "TEXT", canal, f0, length=max(1, f1 - f0))
                st.text = c["texto"]
                if c["fuente"]:
                    st.font = c["fuente"]
                st.font_size = c["px"]
                st.color = (*c["color"], 1)
                st.location = (c["pos"][0], 1 - c["pos"][1])
                st.anchor_x, st.anchor_y = "CENTER", "CENTER"
                st.alignment_x = "CENTER"
    return v


def _render_rango(sc, f0, f1, patron):
    sc.frame_start, sc.frame_end = f0, f1
    sc.render.filepath = patron
    bpy.ops.render.render(animation=True, scene=sc.name)


def render_cuadros(sc, carpeta, prefijo, n, digitos):
    os.makedirs(carpeta, exist_ok=True)
    for f in os.listdir(carpeta):
        if f.startswith(prefijo) and f.endswith(".png"):
            os.remove(os.path.join(carpeta, f))
    ims = sc.render.image_settings
    ims.media_type, ims.file_format, ims.color_mode = "IMAGE", "PNG", "BW"
    _render_rango(sc, 0, n - 1, os.path.join(carpeta, prefijo + "#" * digitos))


def render_un_cuadro(sc, f, salida, color_mode):
    tmp = tempfile.mkdtemp(prefix="intro_")
    ims = sc.render.image_settings
    ims.media_type, ims.file_format, ims.color_mode = "IMAGE", "PNG", color_mode
    viejo = (sc.frame_start, sc.frame_end)
    _render_rango(sc, f, f, os.path.join(tmp, "c_####"))
    sc.frame_start, sc.frame_end = viejo
    hecho = [x for x in os.listdir(tmp) if x.endswith(".png")][0]
    os.makedirs(os.path.dirname(os.path.abspath(salida)), exist_ok=True)
    shutil.move(os.path.join(tmp, hecho), salida)
    shutil.rmtree(tmp, ignore_errors=True)


def render_mp4(v, ruta):
    ims = v.render.image_settings
    ims.media_type = "VIDEO"
    ims.file_format = "FFMPEG"
    ff = v.render.ffmpeg
    ff.format, ff.codec = "MPEG4", "H264"
    ff.constant_rate_factor = "HIGH"
    ff.ffmpeg_preset = "GOOD"
    ff.gopsize = v.render.fps
    ff.audio_codec = "NONE"
    if os.path.exists(ruta):
        os.remove(ruta)
    v.render.use_file_extension = False
    v.render.filepath = ruta
    v.frame_start, v.frame_end = 0, cuadro(v["duracion_ms"], v.render.fps) - 1
    bpy.ops.render.render(animation=True, scene=v.name)


def render_tira(v, p, tiempos_ms, ruta, ocultar=("version",), cols=4, hueco=4):
    """Renderiza 8 cuadros del preview (sin la capa de versión: ningún PNG lleva la versión)
    con una etiqueta de tiempo, y los compone en una cuadrícula."""
    fps = v.render.fps
    se = v.sequence_editor
    silenciados = []
    for st in se.strips_all:
        if any(st.name.startswith(o + "_") for o in ocultar) and not st.mute:
            st.mute = True
            silenciados.append(st)
    canal = max(s.channel for s in se.strips_all) + 1
    n = cuadro(v["duracion_ms"], fps)
    lab = se.strips.new_effect("etiqueta", "TEXT", canal, 0, length=n)
    fnt = fuente(p["fuente_texto"])
    if fnt:
        lab.font = fnt
    lab.font_size = 13
    lab.color = (0.75, 0.75, 0.75, 1)
    lab.use_box, lab.box_color, lab.box_margin = True, (0, 0, 0, 0.75), 0.01
    lab.location = (0.012, 0.975)
    lab.anchor_x, lab.anchor_y = "LEFT", "TOP"
    tmp = tempfile.mkdtemp(prefix="intro_tira_")
    ims = v.render.image_settings
    ims.media_type, ims.file_format, ims.color_mode = "IMAGE", "PNG", "RGB"
    w, h = v.render.resolution_x, v.render.resolution_y
    filas = math.ceil(len(tiempos_ms) / cols)
    W, H = cols * w + (cols + 1) * hueco, filas * h + (filas + 1) * hueco
    lienzo = np.full((H, W, 4), 0.16, dtype=np.float32)
    lienzo[..., 3] = 1
    for i, t in enumerate(tiempos_ms):
        f = min(cuadro(t, fps), n - 1)
        lab.text = f"{f / fps:.2f} s".replace(".", ",")
        _render_rango(v, f, f, os.path.join(tmp, f"t{i}_####"))
        arch = [x for x in os.listdir(tmp) if x.startswith(f"t{i}_")][0]
        img = bpy.data.images.load(os.path.join(tmp, arch))
        px = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        bpy.data.images.remove(img)
        fila, col = divmod(i, cols)
        x = hueco + col * (w + hueco)
        y = H - (hueco + fila * (h + hueco)) - h        # pixels de Blender van de abajo hacia arriba
        lienzo[y:y + h, x:x + w] = px.reshape(h, w, 4)
    se.strips.remove(lab)
    for st in silenciados:
        st.mute = False
    out = bpy.data.images.new("tira", W, H, alpha=False)
    out.pixels.foreach_set(lienzo.ravel())
    out.filepath_raw = ruta
    out.file_format = "PNG"
    out.save()
    bpy.data.images.remove(out)
    shutil.rmtree(tmp, ignore_errors=True)
    v.frame_start, v.frame_end = 0, n - 1


def medir(carpeta, prefijo):
    arch = sorted(f for f in os.listdir(carpeta) if f.startswith(prefijo) and f.endswith(".png"))
    total = sum(os.path.getsize(os.path.join(carpeta, f)) for f in arch)
    return len(arch), total


# ---------------------------------------------------------------- flujo común

def terminar(a, p, sc, v, carpeta, prefijo, n_assets, digitos, generar=None, un_cuadro=None):
    """Pruebas de un cuadro, guardado de escena.blend y render completo según los argumentos.
    `generar(carpeta_cuadros)` y `un_cuadro(f, salida)` reemplazan el render directo de la
    escena cuando el concepto arma sus cuadros de otra forma (C: dos pases + composición)."""
    v["duracion_ms"] = p["duracion_ms"]
    if a.cuadro is not None or a.preview_cuadro is not None:
        escena, lista, modo = (sc, a.cuadro, "BW") if a.cuadro is not None else (v, a.preview_cuadro, "RGB")
        cuadros = [int(x) for x in lista.split(",")]
        salida = a.salida or os.path.join(tempfile.gettempdir(), "intro_prueba.png")
        for f in cuadros:
            dest = salida if len(cuadros) == 1 else os.path.join(salida, f"c_{f:03d}.png")
            if a.cuadro is not None and un_cuadro:
                un_cuadro(f, dest)
            else:
                render_un_cuadro(escena, f, dest, modo)
            print(f"[intro] cuadro de prueba {f} -> {dest}")
        return
    blend = os.path.join(carpeta, "escena.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
    print(f"[intro] escena guardada -> {blend}")
    if not a.render:
        return
    t0 = time.time()
    cuadros_dir = os.path.join(carpeta, "cuadros")
    if generar:
        generar(cuadros_dir)
    else:
        render_cuadros(sc, cuadros_dir, prefijo, n_assets, digitos)
    t_assets = time.time() - t0
    render_mp4(v, os.path.join(carpeta, "preview.mp4"))
    render_tira(v, p, p["tira_ms"], os.path.join(carpeta, "tira.png"))
    n, total = medir(cuadros_dir, prefijo)
    med = {"assets_png": n, "bytes": total, "mb": round(total / 1048576, 3),
           "render_assets_s": round(t_assets, 1), "render_total_s": round(time.time() - t0, 1),
           "blender": bpy.app.version_string}
    with open(os.path.join(carpeta, "medidas.json"), "w", encoding="utf-8") as fh:
        json.dump(med, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"[intro] listo: {med}")


# ---------------------------------------------------------------- franjas (PNG gris de 8 bits, sin PIL)

def _leer_png_gris(ruta):
    import struct
    import zlib
    with open(ruta, "rb") as fh:
        d = fh.read()
    pos, idat, ancho, alto = 8, b"", 0, 0
    while pos < len(d):
        n, tipo = struct.unpack(">I4s", d[pos:pos + 8])
        cuerpo = d[pos + 8:pos + 8 + n]
        if tipo == b"IHDR":
            ancho, alto, prof, ct, _, _, ent = struct.unpack(">IIBBBBB", cuerpo)
            assert (prof, ct, ent) == (8, 0, 0), "franjas: se espera PNG gris de 8 bits sin entrelazado"
        elif tipo == b"IDAT":
            idat += cuerpo
        pos += 12 + n
    raw = zlib.decompress(idat)
    img = np.zeros((alto, ancho), dtype=np.uint8)
    prev = np.zeros(ancho, dtype=np.int32)
    for y in range(alto):
        f = raw[y * (ancho + 1)]
        fila = np.frombuffer(raw, dtype=np.uint8, count=ancho, offset=y * (ancho + 1) + 1).astype(np.int32)
        if f == 0:
            cur = fila
        elif f == 1:    # Sub
            cur = np.cumsum(fila) & 255
        elif f == 2:    # Up
            cur = (fila + prev) & 255
        else:           # Average (3) y Paeth (4): dependen del pixel anterior
            cur = np.zeros(ancho, dtype=np.int32)
            a = 0
            for x in range(ancho):
                b = int(prev[x])
                c = int(prev[x - 1]) if x else 0
                if f == 3:
                    pred = (a + b) >> 1
                else:
                    p_ = a + b - c
                    pa, pb, pc = abs(p_ - a), abs(p_ - b), abs(p_ - c)
                    pred = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                a = (int(fila[x]) + pred) & 255
                cur[x] = a
        img[y] = cur
        prev = cur
    return img


def _escribir_png_gris(ruta, img):
    import struct
    import zlib

    def trozo(t, c):
        return struct.pack(">I", len(c)) + t + c + struct.pack(">I", zlib.crc32(t + c) & 0xFFFFFFFF)
    alto, ancho = img.shape
    filas = b"".join(b"\x00" + img[y].tobytes() for y in range(alto))
    with open(ruta, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + trozo(b"IHDR", struct.pack(">IIBBBBB", ancho, alto, 8, 0, 0, 0, 0))
                 + trozo(b"IDAT", zlib.compress(filas, 9)) + trozo(b"IEND", b""))


def partir_png(ruta, base, n):
    """Parte un PNG gris de 8 bits en n franjas horizontales (de arriba abajo): base_0.png … base_{n-1}.png.
    Cada franja se decodifica por separado en la app (ver intro.py: "franjas")."""
    img = _leer_png_gris(ruta)
    h = img.shape[0]
    cortes = [round(k * h / n) for k in range(n + 1)]
    for k in range(n):
        _escribir_png_gris(f"{base}_{k}.png", img[cortes[k]:cortes[k + 1]])
