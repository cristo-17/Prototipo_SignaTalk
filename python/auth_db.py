import hmac
import hashlib
import secrets
import re
from typing import Optional, Tuple, Dict, Any, List

import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "dbname": "talktome_db",
    "user": "postgres",
    "password": "root",
}

ITERATIONS = 200_000


# =========================
# CONEXION Y SEGURIDAD
# =========================

def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def hash_password(password: str, salt: Optional[bytes] = None) -> Tuple[str, str]:
    if salt is None:
        salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        ITERATIONS,
    )
    return salt.hex(), password_hash.hex()


def verificar_password(password: str, salt_hex: str, password_hash_hex: str) -> bool:
    salt = bytes.fromhex(salt_hex)
    _, nuevo_hash = hash_password(password, salt)
    return hmac.compare_digest(nuevo_hash, password_hash_hex)


def inicializar_bd() -> Tuple[bool, str]:
    sql = """
    CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY,
        usuario VARCHAR(80) UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        nombre_completo VARCHAR(160) NOT NULL,
        rol VARCHAR(30) NOT NULL DEFAULT 'usuario',
        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ultimo_login TIMESTAMP,
        CONSTRAINT chk_usuarios_rol CHECK (rol IN ('admin', 'usuario'))
    );

    CREATE TABLE IF NOT EXISTS perfiles_usuario (
        id SERIAL PRIMARY KEY,
        id_usuario INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
        dni VARCHAR(8) NOT NULL,
        correo VARCHAR(150) NOT NULL,
        telefono VARCHAR(9) NOT NULL,
        direccion VARCHAR(200) NOT NULL,
        velocidad_voz VARCHAR(30) DEFAULT 'normal',
        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT uq_perfil_usuario UNIQUE (id_usuario),
        CONSTRAINT uq_perfil_dni UNIQUE (dni),
        CONSTRAINT uq_perfil_correo UNIQUE (correo),
        CONSTRAINT chk_perfil_dni CHECK (dni ~ '^[0-9]{8}$'),
        CONSTRAINT chk_perfil_telefono CHECK (telefono ~ '^[0-9]{9}$'),
        CONSTRAINT chk_perfil_correo CHECK (correo LIKE '%@%.%'),
        CONSTRAINT chk_perfil_velocidad CHECK (velocidad_voz IN ('lenta', 'normal', 'rapida'))
    );

    CREATE TABLE IF NOT EXISTS gestos_demo (
        id SERIAL PRIMARY KEY,
        id_usuario INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
        nombre_gesto VARCHAR(100) NOT NULL,
        texto_traducido TEXT NOT NULL,
        categoria VARCHAR(100) NOT NULL,
        descripcion TEXT,
        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT uq_gesto_usuario_nombre UNIQUE (id_usuario, nombre_gesto)
    );

    CREATE TABLE IF NOT EXISTS historial_traducciones (
        id SERIAL PRIMARY KEY,
        id_usuario INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
        tipo_traduccion VARCHAR(100) NOT NULL,
        texto_original TEXT NOT NULL,
        texto_traducido TEXT NOT NULL,
        fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS frases_frecuentes (
        id SERIAL PRIMARY KEY,
        id_usuario INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
        frase TEXT NOT NULL,
        categoria VARCHAR(100) NOT NULL,
        descripcion TEXT,
        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
        return True, "Base de datos inicializada correctamente."
    except Exception as e:
        return False, f"Error al inicializar la base de datos: {e}"


# =========================
# VALIDADORES
# =========================

def validar_dni(dni: str) -> bool:
    return bool(re.fullmatch(r"\d{8}", (dni or "").strip()))


def validar_telefono(telefono: str) -> bool:
    return bool(re.fullmatch(r"\d{9}", (telefono or "").strip()))


def validar_correo(correo: str) -> bool:
    correo = (correo or "").strip()
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", correo))


# =========================
# LOGIN Y USUARIOS
# =========================

def validar_login(usuario: str, password: str, rol_esperado: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    usuario = (usuario or "").strip().lower()
    rol_esperado = (rol_esperado or "usuario").strip().lower()
    if rol_esperado not in ("admin", "usuario"):
        return False, "Selecciona un tipo de acceso valido.", None
    if not usuario or not password:
        return False, "Ingresa usuario y contrasena.", None

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, usuario, password_hash, salt, nombre_completo, rol
                    FROM usuarios
                    WHERE usuario = %s
                    LIMIT 1
                    """,
                    (usuario,),
                )
                fila = cur.fetchone()
                if fila is None:
                    return False, "Usuario o contrasena incorrectos.", None
                if fila["rol"] != rol_esperado:
                    return False, f"Esta cuenta no corresponde al acceso {rol_esperado}.", None
                if not verificar_password(password, fila["salt"], fila["password_hash"]):
                    return False, "Usuario o contrasena incorrectos.", None
                cur.execute("UPDATE usuarios SET ultimo_login = CURRENT_TIMESTAMP WHERE id = %s", (fila["id"],))
                return True, "Acceso permitido.", dict(fila)
    except Exception as e:
        return False, f"No se pudo conectar o consultar PostgreSQL: {e}", None


