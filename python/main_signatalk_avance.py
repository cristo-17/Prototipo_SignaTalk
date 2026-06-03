import threading
import traceback
import customtkinter as ctk
import cv2
from PIL import Image

import voice_tools
from auth_db import (
    inicializar_bd,
    validar_login,
    listar_usuarios,
    obtener_usuario,
    guardar_usuario,
    listar_perfiles,
    guardar_perfil,
    obtener_velocidad_usuario,
    listar_gestos,
    guardar_gesto,
    obtener_gesto_por_nombre,
    guardar_traduccion,
    listar_traducciones,
    listar_frases,
    guardar_frase,
)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# =========================
# HELPERS UI
# =========================

def es_admin(master) -> bool:
    usuario = getattr(master, "usuario_actual", None) or {}
    return (usuario.get("rol") or "usuario").strip().lower() == "admin"


def etiqueta(parent, texto):
    ctk.CTkLabel(parent, text=texto, anchor="w", font=("Segoe UI", 12, "bold")).pack(fill="x", padx=8, pady=(8, 2))


def entrada(parent, placeholder="", show=None, width=260):
    e = ctk.CTkEntry(parent, width=width, placeholder_text=placeholder, show=show)
    e.pack(fill="x", padx=8, pady=(0, 6))
    return e


def option(parent, valores, valor_inicial=None, width=260, command=None):
    var = ctk.StringVar(value=valor_inicial or valores[0])
    opt = ctk.CTkOptionMenu(parent, values=valores, variable=var, width=width, command=command)
    opt.pack(fill="x", padx=8, pady=(0, 6))
    return var, opt


def set_textbox(tb, texto):
    tb.configure(state="normal")
    tb.delete("1.0", "end")
    tb.insert("1.0", texto or "")
    tb.configure(state="disabled")


def limpiar_entry(e):
    e.delete(0, "end")


class SignaTalkApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SIGNATALK - 5 Formularios PostgreSQL")
        self.geometry("1120x720")
        self.minsize(1000, 640)
        self.usuario_actual = None
        self.db_ok, self.db_msg = inicializar_bd()
        self.show_frame(LoginFrame)

    def show_frame(self, frame_class):
        for widget in self.winfo_children():
            widget.destroy()
        try:
            frame = frame_class(self)
        except Exception as e:
            traceback.print_exc()
            frame = ErrorFrame(self, "No se pudo abrir la pantalla", repr(e))
        frame.pack(fill="both", expand=True)

    def iniciar_sesion(self, usuario_data):
        self.usuario_actual = dict(usuario_data)
        self.show_frame(MenuFrame)

    def cerrar_sesion(self):
        self.usuario_actual = None
        self.show_frame(LoginFrame)


class BaseFrame(ctk.CTkFrame):
    def titulo(self, titulo, subtitulo=""):
        ctk.CTkLabel(self, text=titulo, font=("Segoe UI", 26, "bold")).pack(pady=(14, 4))
        if subtitulo:
            ctk.CTkLabel(self, text=subtitulo, font=("Segoe UI", 13), wraplength=900).pack(pady=(0, 10))

    def nav_bottom(self):
        nav = ctk.CTkFrame(self)
        nav.pack(side="bottom", fill="x", padx=18, pady=12)
        ctk.CTkButton(nav, text="Volver al menu principal", command=lambda: self.master.show_frame(MenuFrame), width=190).pack(side="left", padx=8, pady=8)
        ctk.CTkButton(nav, text="Cerrar sesion", command=self.master.cerrar_sesion, width=160).pack(side="left", padx=8, pady=8)
        ctk.CTkButton(nav, text="Salir", command=self.master.quit, fg_color="#d90429", width=120).pack(side="right", padx=8, pady=8)
        return nav

    def usuario_id_para_form(self, combo_var=None, mapa=None):
        if not es_admin(self.master):
            return self.master.usuario_actual["id"]
        if combo_var and mapa:
            return mapa.get(combo_var.get())
        return self.master.usuario_actual["id"]


class ErrorFrame(BaseFrame):
    def __init__(self, master, titulo_error="Error", detalle=""):
        super().__init__(master)
        self.titulo("SIGNATALK", titulo_error)
        ctk.CTkLabel(self, text=detalle, text_color="#ff9f1c", wraplength=900).pack(pady=18, padx=20)
        ctk.CTkButton(self, text="Volver al login", command=lambda: master.show_frame(LoginFrame), width=180).pack(pady=12)


