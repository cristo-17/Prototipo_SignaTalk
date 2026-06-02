import threading
import traceback
import customtkinter as ctk
import cv2
from PIL import Image, ImageTk

import voice_tools
from psycopg2.extras import RealDictCursor

from auth_db import (
    get_connection,
    inicializar_bd,
    crear_usuario,
    validar_login,
    obtener_usuario,
    actualizar_perfil,
    obtener_configuracion,
    guardar_configuracion,
    listar_gestos_demo,
    obtener_gesto_demo,
    guardar_traduccion,
    listar_historial,
    eliminar_historial,
    obtener_estadisticas_usuario,
)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def escala_tamano_texto(tamano: str) -> float:
    """Convierte la preferencia de tamaño de texto en escala visual real."""
    return {
        "pequeño": 0.90,
        "normal": 1.00,
        "grande": 1.18,
    }.get((tamano or "normal").lower(), 1.00)


class SignaTalkApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SIGNATALK - Avance con PostgreSQL")
        self.geometry("500x520")
        self.minsize(460, 500)
        self.usuario_actual = None
        self.tamano_texto_actual = "normal"
        self.velocidad_voz_actual = "normal"
        self.db_ok, self.db_msg = inicializar_bd()
        self.show_frame(LoginFrame)

    def show_frame(self, frame_class):
        """Cambia de pantalla sin dejar la app congelada si una vista falla."""
        for widget in self.winfo_children():
            widget.destroy()
        try:
            frame = frame_class(self)
        except Exception as e:
            traceback.print_exc()
            frame = ErrorFrame(self, f"No se pudo abrir la pantalla: {frame_class.__name__}", repr(e))
        frame.pack(fill="both", expand=True)

    def aplicar_preferencias_visuales(self, tema="dark", tamano_texto="normal"):
        """Aplica cambios reales de tema y escala de interfaz."""
        ctk.set_appearance_mode("light" if tema == "light" else "dark")
        ctk.set_widget_scaling(escala_tamano_texto(tamano_texto))
        self.tamano_texto_actual = tamano_texto or "normal"

    def iniciar_sesion(self, usuario_data):
        """Guarda la sesion activa y abre el menu principal.
        Si algo falla al cargar preferencias o estadísticas, no deja el login congelado.
        """
        try:
            if not usuario_data or "id" not in usuario_data:
                self.usuario_actual = None
                self.geometry("500x520")
                self.show_frame(LoginFrame)
                return

            self.usuario_actual = dict(usuario_data)
            self.velocidad_voz_actual = "normal"

            try:
                ok, _, config = obtener_configuracion(usuario_data["id"])
                if ok and config:
                    tema = config.get("tema") or "dark"
                    tamano_texto = config.get("tamano_texto") or "normal"
                    self.velocidad_voz_actual = config.get("velocidad_voz") or "normal"
                    self.aplicar_preferencias_visuales(tema, tamano_texto)
                else:
                    self.aplicar_preferencias_visuales("dark", "normal")
            except Exception as e:
                print("Error cargando configuracion del usuario:", e)
                traceback.print_exc()
                self.aplicar_preferencias_visuales("dark", "normal")

            self.geometry("1000x660")
            self.show_frame(MenuFrame)
        except Exception as e:
            traceback.print_exc()
            self.geometry("500x520")
            self.show_frame(LoginFrame)

    def cerrar_sesion(self):
        """Cierra sesion desde cualquier pantalla y vuelve al login limpio."""
        try:
            self.usuario_actual = None
            self.tamano_texto_actual = "normal"
            self.velocidad_voz_actual = "normal"
            ctk.set_appearance_mode("dark")
            ctk.set_widget_scaling(1.0)
            self.geometry("500x520")
            self.after(20, lambda: self.show_frame(LoginFrame))
        except Exception:
            traceback.print_exc()
            self.usuario_actual = None
            self.show_frame(LoginFrame)


class BaseFrame(ctk.CTkFrame):
    def titulo(self, texto, subtitulo=""):
        ctk.CTkLabel(self, text=texto, font=("Segoe UI", 24, "bold")).pack(pady=(18, 4))
        if subtitulo:
            ctk.CTkLabel(self, text=subtitulo, font=("Segoe UI", 13), wraplength=780).pack(pady=(0, 12))

    def nav_button(self, texto, frame_class, width=180):
        return ctk.CTkButton(self, text=texto, width=width, command=lambda: self.master.show_frame(frame_class))

    def velocidad_voz_configurada(self):
        id_usuario = self.master.usuario_actual.get("id") if self.master.usuario_actual else None
        if not id_usuario:
            return "normal"
        ok, _, config = obtener_configuracion(id_usuario)
        if ok and config:
            return config.get("velocidad_voz", "normal")
        return getattr(self.master, "velocidad_voz_actual", "normal")




def rol_actual(master) -> str:
    usuario = getattr(master, "usuario_actual", None) or {}
    return (usuario.get("rol") or "usuario").strip().lower()


def es_admin(master) -> bool:
    return rol_actual(master) in ("admin", "administrador")