def listar_usuarios(admin: bool, id_usuario_actual: int) -> Tuple[bool, str, List[Dict[str, Any]]]:
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if admin:
                    cur.execute("""
                        SELECT id, usuario, nombre_completo, rol, creado_en, ultimo_login
                        FROM usuarios ORDER BY id
                    """)
                else:
                    cur.execute("""
                        SELECT id, usuario, nombre_completo, rol, creado_en, ultimo_login
                        FROM usuarios WHERE id = %s
                    """, (id_usuario_actual,))
                filas = cur.fetchall()
        return True, "Usuarios obtenidos.", [dict(f) for f in filas]
    except Exception as e:
        return False, f"Error al listar usuarios: {e}", []


def obtener_usuario(id_usuario: int) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, usuario, nombre_completo, rol, creado_en, ultimo_login
                    FROM usuarios WHERE id = %s
                """, (id_usuario,))
                fila = cur.fetchone()
        return (True, "Usuario encontrado.", dict(fila)) if fila else (False, "Usuario no encontrado.", None)
    except Exception as e:
        return False, f"Error al obtener usuario: {e}", None


def guardar_usuario(id_usuario: Optional[int], usuario: str, nombre: str, rol: str, password: str = "", confirmar: str = "") -> Tuple[bool, str]:
    usuario = (usuario or "").strip().lower()
    nombre = (nombre or "").strip()
    rol = (rol or "usuario").strip().lower()
    password = password or ""
    confirmar = confirmar or ""

    if not usuario:
        return False, "El usuario es obligatorio."
    if not nombre:
        return False, "El nombre completo es obligatorio."
    if rol not in ("admin", "usuario"):
        return False, "El rol debe ser admin o usuario."
    if id_usuario is None and not password:
        return False, "La contrasena es obligatoria para crear usuario."
    if password or confirmar:
        if password != confirmar:
            return False, "La contrasena y la confirmacion no coinciden."
        if len(password) < 4:
            return False, "La contrasena debe tener al menos 4 caracteres."

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                if id_usuario is None:
                    salt, password_hash = hash_password(password)
                    cur.execute("""
                        INSERT INTO usuarios (usuario, password_hash, salt, nombre_completo, rol)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (usuario, password_hash, salt, nombre, rol))
                    return True, "Usuario creado correctamente."
                else:
                    if password:
                        salt, password_hash = hash_password(password)
                        cur.execute("""
                            UPDATE usuarios
                            SET usuario=%s, nombre_completo=%s, rol=%s, password_hash=%s, salt=%s
                            WHERE id=%s
                        """, (usuario, nombre, rol, password_hash, salt, id_usuario))
                    else:
                        cur.execute("""
                            UPDATE usuarios
                            SET usuario=%s, nombre_completo=%s, rol=%s
                            WHERE id=%s
                        """, (usuario, nombre, rol, id_usuario))
                    return True, "Usuario actualizado correctamente."
    except psycopg2.errors.UniqueViolation:
        return False, "El nombre de usuario ya existe."
    except Exception as e:
        return False, f"Error al guardar usuario: {e}"


# =========================
# PERFILES
# =========================

def listar_perfiles(admin: bool, id_usuario_actual: int) -> Tuple[bool, str, List[Dict[str, Any]]]:
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if admin:
                    cur.execute("""
                        SELECT u.id AS id_usuario, u.usuario, u.nombre_completo, u.rol,
                               p.id, p.dni, p.correo, p.telefono, p.direccion, p.velocidad_voz, p.creado_en, p.actualizado_en
                        FROM usuarios u
                        LEFT JOIN perfiles_usuario p ON p.id_usuario = u.id
                        ORDER BY u.id
                    """)
                else:
                    cur.execute("""
                        SELECT u.id AS id_usuario, u.usuario, u.nombre_completo, u.rol,
                               p.id, p.dni, p.correo, p.telefono, p.direccion, p.velocidad_voz, p.creado_en, p.actualizado_en
                        FROM usuarios u
                        LEFT JOIN perfiles_usuario p ON p.id_usuario = u.id
                        WHERE u.id = %s
                    """, (id_usuario_actual,))
                filas = cur.fetchall()
        return True, "Perfiles obtenidos.", [dict(f) for f in filas]
    except Exception as e:
        return False, f"Error al listar perfiles: {e}", []