# =========================
# LOGIN Y MENU
# =========================
class LoginFrame(BaseFrame):
    def __init__(self, master):
        super().__init__(master)
        self.titulo("SIGNATALK", "Login conectado a PostgreSQL")
        if not master.db_ok:
            ctk.CTkLabel(self, text=master.db_msg, text_color="#ff9f1c", wraplength=900).pack(pady=8)

        card = ctk.CTkFrame(self)
        card.pack(pady=18, padx=50)

        etiqueta(card, "Tipo de acceso:")
        self.rol_var, _ = option(card, ["usuario", "admin"], "usuario", width=340)

        etiqueta(card, "Usuario:")
        self.usuario_entry = entrada(card, "Ingrese su usuario", width=340)

        etiqueta(card, "Contrasena:")
        self.password_entry = entrada(card, "Ingrese su contrasena", show="*", width=340)

        self.mensaje_label = ctk.CTkLabel(card, text="", wraplength=360)
        self.mensaje_label.pack(pady=8)

        self.login_button = ctk.CTkButton(card, text="Ingresar", command=self.validar, width=180)
        self.login_button.pack(pady=8)
        ctk.CTkButton(card, text="Salir", command=master.quit, fg_color="#d90429", width=180).pack(pady=(4, 18))

    def validar(self):
        usuario = self.usuario_entry.get()
        password = self.password_entry.get()
        rol = self.rol_var.get()
        self.login_button.configure(state="disabled", text="Validando...")
        self.mensaje_label.configure(text="Consultando PostgreSQL...")

        def run():
            ok, msg, data = validar_login(usuario, password, rol)
            self.after(0, lambda: self.procesar(ok, msg, data))

        threading.Thread(target=run, daemon=True).start()

    def procesar(self, ok, msg, data):
        if ok:
            self.mensaje_label.configure(text="Acceso correcto. Abriendo menu...")
            self.after(250, lambda: self.master.iniciar_sesion(data))
        else:
            self.login_button.configure(state="normal", text="Ingresar")
            self.mensaje_label.configure(text=msg)
            self.password_entry.delete(0, "end")


class MenuFrame(BaseFrame):
    def __init__(self, master):
        super().__init__(master)
        usuario = master.usuario_actual or {}
        nombre = usuario.get("nombre_completo") or usuario.get("usuario")
        rol = usuario.get("rol") or "usuario"
        self.titulo("SIGNATALK", f"Sesion activa: {nombre} | Rol: {rol}")

        # Barra inferior fija. Se crea antes del contenido para que siempre sea visible,
        # incluso cuando el administrador tenga mas opciones en pantalla.
        nav = ctk.CTkFrame(self)
        nav.pack(side="bottom", fill="x", padx=18, pady=(6, 12))
        ctk.CTkButton(
            nav,
            text="Cerrar sesion",
            command=master.cerrar_sesion,
            width=170,
        ).pack(side="left", padx=8, pady=8)
        ctk.CTkButton(
            nav,
            text="Salir",
            command=master.quit,
            fg_color="#d90429",
            width=130,
        ).pack(side="right", padx=8, pady=8)

        cont = ctk.CTkScrollableFrame(self, width=1020, height=560)
        cont.pack(fill="both", expand=True, padx=24, pady=(8, 4))

        forms = []
        if es_admin(master):
            forms.append(("Formulario 1: Usuarios", "Crear y modificar usuarios. Rol visible por cuenta.", UsuariosFrame))
        forms.extend([
            ("Formulario 2: Perfiles", "DNI, correo, telefono, direccion y velocidad de voz.", PerfilesFrame),
            ("Formulario 3: Gestos demo", "Gestos predeterminados y propios por usuario.", GestosFrame),
            ("Formulario 4: Traducciones", "Camara, texto a voz y voz a texto.", TraduccionesFrame),
            ("Formulario 5: Frases frecuentes", "Frases utiles propias de cada usuario.", FrasesFrame),
        ])

        for titulo, desc, frame_class in forms:
            card = ctk.CTkFrame(cont)
            card.pack(fill="x", padx=16, pady=7)
            ctk.CTkLabel(
                card,
                text=titulo,
                font=("Segoe UI", 16, "bold"),
                anchor="w",
            ).pack(fill="x", padx=14, pady=(10, 3))
            ctk.CTkLabel(
                card,
                text=desc,
                anchor="w",
                wraplength=850,
            ).pack(fill="x", padx=14, pady=(0, 6))
            ctk.CTkButton(
                card,
                text="Abrir",
                command=lambda f=frame_class: master.show_frame(f),
                width=140,
            ).pack(pady=(0, 10))