def admin_listar_usuarios():
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, usuario, nombre_completo, rol, activo, creado_en, ultimo_login
                    FROM usuarios
                    ORDER BY id ASC
                    """
                )
                filas = cur.fetchall()
        return True, "Usuarios obtenidos.", [dict(f) for f in filas]
    except Exception as e:
        return False, "Error al listar usuarios: " + repr(e), []


def admin_cambiar_rol(id_usuario: int, nuevo_rol: str):
    nuevo_rol = (nuevo_rol or "usuario").strip().lower()
    if nuevo_rol not in ("usuario", "admin"):
        return False, "Rol no válido."
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE usuarios SET rol = %s WHERE id = %s", (nuevo_rol, id_usuario))
        return True, "Rol actualizado correctamente."
    except Exception as e:
        return False, "Error al actualizar rol: " + repr(e)


def admin_cambiar_estado_usuario(id_usuario: int, activo: bool):
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE usuarios SET activo = %s WHERE id = %s", (activo, id_usuario))
        return True, "Estado del usuario actualizado."
    except Exception as e:
        return False, "Error al cambiar estado: " + repr(e)


def admin_guardar_gesto(nombre_gesto: str, texto_traducido: str, categoria: str, descripcion: str):
    nombre_gesto = (nombre_gesto or "").strip().upper()
    texto_traducido = (texto_traducido or "").strip()
    categoria = (categoria or "General").strip()
    descripcion = (descripcion or "").strip()

    if not nombre_gesto or not texto_traducido:
        return False, "Nombre del gesto y texto traducido son obligatorios."

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id FROM gestos_demo WHERE nombre_gesto = %s LIMIT 1", (nombre_gesto,))
                fila = cur.fetchone()
                if fila:
                    cur.execute(
                        """
                        UPDATE gestos_demo
                        SET texto_traducido = %s,
                            categoria = %s,
                            descripcion = %s,
                            activo = TRUE
                        WHERE id = %s
                        """,
                        (texto_traducido, categoria, descripcion, fila["id"]),
                    )
                    return True, "Gesto actualizado correctamente."
                cur.execute(
                    """
                    INSERT INTO gestos_demo (nombre_gesto, texto_traducido, categoria, descripcion, activo)
                    VALUES (%s, %s, %s, %s, TRUE)
                    """,
                    (nombre_gesto, texto_traducido, categoria, descripcion),
                )
        return True, "Gesto registrado correctamente."
    except Exception as e:
        return False, "Error al guardar gesto: " + repr(e)


def admin_cambiar_estado_gesto(id_gesto: int, activo: bool):
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE gestos_demo SET activo = %s WHERE id = %s", (activo, id_gesto))
        return True, "Estado del gesto actualizado."
    except Exception as e:
        return False, "Error al cambiar estado del gesto: " + repr(e)


def admin_listar_gestos_todos():
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, nombre_gesto, texto_traducido, categoria, descripcion, activo, creado_en
                    FROM gestos_demo
                    ORDER BY nombre_gesto ASC
                    """
                )
                filas = cur.fetchall()
        return True, "Gestos obtenidos.", [dict(f) for f in filas]
    except Exception as e:
        return False, "Error al listar gestos: " + repr(e), []


class ErrorFrame(BaseFrame):
    def __init__(self, master, titulo_error="Error", detalle=""):
        super().__init__(master)
        self.titulo("SIGNATALK", titulo_error)
        ctk.CTkLabel(
            self,
            text=detalle or "Ocurrio un error inesperado.",
            text_color="#ff9f1c",
            wraplength=760,
            justify="center",
        ).pack(pady=18, padx=24)
        ctk.CTkLabel(
            self,
            text="Revisa la terminal de VS Code para ver el detalle técnico del error.",
            wraplength=760,
        ).pack(pady=8)
        ctk.CTkButton(self, text="Volver al login", command=lambda: master.show_frame(LoginFrame), width=190).pack(pady=12)
        if master.usuario_actual:
            ctk.CTkButton(self, text="Intentar abrir menú", command=lambda: master.show_frame(MenuFrame), width=190).pack(pady=8)


class LoginFrame(BaseFrame):
    def __init__(self, master):
        super().__init__(master)
        self.titulo("SIGNATALK", "Inicio de sesión conectado a PostgreSQL")

        if not master.db_ok:
            ctk.CTkLabel(self, text=master.db_msg, text_color="#ff9f1c", wraplength=420).pack(pady=8)

        card = ctk.CTkFrame(self)
        card.pack(pady=12, padx=40, fill="x")

        self.usuario_entry = ctk.CTkEntry(card, width=320, placeholder_text="Usuario")
        self.usuario_entry.pack(pady=(24, 10))

        self.password_entry = ctk.CTkEntry(card, width=320, placeholder_text="Contraseña", show="*")
        self.password_entry.pack(pady=10)

        self.mensaje_label = ctk.CTkLabel(card, text="", width=360, wraplength=360)
        self.mensaje_label.pack(pady=10)

        self.login_button = ctk.CTkButton(card, text="Ingresar", command=self.validar, width=190)
        self.login_button.pack(pady=8)

        ctk.CTkButton(card, text="Crear nueva cuenta", command=lambda: master.show_frame(RegistroFrame), width=190).pack(pady=8)
        ctk.CTkButton(card, text="Salir", command=master.quit, fg_color="#d90429", width=190).pack(pady=(8, 24))

        self.usuario_entry.bind("<Return>", lambda event: self.validar())
        self.password_entry.bind("<Return>", lambda event: self.validar())
        self.usuario_entry.focus()

    def validar(self):
        usuario = self.usuario_entry.get()
        password = self.password_entry.get()
        self.login_button.configure(state="disabled", text="Validando...")
        self.mensaje_label.configure(text="Consultando PostgreSQL...")

        def run():
            ok, mensaje, usuario_data = validar_login(usuario, password)
            self.after(0, lambda: self.procesar_resultado(ok, mensaje, usuario_data))

        threading.Thread(target=run, daemon=True).start()

    def procesar_resultado(self, ok, mensaje, usuario_data):
        if ok:
            self.mensaje_label.configure(text="Acceso correcto. Abriendo menu principal...")
            self.login_button.configure(state="disabled", text="Ingresando...")
            # Se programa la navegacion y se protege con try/except para que el
            # botón no se quede en "Ingresando..." si falla la carga del menú.
            def abrir_menu_seguro():
                try:
                    self.master.iniciar_sesion(usuario_data)
                except Exception as e:
                    traceback.print_exc()
                    self.login_button.configure(state="normal", text="Ingresar")
                    self.mensaje_label.configure(text="Acceso correcto, pero no se pudo abrir el menú. Revisa la terminal. Detalle: " + repr(e))

            self.after(150, abrir_menu_seguro)
        else:
            self.login_button.configure(state="normal", text="Ingresar")
            self.mensaje_label.configure(text=mensaje)
            self.password_entry.delete(0, "end")