def guardar_perfil(id_usuario: int, dni: str, correo: str, telefono: str, direccion: str, velocidad_voz: str) -> Tuple[bool, str]:
    dni = (dni or "").strip()
    correo = (correo or "").strip().lower()
    telefono = (telefono or "").strip()
    direccion = (direccion or "").strip()
    velocidad_voz = (velocidad_voz or "normal").strip().lower()

    if not validar_dni(dni):
        return False, "El DNI debe tener exactamente 8 digitos."
    if not validar_correo(correo):
        return False, "Ingresa un correo valido."
    if not validar_telefono(telefono):
        return False, "El telefono debe tener exactamente 9 digitos."
    if not direccion:
        return False, "La direccion es obligatoria."
    if velocidad_voz not in ("lenta", "normal", "rapida"):
        return False, "La velocidad de voz debe ser lenta, normal o rapida."

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO perfiles_usuario (id_usuario, dni, correo, telefono, direccion, velocidad_voz, actualizado_en)
                    VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (id_usuario) DO UPDATE SET
                        dni = EXCLUDED.dni,
                        correo = EXCLUDED.correo,
                        telefono = EXCLUDED.telefono,
                        direccion = EXCLUDED.direccion,
                        velocidad_voz = EXCLUDED.velocidad_voz,
                        actualizado_en = CURRENT_TIMESTAMP
                """, (id_usuario, dni, correo, telefono, direccion, velocidad_voz))
        return True, "Perfil guardado correctamente."
    except psycopg2.errors.UniqueViolation:
        return False, "El DNI o correo ya esta registrado en otro perfil."
    except Exception as e:
        return False, f"Error al guardar perfil: {e}"


def obtener_velocidad_usuario(id_usuario: int) -> str:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT velocidad_voz FROM perfiles_usuario WHERE id_usuario=%s", (id_usuario,))
                fila = cur.fetchone()
        return fila[0] if fila and fila[0] else "normal"
    except Exception:
        return "normal"


# =========================
# GESTOS DEMO
# =========================

def listar_gestos(admin: bool, id_usuario_actual: int) -> Tuple[bool, str, List[Dict[str, Any]]]:
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if admin:
                    cur.execute("""
                        SELECT g.*, u.usuario, u.nombre_completo
                        FROM gestos_demo g
                        JOIN usuarios u ON u.id = g.id_usuario
                        ORDER BY u.usuario, g.nombre_gesto
                    """)
                else:
                    cur.execute("""
                        SELECT g.*, u.usuario, u.nombre_completo
                        FROM gestos_demo g
                        JOIN usuarios u ON u.id = g.id_usuario
                        WHERE g.id_usuario = %s
                        ORDER BY g.nombre_gesto
                    """, (id_usuario_actual,))
                filas = cur.fetchall()
        return True, "Gestos obtenidos.", [dict(f) for f in filas]
    except Exception as e:
        return False, f"Error al listar gestos: {e}", []


def guardar_gesto(id_gesto: Optional[int], id_usuario: int, nombre_gesto: str, texto_traducido: str, categoria: str, descripcion: str) -> Tuple[bool, str]:
    nombre_gesto = (nombre_gesto or "").strip().upper()
    texto_traducido = (texto_traducido or "").strip()
    categoria = (categoria or "").strip()
    descripcion = (descripcion or "").strip()

    if not nombre_gesto:
        return False, "El nombre del gesto es obligatorio."
    if not texto_traducido:
        return False, "El texto traducido es obligatorio."
    if not categoria:
        return False, "La categoria es obligatoria."

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                if id_gesto is None:
                    cur.execute("""
                        INSERT INTO gestos_demo (id_usuario, nombre_gesto, texto_traducido, categoria, descripcion)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (id_usuario, nombre_gesto, texto_traducido, categoria, descripcion))
                    return True, "Gesto creado correctamente para este usuario."
                else:
                    cur.execute("""
                        UPDATE gestos_demo
                        SET id_usuario=%s, nombre_gesto=%s, texto_traducido=%s, categoria=%s, descripcion=%s
                        WHERE id=%s
                    """, (id_usuario, nombre_gesto, texto_traducido, categoria, descripcion, id_gesto))
                    return True, "Gesto actualizado correctamente para este usuario."
    except psycopg2.errors.UniqueViolation:
        return False, "Ese gesto ya existe para el usuario seleccionado."
    except Exception as e:
        return False, f"Error al guardar gesto: {e}"