# =========================
# FORMULARIO 1 USUARIOS
# =========================
class UsuariosFrame(BaseFrame):
    def __init__(self, master):
        super().__init__(master)
        if not es_admin(master):
            self.titulo("Acceso restringido", "Solo el administrador puede usar el Formulario 1.")
            self.nav_bottom()
            return

        self.id_editando = None
        self.titulo("Formulario 1: Usuarios", "Crear y modificar usuarios. La lista se refleja en el Formulario 2.")
        self.nav_bottom()

        body = ctk.CTkFrame(self)
        body.pack(fill="both", expand=True, padx=18, pady=8)

        form = ctk.CTkFrame(body)
        form.pack(side="left", fill="y", padx=(0, 12), pady=6)

        etiqueta(form, "Usuario:")
        self.usuario_entry = entrada(form, "Ejemplo: usuario5", width=300)
        etiqueta(form, "Nombre completo:")
        self.nombre_entry = entrada(form, "Nombre completo", width=300)
        etiqueta(form, "Rol:")
        self.rol_var, _ = option(form, ["usuario", "admin"], "usuario", width=300)
        etiqueta(form, "Contrasena:")
        self.password_entry = entrada(form, "Obligatoria al crear", show="*", width=300)
        etiqueta(form, "Confirmar contrasena:")
        self.confirmar_entry = entrada(form, "Repetir contrasena", show="*", width=300)

        self.mensaje = ctk.CTkLabel(form, text="", wraplength=300)
        self.mensaje.pack(pady=6)
        ctk.CTkButton(form, text="Guardar usuario", command=self.guardar, width=180).pack(pady=4)
        ctk.CTkButton(form, text="Limpiar campos", command=self.limpiar, width=180).pack(pady=4)
        ctk.CTkButton(form, text="Volver al menu principal", command=lambda: master.show_frame(MenuFrame), width=180).pack(pady=4)

        self.scroll = ctk.CTkScrollableFrame(body, width=690)
        self.scroll.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=6)
        self.cargar()

    def limpiar(self):
        self.id_editando = None
        for e in [self.usuario_entry, self.nombre_entry, self.password_entry, self.confirmar_entry]:
            limpiar_entry(e)
        self.rol_var.set("usuario")
        self.mensaje.configure(text="Campos limpios. Puedes crear un nuevo usuario.")

    def guardar(self):
        ok, msg = guardar_usuario(
            self.id_editando,
            self.usuario_entry.get(),
            self.nombre_entry.get(),
            self.rol_var.get(),
            self.password_entry.get(),
            self.confirmar_entry.get(),
        )
        self.mensaje.configure(text=msg)
        if ok:
            self.limpiar()
            self.cargar()

    def cargar(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        ok, msg, usuarios = listar_usuarios(True, self.master.usuario_actual["id"])
        if not ok:
            ctk.CTkLabel(self.scroll, text=msg).pack(pady=8)
            return
        for u in usuarios:
            card = ctk.CTkFrame(self.scroll)
            card.pack(fill="x", padx=8, pady=6)
            texto = f"ID {u['id']} | Usuario: {u['usuario']} | Nombre: {u['nombre_completo']} | Rol: {u['rol']}"
            ctk.CTkLabel(card, text=texto, anchor="w", font=("Segoe UI", 13, "bold"), wraplength=630).pack(fill="x", padx=10, pady=(8, 4))
            ctk.CTkButton(card, text="Cargar para modificar", command=lambda uu=u: self.cargar_form(uu), width=170).pack(padx=10, pady=(0, 8))

    def cargar_form(self, u):
        self.id_editando = u["id"]
        self.usuario_entry.delete(0, "end")
        self.usuario_entry.insert(0, u["usuario"])
        self.nombre_entry.delete(0, "end")
        self.nombre_entry.insert(0, u["nombre_completo"] or "")
        self.rol_var.set(u["rol"] or "usuario")
        self.password_entry.delete(0, "end")
        self.confirmar_entry.delete(0, "end")
        self.mensaje.configure(text="Usuario cargado. Modifica los campos y guarda. La contrasena es opcional al editar.")


# =========================
# FORMULARIO 2 PERFILES
# =========================
class PerfilesFrame(BaseFrame):
    def __init__(self, master):
        super().__init__(master)
        self.id_usuario_seleccionado = master.usuario_actual["id"]
        self.titulo("Formulario 2: Perfiles de usuario", "Cada usuario tiene su propio perfil. El admin puede ver quien creo cada registro.")
        self.nav_bottom()

        body = ctk.CTkFrame(self)
        body.pack(fill="both", expand=True, padx=18, pady=8)

        form = ctk.CTkFrame(body)
        form.pack(side="left", fill="y", padx=(0, 12), pady=6)

        ok, _, usuarios = listar_usuarios(es_admin(master), master.usuario_actual["id"])
        self.usuario_map = {f"{u['usuario']} - {u['nombre_completo']}": u["id"] for u in usuarios}
        if not self.usuario_map:
            self.usuario_map = {master.usuario_actual["usuario"]: master.usuario_actual["id"]}

        etiqueta(form, "Usuario del perfil:")
        self.usuario_var, _ = option(form, list(self.usuario_map.keys()), list(self.usuario_map.keys())[0], width=320)
        etiqueta(form, "DNI:")
        self.dni_entry = entrada(form, "8 digitos", width=320)
        etiqueta(form, "Correo:")
        self.correo_entry = entrada(form, "correo@dominio.com", width=320)
        etiqueta(form, "Telefono:")
        self.telefono_entry = entrada(form, "9 digitos", width=320)
        etiqueta(form, "Direccion:")
        self.direccion_entry = entrada(form, "Direccion del usuario", width=320)
        etiqueta(form, "Velocidad de voz:")
        self.velocidad_var, _ = option(form, ["lenta", "normal", "rapida"], "normal", width=320)

        self.mensaje = ctk.CTkLabel(form, text="", wraplength=320)
        self.mensaje.pack(pady=6)
        ctk.CTkButton(form, text="Guardar perfil", command=self.guardar, width=180).pack(pady=4)
        ctk.CTkButton(form, text="Limpiar campos", command=self.limpiar, width=180).pack(pady=4)
        ctk.CTkButton(form, text="Volver al menu principal", command=lambda: master.show_frame(MenuFrame), width=180).pack(pady=4)

        self.scroll = ctk.CTkScrollableFrame(body, width=690)
        self.scroll.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=6)
        self.cargar()

    def limpiar(self):
        for e in [self.dni_entry, self.correo_entry, self.telefono_entry, self.direccion_entry]:
            limpiar_entry(e)
        self.velocidad_var.set("normal")
        self.mensaje.configure(text="Campos limpios.")

    def guardar(self):
        id_usuario = self.usuario_map.get(self.usuario_var.get(), self.master.usuario_actual["id"])
        if not es_admin(self.master) and id_usuario != self.master.usuario_actual["id"]:
            self.mensaje.configure(text="No puedes modificar perfiles de otros usuarios.")
            return
        ok, msg = guardar_perfil(
            id_usuario,
            self.dni_entry.get(),
            self.correo_entry.get(),
            self.telefono_entry.get(),
            self.direccion_entry.get(),
            self.velocidad_var.get(),
        )
        self.mensaje.configure(text=msg)
        if ok:
            self.cargar()

    def cargar(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        ok, msg, perfiles = listar_perfiles(es_admin(self.master), self.master.usuario_actual["id"])
        if not ok:
            ctk.CTkLabel(self.scroll, text=msg).pack(pady=8)
            return
        for p in perfiles:
            card = ctk.CTkFrame(self.scroll)
            card.pack(fill="x", padx=8, pady=6)
            base = f"Usuario: {p['usuario']} | Nombre: {p['nombre_completo']} | Rol: {p['rol']}"
            ctk.CTkLabel(card, text=base, anchor="w", font=("Segoe UI", 13, "bold"), wraplength=640).pack(fill="x", padx=10, pady=(8, 4))
            detalle = f"DNI: {p.get('dni') or 'Sin perfil'} | Telefono: {p.get('telefono') or '-'} | Correo: {p.get('correo') or '-'}\nDireccion: {p.get('direccion') or '-'} | Velocidad: {p.get('velocidad_voz') or '-'}"
            ctk.CTkLabel(card, text=detalle, anchor="w", wraplength=640, justify="left").pack(fill="x", padx=10, pady=4)
            ctk.CTkButton(card, text="Cargar perfil", command=lambda pp=p: self.cargar_form(pp), width=150).pack(padx=10, pady=(0, 8))

    def cargar_form(self, p):
        self.id_usuario_seleccionado = p["id_usuario"]
        for label, uid in self.usuario_map.items():
            if uid == p["id_usuario"]:
                self.usuario_var.set(label)
                break
        self.limpiar()
        if p.get("dni"):
            self.dni_entry.insert(0, p.get("dni") or "")
            self.correo_entry.insert(0, p.get("correo") or "")
            self.telefono_entry.insert(0, p.get("telefono") or "")
            self.direccion_entry.insert(0, p.get("direccion") or "")
            self.velocidad_var.set(p.get("velocidad_voz") or "normal")
        self.mensaje.configure(text="Perfil cargado para modificar.")


# =========================
# FORMULARIO 3 GESTOS
# =========================
class GestosFrame(BaseFrame):
    def __init__(self, master):
        super().__init__(master)
        self.id_editando = None
        self.titulo("Formulario 3: Gestos demo", "Los gestos pertenecen a cada usuario. Editar uno no afecta a los demas usuarios.")
        self.nav_bottom()

        body = ctk.CTkFrame(self)
        body.pack(fill="both", expand=True, padx=18, pady=8)
        form = ctk.CTkFrame(body)
        form.pack(side="left", fill="y", padx=(0, 12), pady=6)

        ok, _, usuarios = listar_usuarios(es_admin(master), master.usuario_actual["id"])
        self.usuario_map = {f"{u['usuario']} - {u['nombre_completo']}": u["id"] for u in usuarios}
        if not self.usuario_map:
            self.usuario_map = {master.usuario_actual["usuario"]: master.usuario_actual["id"]}

        etiqueta(form, "Usuario propietario:")
        self.usuario_var, self.usuario_combo = option(
            form,
            list(self.usuario_map.keys()),
            list(self.usuario_map.keys())[0],
            width=320,
            command=lambda _: self.cambiar_usuario_propietario(),
        )
        etiqueta(form, "Nombre del gesto:")
        self.nombre_entry = entrada(form, "Ejemplo: HOLA", width=320)
        etiqueta(form, "Texto traducido:")
        self.texto_entry = entrada(form, "Texto resultado", width=320)
        etiqueta(form, "Categoria:")
        self.categoria_entry = entrada(form, "Saludo, Salud, Emergencia...", width=320)
        etiqueta(form, "Descripcion:")
        self.descripcion_entry = entrada(form, "Descripcion breve", width=320)

        self.mensaje = ctk.CTkLabel(form, text="", wraplength=320)
        self.mensaje.pack(pady=6)
        ctk.CTkButton(form, text="Guardar gesto", command=self.guardar, width=180).pack(pady=4)
        ctk.CTkButton(form, text="Limpiar campos", command=self.limpiar, width=180).pack(pady=4)
        ctk.CTkButton(form, text="Volver al menu principal", command=lambda: master.show_frame(MenuFrame), width=180).pack(pady=4)

        self.scroll = ctk.CTkScrollableFrame(body, width=690)
        self.scroll.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=6)
        self.cargar()

    def limpiar(self):
        self.id_editando = None
        for e in [self.nombre_entry, self.texto_entry, self.categoria_entry, self.descripcion_entry]:
            limpiar_entry(e)
        self.mensaje.configure(text="Campos limpios.")

    def cambiar_usuario_propietario(self):
        self.id_editando = None
        for e in [self.nombre_entry, self.texto_entry, self.categoria_entry, self.descripcion_entry]:
            limpiar_entry(e)
        self.mensaje.configure(text="Mostrando solo los gestos del usuario propietario seleccionado.")
        self.cargar()

    def guardar(self):
        id_usuario = self.usuario_map.get(self.usuario_var.get(), self.master.usuario_actual["id"])
        if not es_admin(self.master) and id_usuario != self.master.usuario_actual["id"]:
            self.mensaje.configure(text="No puedes crear gestos para otros usuarios.")
            return
        ok, msg = guardar_gesto(
            self.id_editando,
            id_usuario,
            self.nombre_entry.get(),
            self.texto_entry.get(),
            self.categoria_entry.get(),
            self.descripcion_entry.get(),
        )
        self.mensaje.configure(text=msg)
        if ok:
            self.limpiar()
            self.cargar()

    def cargar(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        ok, msg, gestos = listar_gestos(es_admin(self.master), self.master.usuario_actual["id"])
        if not ok:
            ctk.CTkLabel(self.scroll, text=msg).pack(pady=8)
            return
        id_filtrado = self.usuario_map.get(self.usuario_var.get(), self.master.usuario_actual["id"])
        gestos = [g for g in gestos if g.get("id_usuario") == id_filtrado]
        if not gestos:
            ctk.CTkLabel(self.scroll, text="No hay gestos registrados para el usuario seleccionado.").pack(pady=8)
            return
        for g in gestos:
            card = ctk.CTkFrame(self.scroll)
            card.pack(fill="x", padx=8, pady=6)
            header = f"Usuario: {g['usuario']} | Gesto: {g['nombre_gesto']} | Categoria: {g['categoria']}"
            ctk.CTkLabel(card, text=header, anchor="w", font=("Segoe UI", 13, "bold"), wraplength=640).pack(fill="x", padx=10, pady=(8, 4))
            ctk.CTkLabel(card, text=f"Texto: {g['texto_traducido']}\nDescripcion: {g.get('descripcion') or ''}", anchor="w", wraplength=640, justify="left").pack(fill="x", padx=10, pady=4)
            ctk.CTkButton(card, text="Cargar para modificar", command=lambda gg=g: self.cargar_form(gg), width=170).pack(padx=10, pady=(0, 8))

    def cargar_form(self, g):
        self.id_editando = g["id"]
        for label, uid in self.usuario_map.items():
            if uid == g["id_usuario"]:
                self.usuario_var.set(label)
                break
        self.nombre_entry.delete(0, "end")
        self.nombre_entry.insert(0, g["nombre_gesto"])
        self.texto_entry.delete(0, "end")
        self.texto_entry.insert(0, g["texto_traducido"])
        self.categoria_entry.delete(0, "end")
        self.categoria_entry.insert(0, g["categoria"])
        self.descripcion_entry.delete(0, "end")
        self.descripcion_entry.insert(0, g.get("descripcion") or "")
        self.mensaje.configure(text="Gesto cargado. La modificacion solo afectara al usuario propietario de este registro.")


# =========================
# FORMULARIO 4 TRADUCCIONES
# =========================
class TraduccionesFrame(BaseFrame):
    def __init__(self, master):
        super().__init__(master)
        self.cap = None
        self.camera_running = False
        self.current_traducido = ""
        self.current_original = ""
        self.current_tipo = ""
        self.titulo("Formulario 4: Traducciones", "Camara/LSP demo, Texto a Voz y Voz a Texto. El historial es propio de cada usuario.")
        self.nav_bottom()

        self.body = ctk.CTkFrame(self)
        self.body.pack(fill="both", expand=True, padx=18, pady=8)

        self.tabs = ctk.CTkTabview(self.body)
        self.tabs.pack(fill="both", expand=True, padx=8, pady=8)
        self.tab_cam = self.tabs.add("1. Camara / LSP demo")
        self.tab_tts = self.tabs.add("2. Texto a Voz")
        self.tab_stt = self.tabs.add("3. Voz a Texto")

        self.crear_tab_camara()
        self.crear_tab_tts()
        self.crear_tab_stt()

        ctk.CTkLabel(self.body, text="Traducciones guardadas del usuario actual" + (" / todas para admin" if es_admin(master) else ""), font=("Segoe UI", 14, "bold")).pack(pady=(6, 2))
        self.scroll_hist = ctk.CTkScrollableFrame(self.body, height=150)
        self.scroll_hist.pack(fill="x", padx=8, pady=(2, 8))
        self.cargar_historial_visual()

    def crear_tab_camara(self):
        cont = ctk.CTkFrame(self.tab_cam)
        cont.pack(fill="both", expand=True, padx=8, pady=8)
        left = ctk.CTkFrame(cont)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8), pady=4)
        right = ctk.CTkFrame(cont)
        right.pack(side="left", fill="y", padx=(8, 0), pady=4)

        self.video_label = ctk.CTkLabel(left, text="Camara detenida", width=520, height=280)
        self.video_label.pack(fill="both", expand=True, padx=8, pady=8)
        btns = ctk.CTkFrame(left)
        btns.pack(pady=6)
        ctk.CTkButton(btns, text="Iniciar camara", command=self.iniciar_camara, width=140).pack(side="left", padx=5)
        ctk.CTkButton(btns, text="Detener camara", command=self.detener_camara, width=140).pack(side="left", padx=5)

        ok, _, gestos = listar_gestos(False, self.master.usuario_actual["id"])
        valores = [g["nombre_gesto"] for g in gestos] or ["HOLA"]
        etiqueta(right, "Gesto detectado para simular:")
        self.gesto_var, _ = option(right, valores, valores[0], width=280)
        ctk.CTkButton(right, text="Simular reconocimiento", command=self.simular_gesto, width=220).pack(pady=5)
        etiqueta(right, "Resultado visual:")
        self.resultado_cam = ctk.CTkTextbox(right, width=300, height=130)
        self.resultado_cam.pack(padx=8, pady=(0, 6))
        self.resultado_cam.configure(state="disabled")
        ctk.CTkButton(right, text="Reproducir resultado", command=self.reproducir_actual, width=220).pack(pady=5)
        ctk.CTkButton(right, text="Guardar en historial", command=self.guardar_actual, width=220).pack(pady=5)
        self.msg_cam = ctk.CTkLabel(right, text="", wraplength=300)
        self.msg_cam.pack(pady=5)

    def crear_tab_tts(self):
        cont = ctk.CTkFrame(self.tab_tts)
        cont.pack(fill="both", expand=True, padx=8, pady=8)
        etiqueta(cont, "Texto que se va a reproducir:")
        self.tts_entry = ctk.CTkTextbox(cont, height=90)
        self.tts_entry.pack(fill="x", padx=8, pady=(0, 6))
        etiqueta(cont, "Resultado / mensaje del sistema (solo visualizacion):")
        self.tts_result = ctk.CTkTextbox(cont, height=90)
        self.tts_result.pack(fill="x", padx=8, pady=(0, 6))
        self.tts_result.configure(state="disabled")
        btns = ctk.CTkFrame(cont)
        btns.pack(pady=8)
        ctk.CTkButton(btns, text="Reproducir", command=self.reproducir_tts, width=150).pack(side="left", padx=5)
        ctk.CTkButton(btns, text="Guardar en historial", command=self.guardar_tts, width=170).pack(side="left", padx=5)

    def crear_tab_stt(self):
        cont = ctk.CTkFrame(self.tab_stt)
        cont.pack(fill="both", expand=True, padx=8, pady=8)
        etiqueta(cont, "Texto reconocido desde voz (solo visualizacion):")
        self.stt_result = ctk.CTkTextbox(cont, height=120)
        self.stt_result.pack(fill="x", padx=8, pady=(0, 6))
        self.stt_result.configure(state="disabled")
        btns = ctk.CTkFrame(cont)
        btns.pack(pady=8)
        ctk.CTkButton(btns, text="Iniciar reconocimiento", command=self.reconocer_voz, width=180).pack(side="left", padx=5)
        ctk.CTkButton(btns, text="Guardar en historial", command=self.guardar_stt, width=170).pack(side="left", padx=5)

    def iniciar_camara(self):
        if self.cap is None:
            self.cap = cv2.VideoCapture(0)
        self.camera_running = True
        self.update_frame()

    def detener_camara(self):
        self.camera_running = False
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.video_label.configure(image=None, text="Camara detenida")

    def update_frame(self):
        if self.cap is not None and self.camera_running:
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame)
                img.thumbnail((520, 280))
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                self.video_label.configure(image=ctk_img, text="")
                self.video_label.image = ctk_img
            self.after(25, self.update_frame)

    def simular_gesto(self):
        ok, msg, gesto = obtener_gesto_por_nombre(self.master.usuario_actual["id"], self.gesto_var.get())
        if not ok or not gesto:
            self.msg_cam.configure(text=msg)
            return
        self.current_tipo = "LSP a texto demo"
        self.current_original = f"Gesto detectado: {gesto['nombre_gesto']}"
        self.current_traducido = gesto["texto_traducido"]
        set_textbox(self.resultado_cam, f"{self.current_original}\nTraduccion: {self.current_traducido}")
        self.msg_cam.configure(text="Gesto consultado desde los registros del usuario actual.")

    def reproducir_actual(self):
        if not self.current_traducido:
            self.msg_cam.configure(text="Primero simula un gesto.")
            return
        velocidad = obtener_velocidad_usuario(self.master.usuario_actual["id"])
        def run():
            msg = voice_tools.texto_a_voz(self.current_traducido, velocidad)
            self.after(0, lambda: self.msg_cam.configure(text=msg))
        threading.Thread(target=run, daemon=True).start()

    def guardar_actual(self):
        if not self.current_traducido:
            self.msg_cam.configure(text="No hay traduccion para guardar.")
            return
        ok, msg = guardar_traduccion(self.master.usuario_actual["id"], self.current_tipo, self.current_original, self.current_traducido)
        self.msg_cam.configure(text=msg)
        self.cargar_historial_visual()

    def reproducir_tts(self):
        texto = self.tts_entry.get("1.0", "end").strip()
        if not texto:
            set_textbox(self.tts_result, "Ingresa texto para reproducir.")
            return
        set_textbox(self.tts_result, "Reproduciendo texto...")
        velocidad = obtener_velocidad_usuario(self.master.usuario_actual["id"])
        def run():
            msg = voice_tools.texto_a_voz(texto, velocidad)
            self.after(0, lambda: set_textbox(self.tts_result, msg))
        threading.Thread(target=run, daemon=True).start()

    def guardar_tts(self):
        texto = self.tts_entry.get("1.0", "end").strip()
        if not texto:
            set_textbox(self.tts_result, "No hay texto para guardar.")
            return
        ok, msg = guardar_traduccion(self.master.usuario_actual["id"], "Texto a voz", "Texto escrito por usuario", texto)
        set_textbox(self.tts_result, msg)
        self.cargar_historial_visual()

    def reconocer_voz(self):
        set_textbox(self.stt_result, "Escuchando microfono...")
        def run():
            resultado = voice_tools.voz_a_texto()
            self.after(0, lambda: set_textbox(self.stt_result, resultado))
        threading.Thread(target=run, daemon=True).start()

    def guardar_stt(self):
        texto = self.stt_result.get("1.0", "end").strip().replace("Texto reconocido: ", "")
        if not texto or texto.startswith("Escuchando"):
            set_textbox(self.stt_result, "Primero realiza el reconocimiento de voz.")
            return
        ok, msg = guardar_traduccion(self.master.usuario_actual["id"], "Voz a texto", "Audio capturado desde microfono", texto)
        set_textbox(self.stt_result, msg)
        self.cargar_historial_visual()

    def cargar_historial_visual(self):
        for w in self.scroll_hist.winfo_children():
            w.destroy()
        ok, msg, filas = listar_traducciones(es_admin(self.master), self.master.usuario_actual["id"])
        if not ok:
            ctk.CTkLabel(self.scroll_hist, text=msg).pack(pady=6)
            return
        if not filas:
            ctk.CTkLabel(self.scroll_hist, text="No hay traducciones guardadas.").pack(pady=6)
            return
        for f in filas[:10]:
            texto = f"Usuario: {f['usuario']} | {f['tipo_traduccion']} | {f['texto_traducido']}"
            ctk.CTkLabel(self.scroll_hist, text=texto, anchor="w", wraplength=980, justify="left").pack(fill="x", padx=8, pady=3)

    def destroy(self):
        self.detener_camara()
        super().destroy()