class RegistroFrame(BaseFrame):
    def __init__(self, master):
        super().__init__(master)
        self.titulo("Registro de usuario", "Formulario conectado a la tabla usuarios")

        card = ctk.CTkFrame(self)
        card.pack(pady=10, padx=40, fill="x")

        self.usuario_entry = ctk.CTkEntry(card, width=340, placeholder_text="Usuario")
        self.usuario_entry.pack(pady=(22, 8))
        self.nombre_entry = ctk.CTkEntry(card, width=340, placeholder_text="Nombre completo")
        self.nombre_entry.pack(pady=8)

        ctk.CTkLabel(
            card,
            text="Rol asignado: usuario\nLos roles administrativos se asignan únicamente desde el Panel Administrador.",
            text_color="#9aa4ad",
            wraplength=340,
            justify="center",
        ).pack(pady=8)

        self.password_entry = ctk.CTkEntry(card, width=340, placeholder_text="Contraseña", show="*")
        self.password_entry.pack(pady=8)
        self.repetir_entry = ctk.CTkEntry(card, width=340, placeholder_text="Confirmar contraseña", show="*")
        self.repetir_entry.pack(pady=8)

        self.mensaje_label = ctk.CTkLabel(card, text="", width=380, wraplength=380)
        self.mensaje_label.pack(pady=10)

        self.registrar_btn = ctk.CTkButton(card, text="Registrar", command=self.registrar, width=190)
        self.registrar_btn.pack(pady=8)
        ctk.CTkButton(card, text="Volver al login", command=lambda: master.show_frame(LoginFrame), width=190).pack(pady=8)
        ctk.CTkButton(card, text="Salir", command=master.quit, fg_color="#d90429", width=190).pack(pady=(8, 22))

    def registrar(self):
        usuario = self.usuario_entry.get()
        nombre = self.nombre_entry.get()
        rol = "usuario"
        password = self.password_entry.get()
        repetir = self.repetir_entry.get()

        if password != repetir:
            self.mensaje_label.configure(text="Las contraseñas no coinciden.")
            return

        self.registrar_btn.configure(state="disabled", text="Registrando...")
        ok, mensaje = crear_usuario(usuario, password, nombre, rol)
        self.mensaje_label.configure(text=mensaje)
        if ok:
            self.password_entry.delete(0, "end")
            self.repetir_entry.delete(0, "end")
            self.mensaje_label.configure(text=mensaje + " Ahora inicia sesión con ese usuario.")
            self.after(900, lambda: self.master.show_frame(LoginFrame))
        else:
            self.registrar_btn.configure(state="normal", text="Registrar")