def obtener_gesto_por_nombre(id_usuario: int, nombre_gesto: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM gestos_demo
                    WHERE id_usuario=%s AND nombre_gesto=%s
                    LIMIT 1
                """, (id_usuario, (nombre_gesto or "").strip().upper()))
                fila = cur.fetchone()
        return (True, "Gesto encontrado.", dict(fila)) if fila else (False, "Gesto no encontrado.", None)
    except Exception as e:
        return False, f"Error al obtener gesto: {e}", None


# =========================
# TRADUCCIONES
# =========================

def guardar_traduccion(id_usuario: int, tipo_traduccion: str, texto_original: str, texto_traducido: str) -> Tuple[bool, str]:
    tipo_traduccion = (tipo_traduccion or "").strip()
    texto_original = (texto_original or "").strip()
    texto_traducido = (texto_traducido or "").strip()
    if not tipo_traduccion or not texto_original or not texto_traducido:
        return False, "Tipo, texto original y texto traducido son obligatorios."
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO historial_traducciones (id_usuario, tipo_traduccion, texto_original, texto_traducido)
                    VALUES (%s, %s, %s, %s)
                """, (id_usuario, tipo_traduccion, texto_original, texto_traducido))
        return True, "Traduccion guardada en el historial del usuario actual."
    except Exception as e:
        return False, f"Error al guardar traduccion: {e}"


def listar_traducciones(admin: bool, id_usuario_actual: int) -> Tuple[bool, str, List[Dict[str, Any]]]:
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if admin:
                    cur.execute("""
                        SELECT h.*, u.usuario
                        FROM historial_traducciones h
                        JOIN usuarios u ON u.id = h.id_usuario
                        ORDER BY h.fecha_hora DESC
                    """)
                else:
                    cur.execute("""
                        SELECT h.*, u.usuario
                        FROM historial_traducciones h
                        JOIN usuarios u ON u.id = h.id_usuario
                        WHERE h.id_usuario=%s
                        ORDER BY h.fecha_hora DESC
                    """, (id_usuario_actual,))
                filas = cur.fetchall()
        return True, "Traducciones obtenidas.", [dict(f) for f in filas]
    except Exception as e:
        return False, f"Error al listar traducciones: {e}", []


# =========================
# FRASES FRECUENTES
# =========================

def listar_frases(admin: bool, id_usuario_actual: int) -> Tuple[bool, str, List[Dict[str, Any]]]:
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if admin:
                    cur.execute("""
                        SELECT f.*, u.usuario
                        FROM frases_frecuentes f
                        JOIN usuarios u ON u.id = f.id_usuario
                        ORDER BY u.usuario, f.id
                    """)
                else:
                    cur.execute("""
                        SELECT f.*, u.usuario
                        FROM frases_frecuentes f
                        JOIN usuarios u ON u.id = f.id_usuario
                        WHERE f.id_usuario=%s
                        ORDER BY f.id
                    """, (id_usuario_actual,))
                filas = cur.fetchall()
        return True, "Frases obtenidas.", [dict(f) for f in filas]
    except Exception as e:
        return False, f"Error al listar frases: {e}", []


def guardar_frase(id_frase: Optional[int], id_usuario: int, frase: str, categoria: str, descripcion: str) -> Tuple[bool, str]:
    frase = (frase or "").strip()
    categoria = (categoria or "").strip()
    descripcion = (descripcion or "").strip()
    if not frase:
        return False, "La frase frecuente es obligatoria."
    if not categoria:
        return False, "La categoria es obligatoria."
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                if id_frase is None:
                    cur.execute("""
                        INSERT INTO frases_frecuentes (id_usuario, frase, categoria, descripcion)
                        VALUES (%s, %s, %s, %s)
                    """, (id_usuario, frase, categoria, descripcion))
                    return True, "Frase frecuente creada correctamente."
                else:
                    cur.execute("""
                        UPDATE frases_frecuentes
                        SET id_usuario=%s, frase=%s, categoria=%s, descripcion=%s
                        WHERE id=%s
                    """, (id_usuario, frase, categoria, descripcion, id_frase))
                    return True, "Frase frecuente actualizada correctamente."
    except Exception as e:
        return False, f"Error al guardar frase frecuente: {e}"