# =========================
# FORMULARIO 5 FRASES
# =========================
class FrasesFrame(BaseFrame):
    def __init__(self, master):
        super().__init__(master)
        self.id_editando = None
        self.titulo("Formulario 5: Frases frecuentes", "Cada usuario tiene sus propias frases. El admin ve el propietario de cada registro.")
        self.nav_bottom()

        body = ctk.CTkFrame(self)
        body.pack(fill="both", expand=True, padx=18, pady=8)
        form = ctk.CTkFrame(body)
        form.pack(side="left", fill="y", padx=(0, 12), pady=6)

        ok, _, usuarios = listar_usuarios(es_admin(master), master.usuario_actual["id"])
        self.usuario_map = {f"{u['usuario']} - {u['nombre_completo']}": u["id"] for u in usuarios}
        if not self.usuario_map:
            self.usuario_map = {master.usuario_actual["usuario"]: master.usuario_actual["id"]}

        etiqueta(form, "Usuario propietario:")
        self.usuario_var, self.usuario_combo = option(
            form,
            list(self.usuario_map.keys()),
            list(self.usuario_map.keys())[0],
            width=320,
            command=lambda _: self.cambiar_usuario_propietario(),
        )
        etiqueta(form, "Frase frecuente:")
        self.frase_entry = entrada(form, "Ejemplo: Necesito ayuda", width=320)
        etiqueta(form, "Categoria:")
        self.categoria_entry = entrada(form, "Emergencia, Salud, Cortesia...", width=320)
        etiqueta(form, "Descripcion:")
        self.descripcion_entry = entrada(form, "Descripcion breve", width=320)

        self.mensaje = ctk.CTkLabel(form, text="", wraplength=320)
        self.mensaje.pack(pady=6)
        ctk.CTkButton(form, text="Guardar frase", command=self.guardar, width=180).pack(pady=4)
        ctk.CTkButton(form, text="Limpiar campos", command=self.limpiar, width=180).pack(pady=4)
        ctk.CTkButton(form, text="Volver al menu principal", command=lambda: master.show_frame(MenuFrame), width=180).pack(pady=4)

        self.scroll = ctk.CTkScrollableFrame(body, width=690)
        self.scroll.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=6)
        self.cargar()

    def limpiar(self):
        self.id_editando = None
        for e in [self.frase_entry, self.categoria_entry, self.descripcion_entry]:
            limpiar_entry(e)
        self.mensaje.configure(text="Campos limpios.")

    def cambiar_usuario_propietario(self):
        self.id_editando = None
        for e in [self.frase_entry, self.categoria_entry, self.descripcion_entry]:
            limpiar_entry(e)
        self.mensaje.configure(text="Mostrando solo las frases del usuario propietario seleccionado.")
        self.cargar()

    def guardar(self):
        id_usuario = self.usuario_map.get(self.usuario_var.get(), self.master.usuario_actual["id"])
        if not es_admin(self.master) and id_usuario != self.master.usuario_actual["id"]:
            self.mensaje.configure(text="No puedes crear frases para otros usuarios.")
            return
        ok, msg = guardar_frase(self.id_editando, id_usuario, self.frase_entry.get(), self.categoria_entry.get(), self.descripcion_entry.get())
        self.mensaje.configure(text=msg)
        if ok:
            self.limpiar()
            self.cargar()

    def cargar(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        ok, msg, frases = listar_frases(es_admin(self.master), self.master.usuario_actual["id"])
        if not ok:
            ctk.CTkLabel(self.scroll, text=msg).pack(pady=8)
            return
        id_filtrado = self.usuario_map.get(self.usuario_var.get(), self.master.usuario_actual["id"])
        frases = [f for f in frases if f.get("id_usuario") == id_filtrado]
        if not frases:
            ctk.CTkLabel(self.scroll, text="No hay frases registradas para el usuario seleccionado.").pack(pady=8)
            return
        for f in frases:
            card = ctk.CTkFrame(self.scroll)
            card.pack(fill="x", padx=8, pady=6)
            header = f"Usuario: {f['usuario']} | Categoria: {f['categoria']}"
            ctk.CTkLabel(card, text=header, anchor="w", font=("Segoe UI", 13, "bold"), wraplength=640).pack(fill="x", padx=10, pady=(8, 4))
            ctk.CTkLabel(card, text=f"Frase: {f['frase']}\nDescripcion: {f.get('descripcion') or ''}", anchor="w", wraplength=640, justify="left").pack(fill="x", padx=10, pady=4)
            actions = ctk.CTkFrame(card)
            actions.pack(fill="x", padx=10, pady=(0, 8))
            ctk.CTkButton(actions, text="Cargar para modificar", command=lambda ff=f: self.cargar_form(ff), width=170).pack(side="left", padx=5)
            ctk.CTkButton(actions, text="Reproducir", command=lambda texto=f['frase']: self.reproducir(texto), width=120).pack(side="left", padx=5)

    def cargar_form(self, f):
        self.id_editando = f["id"]
        for label, uid in self.usuario_map.items():
            if uid == f["id_usuario"]:
                self.usuario_var.set(label)
                break
        self.frase_entry.delete(0, "end")
        self.frase_entry.insert(0, f["frase"])
        self.categoria_entry.delete(0, "end")
        self.categoria_entry.insert(0, f["categoria"])
        self.descripcion_entry.delete(0, "end")
        self.descripcion_entry.insert(0, f.get("descripcion") or "")
        self.mensaje.configure(text="Frase cargada. La modificacion solo afectara al usuario propietario.")

    def reproducir(self, texto):
        velocidad = obtener_velocidad_usuario(self.master.usuario_actual["id"])
        self.mensaje.configure(text="Reproduciendo frase...")
        def run():
            msg = voice_tools.texto_a_voz(texto, velocidad)
            self.after(0, lambda: self.mensaje.configure(text=msg))
        threading.Thread(target=run, daemon=True).start()


if __name__ == "__main__":
    app = SignaTalkApp()
    app.mainloop()