class MenuFrame(BaseFrame):
    def __init__(self, master):
        super().__init__(master)
        usuario = master.usuario_actual or {}
        nombre = usuario.get("nombre_completo") or usuario.get("usuario") or "Usuario"
        rol = rol_actual(master)
        self.titulo("SIGNATALK", f"Sesión activa: {nombre} | Rol: {rol}")

        ok, _, stats = obtener_estadisticas_usuario(usuario.get("id"))
        resumen = f"Traducciones guardadas: {stats.get('total', 0)}" if ok else "Resumen no disponible"
        ctk.CTkLabel(self, text=resumen, font=("Segoe UI", 13)).pack(pady=(0, 6))

        if es_admin(master):
            ctk.CTkLabel(
                self,
                text="Modo administrador activo: puedes gestionar usuarios y gestos demo del sistema.",
                text_color="#00b894",
                font=("Segoe UI", 13, "bold"),
            ).pack(pady=(0, 10))
        else:
            ctk.CTkLabel(
                self,
                text="Modo usuario: puedes usar traducción, voz, historial y tu perfil. No tienes permisos administrativos.",
                text_color="#9aa4ad",
                font=("Segoe UI", 12),
                wraplength=760,
            ).pack(pady=(0, 10))

        grid = ctk.CTkFrame(self)
        grid.pack(padx=28, pady=10, fill="both", expand=True)
        grid.grid_columnconfigure((0, 1, 2), weight=1)
        grid.grid_rowconfigure((0, 1), weight=1)

        items = [
            ("1. Traducción / Cámara", "Simula LSP → texto/voz y guarda el resultado", TraduccionFrame),
            ("2. Historial", "Consulta y reproduce traducciones guardadas", HistorialFrame),
            ("3. Configuración / Perfil", "Actualiza preferencias y datos del usuario", ConfiguracionFrame),
            ("4. Texto a Voz", "Convierte texto escrito en audio", TextoAVozFrame),
            ("5. Voz a Texto", "Convierte voz del micrófono en texto", VozATextoFrame),
        ]
        if es_admin(master):
            items.append(("6. Panel Administrador", "Gestiona usuarios, roles y gestos demo", AdminPanelFrame))

        for i, (titulo, desc, frame) in enumerate(items):
            card = ctk.CTkFrame(grid)
            card.grid(row=i // 3, column=i % 3, padx=10, pady=10, sticky="nsew")
            ctk.CTkLabel(card, text=titulo, font=("Segoe UI", 15, "bold")).pack(pady=(16, 6))
            ctk.CTkLabel(card, text=desc, wraplength=260).pack(pady=6, padx=14)
            ctk.CTkButton(card, text="Abrir", command=lambda f=frame: master.show_frame(f), width=140).pack(pady=(10, 16))

        bottom = ctk.CTkFrame(self)
        bottom.pack(pady=(0, 18))
        ctk.CTkButton(bottom, text="Cerrar sesión", command=master.cerrar_sesion, width=180).pack(side="left", padx=8)
        ctk.CTkButton(bottom, text="Salir", command=master.quit, fg_color="#d90429", width=180).pack(side="left", padx=8)


class TraduccionFrame(BaseFrame):
    def __init__(self, master):
        super().__init__(master)
        self.cap = None
        self.camera_running = False
        self.current_tipo = "LSP a texto (demo)"
        self.current_original = ""
        self.current_traducido = ""

        self.titulo("Pantalla de Traducción", "Cámara base + reconocimiento simulado desde tabla gestos_demo")

        cont = ctk.CTkFrame(self)
        cont.pack(fill="both", expand=True, padx=20, pady=10)
        cont.grid_columnconfigure(0, weight=3)
        cont.grid_columnconfigure(1, weight=2)
        cont.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(cont)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=5)
        right = ctk.CTkFrame(cont)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=5)

        self.video_label = ctk.CTkLabel(left, text="Cámara detenida", width=560, height=360)
        self.video_label.pack(pady=14, padx=14, fill="both", expand=True)

        cam_buttons = ctk.CTkFrame(left)
        cam_buttons.pack(pady=(0, 14))
        ctk.CTkButton(cam_buttons, text="Iniciar cámara", command=self.iniciar_camara, width=150).pack(side="left", padx=6)
        ctk.CTkButton(cam_buttons, text="Detener cámara", command=self.detener_camara, width=150).pack(side="left", padx=6)

        ok, msg, gestos = listar_gestos_demo()
        self.gestos = {g["nombre_gesto"]: g for g in gestos} if ok else {}
        valores = list(self.gestos.keys()) or ["HOLA", "GRACIAS", "AYUDA"]

        ctk.CTkLabel(right, text="Simulación de seña detectada", font=("Segoe UI", 16, "bold")).pack(pady=(20, 10))
        self.gesto_combo = ctk.CTkComboBox(right, values=valores, width=260)
        self.gesto_combo.set(valores[0])
        self.gesto_combo.pack(pady=8)
        ctk.CTkButton(right, text="Simular reconocimiento", command=self.simular_gesto, width=220).pack(pady=8)

        self.resultado_label = ctk.CTkLabel(right, text="Resultado pendiente", wraplength=320, justify="left")
        self.resultado_label.pack(pady=12, padx=18)

        ctk.CTkButton(right, text="Reconocer voz (STT)", command=self.reconocer_voz, width=220).pack(pady=8)
        ctk.CTkButton(right, text="Reproducir resultado (TTS)", command=self.reproducir_resultado, width=220).pack(pady=8)
        ctk.CTkButton(right, text="Guardar en historial", command=self.guardar_actual, width=220).pack(pady=8)
        self.mensaje_label = ctk.CTkLabel(right, text="", wraplength=320)
        self.mensaje_label.pack(pady=10)
        ctk.CTkButton(right, text="Volver al menú", command=lambda: master.show_frame(MenuFrame), width=220).pack(pady=(10, 20))

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
        self.video_label.configure(image=None, text="Cámara detenida")

    def update_frame(self):
        if self.cap is not None and self.camera_running:
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame)
                img.thumbnail((560, 360))
                imgtk = ImageTk.PhotoImage(image=img)
                self.video_label.configure(image=imgtk, text="")
                self.video_label.image = imgtk
            self.after(20, self.update_frame)

    def simular_gesto(self):
        nombre = self.gesto_combo.get()
        ok, msg, gesto = obtener_gesto_demo(nombre)
        if ok and gesto:
            self.current_tipo = "LSP a texto (demo)"
            self.current_original = f"Gesto detectado: {gesto['nombre_gesto']}"
            self.current_traducido = gesto["texto_traducido"]
            self.resultado_label.configure(
                text=f"Tipo: {self.current_tipo}\nOriginal: {self.current_original}\nTraducción: {self.current_traducido}"
            )
            self.mensaje_label.configure(text="La seña fue consultada desde PostgreSQL.")
        else:
            self.mensaje_label.configure(text=msg)

    def reconocer_voz(self):
        self.resultado_label.configure(text="Escuchando micrófono...")

        def run():
            resultado = voice_tools.voz_a_texto()
            self.current_tipo = "Voz a texto"
            self.current_original = "Audio capturado desde micrófono"
            self.current_traducido = resultado.replace("Texto reconocido: ", "")
            self.after(0, lambda: self.resultado_label.configure(
                text=f"Tipo: {self.current_tipo}\nOriginal: {self.current_original}\nResultado: {self.current_traducido}"
            ))

        threading.Thread(target=run, daemon=True).start()

    def reproducir_resultado(self):
        texto = self.current_traducido
        if not texto:
            self.mensaje_label.configure(text="Primero simula una seña o reconoce voz.")
            return
        velocidad = self.velocidad_voz_configurada()
        self.mensaje_label.configure(text=f"Reproduciendo audio en velocidad: {velocidad}...")

        def run():
            msg = voice_tools.texto_a_voz(texto, velocidad=velocidad)
            self.after(0, lambda: self.mensaje_label.configure(text=msg))

        threading.Thread(target=run, daemon=True).start()

    def guardar_actual(self):
        if not self.current_traducido:
            self.mensaje_label.configure(text="No hay traducción para guardar.")
            return
        id_usuario = self.master.usuario_actual["id"]
        ok, msg = guardar_traduccion(id_usuario, self.current_tipo, self.current_original, self.current_traducido)
        self.mensaje_label.configure(text=msg)

    def destroy(self):
        self.detener_camara()
        super().destroy()


class HistorialFrame(BaseFrame):
    def __init__(self, master):
        super().__init__(master)
        if es_admin(master):
            subtitulo = "Consulta real a PostgreSQL: reproduce o elimina registros guardados"
        else:
            subtitulo = "Consulta real a PostgreSQL: reproduce registros. La eliminación queda restringida al administrador."
        self.titulo("Historial de traducciones", subtitulo)

        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=20, pady=8)
        self.filtro_entry = ctk.CTkEntry(top, placeholder_text="Buscar por texto o tipo", width=340)
        self.filtro_entry.pack(side="left", padx=8, pady=10)
        ctk.CTkButton(top, text="Buscar", command=self.cargar_historial, width=120).pack(side="left", padx=8)
        ctk.CTkButton(top, text="Actualizar", command=self.cargar_historial, width=120).pack(side="left", padx=8)
        ctk.CTkButton(top, text="Volver al menú", command=lambda: master.show_frame(MenuFrame), width=150).pack(side="right", padx=8)

        self.mensaje_label = ctk.CTkLabel(self, text="")
        self.mensaje_label.pack(pady=2)

        self.scroll = ctk.CTkScrollableFrame(self, width=930, height=470)
        self.scroll.pack(fill="both", expand=True, padx=20, pady=(4, 18))
        self.cargar_historial()

    def cargar_historial(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        id_usuario = self.master.usuario_actual["id"]
        filtro = self.filtro_entry.get() if hasattr(self, "filtro_entry") else ""
        ok, msg, filas = listar_historial(id_usuario, filtro)
        self.mensaje_label.configure(text=f"{len(filas)} registro(s) encontrados." if ok else msg)

        if not filas:
            ctk.CTkLabel(self.scroll, text="No hay traducciones guardadas todavía.").pack(pady=20)
            return

        for fila in filas:
            card = ctk.CTkFrame(self.scroll)
            card.pack(fill="x", padx=8, pady=8)
            fecha = fila.get("fecha_hora")
            header = f"ID {fila['id']} | {fila.get('tipo_traduccion')} | {fecha}"
            ctk.CTkLabel(card, text=header, font=("Segoe UI", 13, "bold"), anchor="w").pack(fill="x", padx=12, pady=(10, 4))
            ctk.CTkLabel(card, text=f"Original: {fila.get('texto_original')}", anchor="w", wraplength=850, justify="left").pack(fill="x", padx=12)
            ctk.CTkLabel(card, text=f"Resultado: {fila.get('texto_traducido')}", anchor="w", wraplength=850, justify="left").pack(fill="x", padx=12, pady=(0, 8))
            actions = ctk.CTkFrame(card)
            actions.pack(fill="x", padx=8, pady=(0, 10))
            ctk.CTkButton(
                actions,
                text="Reproducir",
                width=115,
                command=lambda t=fila.get('texto_traducido', ''): self.reproducir(t),
            ).pack(side="left", padx=5)
            if es_admin(self.master):
                ctk.CTkButton(actions, text="Eliminar", width=100, fg_color="#d90429", command=lambda i=fila['id']: self.eliminar(i)).pack(side="left", padx=5)
            else:
                ctk.CTkLabel(actions, text="Eliminar: solo administrador", text_color="#9aa4ad").pack(side="left", padx=8)

    def reproducir(self, texto):
        if not texto:
            self.mensaje_label.configure(text="No hay texto para reproducir.")
            return
        velocidad = self.velocidad_voz_configurada()
        self.mensaje_label.configure(text=f"Reproduciendo traducción en velocidad: {velocidad}...")

        def run():
            msg = voice_tools.texto_a_voz(texto, velocidad=velocidad)
            self.after(0, lambda: self.mensaje_label.configure(text=msg))

        threading.Thread(target=run, daemon=True).start()

    def eliminar(self, id_historial):
        if not es_admin(self.master):
            self.mensaje_label.configure(text="No tienes permiso para eliminar registros.")
            return
        ok, msg = eliminar_historial(self.master.usuario_actual["id"], id_historial)
        self.mensaje_label.configure(text=msg)
        self.cargar_historial()


class AdminPanelFrame(BaseFrame):
    def __init__(self, master):
        super().__init__(master)
        if not es_admin(master):
            self.titulo("Acceso restringido", "Esta sección solo está disponible para administradores.")
            ctk.CTkButton(self, text="Volver al menú", command=lambda: master.show_frame(MenuFrame), width=180).pack(pady=20)
            return

        self.titulo("Panel Administrador", "Funciones exclusivas del rol administrador")
        ctk.CTkLabel(
            self,
            text="Desde aquí se realizan modificaciones generales del sistema. Los usuarios normales no pueden acceder a esta pantalla.",
            wraplength=760,
            justify="center",
        ).pack(pady=(0, 18))

        cont = ctk.CTkFrame(self)
        cont.pack(padx=40, pady=18, fill="both", expand=True)
        cont.grid_columnconfigure((0, 1), weight=1)

        card1 = ctk.CTkFrame(cont)
        card1.grid(row=0, column=0, padx=16, pady=16, sticky="nsew")
        ctk.CTkLabel(card1, text="Gestión de usuarios", font=("Segoe UI", 18, "bold")).pack(pady=(28, 8))
        ctk.CTkLabel(card1, text="Crear usuarios, activar/desactivar cuentas y cambiar roles.", wraplength=330).pack(pady=8, padx=18)
        ctk.CTkButton(card1, text="Abrir", command=lambda: master.show_frame(AdminUsuariosFrame), width=160).pack(pady=(14, 28))

        card2 = ctk.CTkFrame(cont)
        card2.grid(row=0, column=1, padx=16, pady=16, sticky="nsew")
        ctk.CTkLabel(card2, text="Gestión de gestos demo", font=("Segoe UI", 18, "bold")).pack(pady=(28, 8))
        ctk.CTkLabel(card2, text="Registrar, editar o desactivar gestos de prueba usados en la simulación.", wraplength=330).pack(pady=8, padx=18)
        ctk.CTkButton(card2, text="Abrir", command=lambda: master.show_frame(AdminGestosFrame), width=160).pack(pady=(14, 28))

        nav = ctk.CTkFrame(self)
        nav.pack(pady=14)
        ctk.CTkButton(nav, text="Volver al menú", command=lambda: master.show_frame(MenuFrame), width=160).pack(side="left", padx=8)
        ctk.CTkButton(nav, text="Cerrar sesión", command=master.cerrar_sesion, width=160).pack(side="left", padx=8)
        ctk.CTkButton(nav, text="Salir", command=master.quit, fg_color="#d90429", width=140).pack(side="left", padx=8)


class AdminUsuariosFrame(BaseFrame):
    def __init__(self, master):
        super().__init__(master)
        if not es_admin(master):
            self.titulo("Acceso restringido", "No tienes permisos administrativos.")
            ctk.CTkButton(self, text="Volver al menú", command=lambda: master.show_frame(MenuFrame), width=180).pack(pady=20)
            return

        self.titulo("Administración de usuarios", "Crear cuentas, activar/desactivar usuarios y asignar roles")
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=24, pady=8)

        self.usuario_entry = ctk.CTkEntry(top, placeholder_text="Usuario", width=150)
        self.usuario_entry.pack(side="left", padx=5, pady=10)
        self.nombre_entry = ctk.CTkEntry(top, placeholder_text="Nombre completo", width=190)
        self.nombre_entry.pack(side="left", padx=5, pady=10)
        self.password_entry = ctk.CTkEntry(top, placeholder_text="Contraseña", show="*", width=150)
        self.password_entry.pack(side="left", padx=5, pady=10)
        self.rol_combo = ctk.CTkComboBox(top, values=["usuario", "admin"], width=110)
        self.rol_combo.set("usuario")
        self.rol_combo.pack(side="left", padx=5, pady=10)
        self.crear_admin_btn = ctk.CTkButton(top, text="Crear", command=self.crear_desde_admin, width=90)
        self.crear_admin_btn.pack(side="left", padx=5)
        ctk.CTkButton(top, text="Cerrar sesión", command=master.cerrar_sesion, width=120).pack(side="right", padx=5)
        ctk.CTkButton(top, text="Volver", command=lambda: master.show_frame(AdminPanelFrame), width=90).pack(side="right", padx=5)

        self.mensaje_label = ctk.CTkLabel(self, text="", wraplength=850)
        self.mensaje_label.pack(pady=4)
        self.scroll = ctk.CTkScrollableFrame(self, width=940, height=430)
        self.scroll.pack(fill="both", expand=True, padx=24, pady=(4, 8))
        bottom = ctk.CTkFrame(self)
        bottom.pack(pady=(0, 14))
        ctk.CTkButton(bottom, text="Volver al panel", command=lambda: master.show_frame(AdminPanelFrame), width=150).pack(side="left", padx=6)
        ctk.CTkButton(bottom, text="Cerrar sesión", command=master.cerrar_sesion, width=150).pack(side="left", padx=6)
        self.cargar_usuarios()

    def crear_desde_admin(self):
        self.crear_admin_btn.configure(state="disabled", text="Creando...")
        ok, msg = crear_usuario(
            self.usuario_entry.get(),
            self.password_entry.get(),
            self.nombre_entry.get(),
            self.rol_combo.get(),
        )
        self.mensaje_label.configure(text=msg)
        if ok:
            self.usuario_entry.delete(0, "end")
            self.nombre_entry.delete(0, "end")
            self.password_entry.delete(0, "end")
            self.rol_combo.set("usuario")
            self.cargar_usuarios()
        self.crear_admin_btn.configure(state="normal", text="Crear")

    def cargar_usuarios(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        ok, msg, usuarios = admin_listar_usuarios()
        self.mensaje_label.configure(text=f"{len(usuarios)} usuario(s) encontrados." if ok else msg)
        for u in usuarios:
            card = ctk.CTkFrame(self.scroll)
            card.pack(fill="x", padx=8, pady=7)
            estado = "activo" if u.get("activo") else "inactivo"
            texto = f"ID {u['id']} | {u['usuario']} | Rol: {u.get('rol')} | Estado: {estado}"
            ctk.CTkLabel(card, text=texto, font=("Segoe UI", 13, "bold"), anchor="w").pack(fill="x", padx=12, pady=(10, 2))
            ctk.CTkLabel(card, text=f"Nombre: {u.get('nombre_completo') or ''} | Último login: {u.get('ultimo_login')}", anchor="w").pack(fill="x", padx=12, pady=(0, 8))
            actions = ctk.CTkFrame(card)
            actions.pack(fill="x", padx=8, pady=(0, 10))
            nuevo_rol = "admin" if (u.get("rol") or "usuario") == "usuario" else "usuario"
            ctk.CTkButton(actions, text=f"Cambiar a {nuevo_rol}", width=125, command=lambda i=u['id'], r=nuevo_rol: self.cambiar_rol(i, r)).pack(side="left", padx=5)
            nuevo_estado = not bool(u.get("activo"))
            texto_estado = "Activar" if nuevo_estado else "Desactivar"
            ctk.CTkButton(actions, text=texto_estado, width=110, fg_color="#d90429" if not nuevo_estado else None, command=lambda i=u['id'], a=nuevo_estado: self.cambiar_estado(i, a)).pack(side="left", padx=5)

    def cambiar_rol(self, id_usuario, nuevo_rol):
        ok, msg = admin_cambiar_rol(id_usuario, nuevo_rol)
        self.mensaje_label.configure(text=msg)
        self.cargar_usuarios()

    def cambiar_estado(self, id_usuario, activo):
        if id_usuario == self.master.usuario_actual.get("id") and not activo:
            self.mensaje_label.configure(text="No puedes desactivar tu propia cuenta durante la sesión.")
            return
        ok, msg = admin_cambiar_estado_usuario(id_usuario, activo)
        self.mensaje_label.configure(text=msg)
        self.cargar_usuarios()


class AdminGestosFrame(BaseFrame):
    def __init__(self, master):
        super().__init__(master)
        if not es_admin(master):
            self.titulo("Acceso restringido", "No tienes permisos administrativos.")
            ctk.CTkButton(self, text="Volver al menú", command=lambda: master.show_frame(MenuFrame), width=180).pack(pady=20)
            return

        self.titulo("Administración de gestos demo", "Modificar gestos de prueba usados en la pantalla de traducción")
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=24, pady=8)

        self.nombre_entry = ctk.CTkEntry(top, placeholder_text="Gesto: HOLA", width=130)
        self.nombre_entry.pack(side="left", padx=5, pady=10)
        self.texto_entry = ctk.CTkEntry(top, placeholder_text="Texto traducido", width=250)
        self.texto_entry.pack(side="left", padx=5, pady=10)
        self.categoria_entry = ctk.CTkEntry(top, placeholder_text="Categoría", width=130)
        self.categoria_entry.pack(side="left", padx=5, pady=10)
        self.descripcion_entry = ctk.CTkEntry(top, placeholder_text="Descripción", width=210)
        self.descripcion_entry.pack(side="left", padx=5, pady=10)
        ctk.CTkButton(top, text="Guardar", command=self.guardar_gesto, width=95).pack(side="left", padx=5)
        ctk.CTkButton(top, text="Cerrar sesión", command=master.cerrar_sesion, width=120).pack(side="right", padx=5)
        ctk.CTkButton(top, text="Volver", command=lambda: master.show_frame(AdminPanelFrame), width=90).pack(side="right", padx=5)

        self.mensaje_label = ctk.CTkLabel(self, text="", wraplength=850)
        self.mensaje_label.pack(pady=4)
        self.scroll = ctk.CTkScrollableFrame(self, width=940, height=430)
        self.scroll.pack(fill="both", expand=True, padx=24, pady=(4, 8))
        bottom = ctk.CTkFrame(self)
        bottom.pack(pady=(0, 14))
        ctk.CTkButton(bottom, text="Volver al panel", command=lambda: master.show_frame(AdminPanelFrame), width=150).pack(side="left", padx=6)
        ctk.CTkButton(bottom, text="Cerrar sesión", command=master.cerrar_sesion, width=150).pack(side="left", padx=6)
        self.cargar_gestos()

    def guardar_gesto(self):
        ok, msg = admin_guardar_gesto(
            self.nombre_entry.get(),
            self.texto_entry.get(),
            self.categoria_entry.get(),
            self.descripcion_entry.get(),
        )
        self.mensaje_label.configure(text=msg)
        if ok:
            self.nombre_entry.delete(0, "end")
            self.texto_entry.delete(0, "end")
            self.categoria_entry.delete(0, "end")
            self.descripcion_entry.delete(0, "end")
            self.cargar_gestos()

    def cargar_gestos(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        ok, msg, gestos = admin_listar_gestos_todos()
        self.mensaje_label.configure(text=f"{len(gestos)} gesto(s) registrados." if ok else msg)
        for g in gestos:
            card = ctk.CTkFrame(self.scroll)
            card.pack(fill="x", padx=8, pady=7)
            estado = "activo" if g.get("activo") else "inactivo"
            ctk.CTkLabel(card, text=f"ID {g['id']} | {g.get('nombre_gesto')} | {g.get('categoria')} | Estado: {estado}", font=("Segoe UI", 13, "bold"), anchor="w").pack(fill="x", padx=12, pady=(10, 2))
            ctk.CTkLabel(card, text=f"Texto: {g.get('texto_traducido')}", anchor="w", wraplength=850, justify="left").pack(fill="x", padx=12)
            ctk.CTkLabel(card, text=f"Descripción: {g.get('descripcion') or ''}", anchor="w", wraplength=850, justify="left").pack(fill="x", padx=12, pady=(0, 8))
            actions = ctk.CTkFrame(card)
            actions.pack(fill="x", padx=8, pady=(0, 10))
            nuevo_estado = not bool(g.get("activo"))
            texto_estado = "Activar" if nuevo_estado else "Desactivar"
            ctk.CTkButton(actions, text=texto_estado, width=110, fg_color="#d90429" if not nuevo_estado else None, command=lambda i=g['id'], a=nuevo_estado: self.cambiar_estado(i, a)).pack(side="left", padx=5)
            ctk.CTkButton(actions, text="Cargar en formulario", width=150, command=lambda gg=g: self.cargar_en_formulario(gg)).pack(side="left", padx=5)

    def cargar_en_formulario(self, gesto):
        self.nombre_entry.delete(0, "end")
        self.nombre_entry.insert(0, gesto.get("nombre_gesto") or "")
        self.texto_entry.delete(0, "end")
        self.texto_entry.insert(0, gesto.get("texto_traducido") or "")
        self.categoria_entry.delete(0, "end")
        self.categoria_entry.insert(0, gesto.get("categoria") or "")
        self.descripcion_entry.delete(0, "end")
        self.descripcion_entry.insert(0, gesto.get("descripcion") or "")
        self.mensaje_label.configure(text="Gesto cargado. Modifica los campos y presiona Guardar.")

    def cambiar_estado(self, id_gesto, activo):
        ok, msg = admin_cambiar_estado_gesto(id_gesto, activo)
        self.mensaje_label.configure(text=msg)
        self.cargar_gestos()


class ConfiguracionFrame(BaseFrame):
    def __init__(self, master):
        super().__init__(master)
        self.titulo("Configuración y Perfil", "Actualiza los datos visibles, el tamaño de texto y la velocidad real de voz")
        id_usuario = master.usuario_actual["id"]
        _, _, usuario = obtener_usuario(id_usuario)
        _, _, config = obtener_configuracion(id_usuario)
        usuario = usuario or master.usuario_actual
        self.config = config or {}

        cont = ctk.CTkScrollableFrame(self, width=900, height=500)
        cont.pack(padx=35, pady=12, fill="both", expand=True)
        cont.grid_columnconfigure(0, weight=1)
        cont.grid_columnconfigure(1, weight=1)

        header = ctk.CTkFrame(cont)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(12, 16))
        ctk.CTkLabel(
            header,
            text=f"Usuario: {usuario.get('usuario')}",
            font=("Segoe UI", 16, "bold")
        ).pack(pady=(12, 4))
        ctk.CTkLabel(
            header,
            text="Esta pantalla sí modifica el comportamiento de la aplicación: el tamaño de texto cambia la escala visual y la velocidad de voz afecta la reproducción TTS.",
            wraplength=760,
            justify="center"
        ).pack(pady=(0, 12))

        def crear_fila(row, titulo, descripcion, opciones_texto=None):
            info = ctk.CTkFrame(cont)
            info.grid(row=row, column=0, sticky="nsew", padx=(12, 8), pady=8)
            ctk.CTkLabel(
                info,
                text=titulo,
                font=("Segoe UI", 14, "bold"),
                anchor="w"
            ).pack(fill="x", padx=12, pady=(10, 2))
            ctk.CTkLabel(
                info,
                text=descripcion,
                wraplength=340,
                justify="left",
                anchor="w"
            ).pack(fill="x", padx=12, pady=(0, 10))

            campo = ctk.CTkFrame(cont)
            campo.grid(row=row, column=1, sticky="nsew", padx=(8, 12), pady=8)
            if opciones_texto:
                ctk.CTkLabel(
                    campo,
                    text=opciones_texto,
                    font=("Segoe UI", 12),
                    wraplength=360,
                    justify="left",
                    anchor="w"
                ).pack(fill="x", padx=16, pady=(12, 4))
            return campo

        campo_nombre = crear_fila(
            1,
            "Nombre completo",
            "Dato visible en el perfil y en el menú principal. Sirve para identificar al usuario activo.",
        )
        self.nombre_entry = ctk.CTkEntry(campo_nombre, width=360, placeholder_text="Nombre completo")
        self.nombre_entry.insert(0, usuario.get("nombre_completo") or "")
        self.nombre_entry.pack(fill="x", padx=16, pady=(14, 16))

        campo_tema = crear_fila(
            2,
            "Tema visual",
            "Define la apariencia de la interfaz. Se aplica al guardar.",
            "Opciones: dark = fondo oscuro | light = fondo claro",
        )
        self.tema_var = ctk.StringVar(value=self.config.get("tema", "dark"))
        self.tema_menu = ctk.CTkOptionMenu(campo_tema, values=["dark", "light"], variable=self.tema_var, width=360)
        self.tema_menu.pack(fill="x", padx=16, pady=(4, 16))

        campo_tamano = crear_fila(
            3,
            "Tamaño de texto",
            "Ahora sí cambia la escala visual real de la aplicación. Al guardar, los formularios se verán más pequeños o más grandes.",
            "Opciones: pequeño = escala 90% | normal = escala 100% | grande = escala 118%",
        )
        self.tamano_var = ctk.StringVar(value=self.config.get("tamano_texto", "normal"))
        self.tamano_menu = ctk.CTkOptionMenu(campo_tamano, values=["pequeño", "normal", "grande"], variable=self.tamano_var, width=360)
        self.tamano_menu.pack(fill="x", padx=16, pady=(4, 16))

        campo_velocidad = crear_fila(
            4,
            "Velocidad de voz",
            "Ahora sí afecta la reproducción del módulo Texto a Voz. Se usa en la pantalla de traducción y en Texto a Voz.",
            "Opciones: lenta | normal | rápida",
        )
        self.velocidad_var = ctk.StringVar(value=self.config.get("velocidad_voz", "normal"))
        self.velocidad_menu = ctk.CTkOptionMenu(campo_velocidad, values=["lenta", "normal", "rápida"], variable=self.velocidad_var, width=360)
        self.velocidad_menu.pack(fill="x", padx=16, pady=(4, 16))

        self.mensaje_label = ctk.CTkLabel(cont, text="", wraplength=760)
        self.mensaje_label.grid(row=5, column=0, columnspan=2, padx=12, pady=(10, 4), sticky="ew")

        buttons = ctk.CTkFrame(cont)
        buttons.grid(row=6, column=0, columnspan=2, pady=(8, 22))
        ctk.CTkButton(buttons, text="Guardar configuración", command=self.guardar, width=190).pack(side="left", padx=8)
        ctk.CTkButton(buttons, text="Volver al menú", command=lambda: master.show_frame(MenuFrame), width=190).pack(side="left", padx=8)

    def guardar(self):
        id_usuario = self.master.usuario_actual["id"]
        nombre = self.nombre_entry.get()
        tema = self.tema_var.get()
        tamano_texto = self.tamano_var.get()
        velocidad_voz = self.velocidad_var.get()

        # Se mantienen valores internos por compatibilidad con la tabla, pero ya no se muestran en pantalla.
        idioma = self.config.get("idioma", "es")
        notificaciones = bool(self.config.get("notificaciones", True))

        ok1, msg1 = actualizar_perfil(id_usuario, nombre)
        ok2, msg2 = guardar_configuracion(id_usuario, tema, tamano_texto, velocidad_voz, idioma, notificaciones)
        self.master.aplicar_preferencias_visuales(tema, tamano_texto)
        self.master.velocidad_voz_actual = velocidad_voz
        if ok1 and ok2:
            self.master.usuario_actual["nombre_completo"] = nombre
            self.config["tema"] = tema
            self.config["tamano_texto"] = tamano_texto
            self.config["velocidad_voz"] = velocidad_voz
            self.mensaje_label.configure(text=f"Configuración guardada. Tamaño: {tamano_texto}. Voz: {velocidad_voz}.")
        else:
            self.mensaje_label.configure(text=msg1 + chr(10) + msg2)



class TextoAVozFrame(BaseFrame):
    def __init__(self, master):
        super().__init__(master)
        velocidad = self.velocidad_voz_configurada()
        self.titulo("Texto a Voz", f"Módulo TTS del prototipo | Velocidad configurada: {velocidad}")
        self.entry = ctk.CTkEntry(self, width=620, placeholder_text="Ingresa el texto que quieres escuchar")
        self.entry.pack(pady=16)
        self.output = ctk.CTkLabel(self, text="", width=620, wraplength=620)
        self.output.pack(pady=8)
        ctk.CTkButton(self, text="Reproducir", command=self.reproducir, width=180).pack(pady=8)
        ctk.CTkButton(self, text="Guardar como traducción", command=self.guardar, width=180).pack(pady=8)
        ctk.CTkButton(self, text="Volver al menú", command=lambda: master.show_frame(MenuFrame), width=180).pack(pady=8)

    def reproducir(self):
        text = self.entry.get()
        velocidad = self.velocidad_voz_configurada()
        self.output.configure(text=f"Reproduciendo en velocidad: {velocidad}...")

        def run():
            resultado = voice_tools.texto_a_voz(text, velocidad=velocidad)
            self.after(0, lambda: self.output.configure(text=resultado))

        threading.Thread(target=run, daemon=True).start()

    def guardar(self):
        text = self.entry.get()
        ok, msg = guardar_traduccion(self.master.usuario_actual["id"], "Texto a voz", "Texto escrito por usuario", text)
        self.output.configure(text=msg)


class VozATextoFrame(BaseFrame):
    def __init__(self, master):
        super().__init__(master)
        self.ultimo_texto = ""
        self.titulo("Voz a Texto", "Módulo STT del prototipo")
        self.output = ctk.CTkLabel(self, text="Presiona el botón y habla.", width=620, wraplength=620)
        self.output.pack(pady=24)
        ctk.CTkButton(self, text="Iniciar reconocimiento", command=self.reconocer, width=220).pack(pady=8)
        ctk.CTkButton(self, text="Guardar en historial", command=self.guardar, width=220).pack(pady=8)
        ctk.CTkButton(self, text="Volver al menú", command=lambda: master.show_frame(MenuFrame), width=220).pack(pady=8)

    def reconocer(self):
        self.output.configure(text="Habla ahora...")

        def run():
            resultado = voice_tools.voz_a_texto()
            self.ultimo_texto = resultado.replace("Texto reconocido: ", "")
            self.after(0, lambda: self.output.configure(text=resultado))

        threading.Thread(target=run, daemon=True).start()

    def guardar(self):
        if not self.ultimo_texto:
            self.output.configure(text="Primero debes reconocer voz.")
            return
        ok, msg = guardar_traduccion(self.master.usuario_actual["id"], "Voz a texto", "Audio capturado desde micrófono", self.ultimo_texto)
        self.output.configure(text=msg)


if __name__ == "__main__":
    app = SignaTalkApp()
    app.mainloop()
