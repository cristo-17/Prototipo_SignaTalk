import os
import hmac
import secrets
import hashlib
from typing import Optional, Tuple, Dict, Any, List

import psycopg2
from psycopg2.extras import RealDictCursor

# ==========================================================
# CONFIGURACIÓN DE POSTGRESQL LOCAL
# ==========================================================
# Cambia la contraseña si tu pgAdmin/PostgreSQL usa otra.
# También puedes definir variables de entorno en Windows:
# POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "dbname": os.getenv("POSTGRES_DB", "talktome_db"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "root"),
}

ITERATIONS = 200_000


def get_connection():
    """Crea una conexión nueva a PostgreSQL."""
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_client_encoding("WIN1252")
    return conn


def hash_password(password: str, salt: Optional[bytes] = None) -> Tuple[str, str]:
    """Genera salt y hash seguro para guardar la contraseña."""
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
    """Valida una contraseña comparándola con el hash guardado."""
    salt = bytes.fromhex(salt_hex)
    _, nuevo_hash_hex = hash_password(password, salt)
    return hmac.compare_digest(nuevo_hash_hex, password_hash_hex)


def inicializar_bd() -> Tuple[bool, str]:
    """Crea/actualiza las tablas necesarias para el avance del proyecto."""
    sql = """
    CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY,
        usuario VARCHAR(80) UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        nombre_completo VARCHAR(160),
        rol VARCHAR(50) DEFAULT 'usuario',
        activo BOOLEAN DEFAULT TRUE,
        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ultimo_login TIMESTAMP
    );

    ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS password_hash TEXT;
    ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS salt TEXT;
    ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS nombre_completo VARCHAR(160);
    ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS rol VARCHAR(50) DEFAULT 'usuario';
    ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS activo BOOLEAN DEFAULT TRUE;
    ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
    ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS ultimo_login TIMESTAMP;

    CREATE TABLE IF NOT EXISTS configuracion_usuario (
        id SERIAL PRIMARY KEY,
        id_usuario INT UNIQUE NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
        tema VARCHAR(20) DEFAULT 'dark',
        tamano_texto VARCHAR(20) DEFAULT 'normal',
        velocidad_voz VARCHAR(20) DEFAULT 'normal',
        idioma VARCHAR(20) DEFAULT 'es',
        notificaciones BOOLEAN DEFAULT TRUE,
        actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- SOLUCIÓN AL ERROR: Borramos la tabla antigua para recrearla con 'nombre_gesto'
    DROP TABLE IF EXISTS gestos_demo CASCADE;

    CREATE TABLE IF NOT EXISTS gestos_demo (
        id SERIAL PRIMARY KEY,
        nombre_gesto VARCHAR(100) UNIQUE NOT NULL,
        texto_traducido TEXT NOT NULL,
        categoria VARCHAR(100),
        descripcion TEXT,
        activo BOOLEAN DEFAULT TRUE,
        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS historial_traducciones (
        id SERIAL PRIMARY KEY,
        id_usuario INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
        tipo_traduccion VARCHAR(80),
        texto_original TEXT,
        texto_traducido TEXT,
        es_favorito BOOLEAN DEFAULT FALSE,
        fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Prevenimos otro error futuro asegurando que 'es_favorito' exista
    ALTER TABLE historial_traducciones ADD COLUMN IF NOT EXISTS es_favorito BOOLEAN DEFAULT FALSE;

    CREATE TABLE IF NOT EXISTS frases_favoritas (
        id SERIAL PRIMARY KEY,
        id_usuario INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
        frase TEXT NOT NULL,
        categoria VARCHAR(100) DEFAULT 'General',
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS retroalimentacion (
        id SERIAL PRIMARY KEY,
        id_usuario INT REFERENCES usuarios(id) ON DELETE SET NULL,
        comentario TEXT,
        calificacion INT CHECK (calificacion BETWEEN 1 AND 5),
        fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    INSERT INTO gestos_demo (nombre_gesto, texto_traducido, categoria, descripcion)
    VALUES
        ('HOLA', 'Hola, ¿cómo estás?', 'Saludo', 'Gesto inicial de saludo.'),
        ('GRACIAS', 'Muchas gracias.', 'Cortesía', 'Expresión de agradecimiento.'),
        ('AYUDA', 'Necesito ayuda, por favor.', 'Emergencia', 'Solicitud de apoyo.'),
        ('AGUA', 'Quiero agua, por favor.', 'Necesidad básica', 'Solicitud de agua.'),
        ('BAÑO', 'Necesito ir al baño.', 'Necesidad básica', 'Solicitud para ir al baño.'),
        ('DOLOR', 'Tengo dolor y necesito atención.', 'Salud', 'Comunicación de malestar.'),
        ('SI', 'Sí, estoy de acuerdo.', 'Respuesta', 'Respuesta afirmativa.'),
        ('NO', 'No, no estoy de acuerdo.', 'Respuesta', 'Respuesta negativa.')
    ON CONFLICT (nombre_gesto) DO NOTHING;
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
        return True, "Base de datos inicializada correctamente."
    except Exception as e:
        return False, f"Error al inicializar la base de datos: {e}"


def crear_usuario(
    usuario: str,
    password: str,
    nombre_completo: str = "",
    rol: str = "usuario",
) -> Tuple[bool, str]:
    """Crea un usuario con contraseña encriptada y configuración inicial."""
    usuario = usuario.strip().lower()
    rol = (rol or "usuario").strip().lower()

    if not usuario or not password:
        return False, "Usuario y contraseña son obligatorios."

    if len(password) < 4:
        return False, "La contraseña debe tener al menos 4 caracteres."

    salt, password_hash = hash_password(password)

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO usuarios (usuario, password_hash, salt, nombre_completo, rol, activo)
                    VALUES (%s, %s, %s, %s, %s, TRUE)
                    RETURNING id
                    """,
                    (usuario, password_hash, salt, nombre_completo, rol),
                )
                nuevo_id = cur.fetchone()[0]
                cur.execute(
                    """
                    INSERT INTO configuracion_usuario (id_usuario)
                    VALUES (%s)
                    ON CONFLICT (id_usuario) DO NOTHING
                    """,
                    (nuevo_id,),
                )
        return True, f"Usuario '{usuario}' creado correctamente."
    except psycopg2.errors.UniqueViolation:
        return False, f"El usuario '{usuario}' ya existe."
    except Exception as e:
        return False, f"Error al crear usuario: {e}"


def validar_login(usuario: str, password: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Valida usuario y contraseña contra PostgreSQL."""
    usuario = usuario.strip().lower()
    if not usuario or not password:
        return False, "Ingresa usuario y contraseña.", None

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, usuario, password_hash, salt, nombre_completo, rol, activo
                    FROM usuarios
                    WHERE usuario = %s
                    LIMIT 1
                    """,
                    (usuario,),
                )
                fila = cur.fetchone()

                if fila is None:
                    return False, "Usuario o contraseña incorrectos.", None

                if not fila["activo"]:
                    return False, "El usuario está desactivado.", None

                if not verificar_password(password, fila["salt"], fila["password_hash"]):
                    return False, "Usuario o contraseña incorrectos.", None

                cur.execute(
                    "UPDATE usuarios SET ultimo_login = CURRENT_TIMESTAMP WHERE id = %s",
                    (fila["id"],),
                )
                cur.execute(
                    """
                    INSERT INTO configuracion_usuario (id_usuario)
                    VALUES (%s)
                    ON CONFLICT (id_usuario) DO NOTHING
                    """,
                    (fila["id"],),
                )

                return True, "Acceso permitido.", {
                    "id": fila["id"],
                    "usuario": fila["usuario"],
                    "nombre_completo": fila["nombre_completo"],
                    "rol": fila["rol"],
                }
    except Exception as e:
        return False, f"No se pudo conectar o consultar PostgreSQL: {e}", None


def obtener_usuario(id_usuario: int) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, usuario, nombre_completo, rol, activo, creado_en, ultimo_login
                    FROM usuarios
                    WHERE id = %s
                    """,
                    (id_usuario,),
                )
                fila = cur.fetchone()
        if fila:
            return True, "Usuario encontrado.", dict(fila)
        return False, "Usuario no encontrado.", None
    except Exception as e:
        return False, f"Error al consultar usuario: {e}", None


def actualizar_perfil(id_usuario: int, nombre_completo: str) -> Tuple[bool, str]:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE usuarios SET nombre_completo = %s WHERE id = %s",
                    (nombre_completo.strip(), id_usuario),
                )
        return True, "Perfil actualizado correctamente."
    except Exception as e:
        return False, f"Error al actualizar perfil: {e}"


def obtener_configuracion(id_usuario: int) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO configuracion_usuario (id_usuario)
                    VALUES (%s)
                    ON CONFLICT (id_usuario) DO NOTHING
                    """,
                    (id_usuario,),
                )
                cur.execute(
                    """
                    SELECT tema, tamano_texto, velocidad_voz, idioma, notificaciones
                    FROM configuracion_usuario
                    WHERE id_usuario = %s
                    """,
                    (id_usuario,),
                )
                fila = cur.fetchone()
        return True, "Configuración encontrada.", dict(fila) if fila else None
    except Exception as e:
        return False, f"Error al obtener configuración: {e}", None


def guardar_configuracion(
    id_usuario: int,
    tema: str,
    tamano_texto: str,
    velocidad_voz: str,
    idioma: str,
    notificaciones: bool,
) -> Tuple[bool, str]:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO configuracion_usuario
                        (id_usuario, tema, tamano_texto, velocidad_voz, idioma, notificaciones, actualizado_en)
                    VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (id_usuario) DO UPDATE SET
                        tema = EXCLUDED.tema,
                        tamano_texto = EXCLUDED.tamano_texto,
                        velocidad_voz = EXCLUDED.velocidad_voz,
                        idioma = EXCLUDED.idioma,
                        notificaciones = EXCLUDED.notificaciones,
                        actualizado_en = CURRENT_TIMESTAMP
                    """,
                    (id_usuario, tema, tamano_texto, velocidad_voz, idioma, notificaciones),
                )
        return True, "Configuración guardada correctamente."
    except Exception as e:
        return False, f"Error al guardar configuración: {e}"


def listar_gestos_demo() -> Tuple[bool, str, List[Dict[str, Any]]]:
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, nombre_gesto, texto_traducido, categoria, descripcion
                    FROM gestos_demo
                    WHERE activo = TRUE
                    ORDER BY nombre_gesto
                    """
                )
                filas = cur.fetchall()
        return True, "Gestos obtenidos.", [dict(f) for f in filas]
    except Exception as e:
        return False, f"Error al listar gestos: {e}", []


def obtener_gesto_demo(nombre_gesto: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, nombre_gesto, texto_traducido, categoria, descripcion
                    FROM gestos_demo
                    WHERE nombre_gesto = %s AND activo = TRUE
                    LIMIT 1
                    """,
                    (nombre_gesto,),
                )
                fila = cur.fetchone()
        if fila:
            return True, "Gesto encontrado.", dict(fila)
        return False, "Gesto no encontrado.", None
    except Exception as e:
        return False, f"Error al obtener gesto: {e}", None


def guardar_traduccion(
    id_usuario: int,
    tipo_traduccion: str,
    texto_original: str,
    texto_traducido: str,
) -> Tuple[bool, str]:
    if not texto_traducido.strip():
        return False, "No hay texto traducido para guardar."
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO historial_traducciones
                        (id_usuario, tipo_traduccion, texto_original, texto_traducido)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (id_usuario, tipo_traduccion, texto_original, texto_traducido),
                )
                nuevo_id = cur.fetchone()[0]
        return True, f"Traducción guardada en historial con ID {nuevo_id}."
    except Exception as e:
        return False, f"Error al guardar traducción: {e}"


def listar_historial(id_usuario: int, filtro: str = "") -> Tuple[bool, str, List[Dict[str, Any]]]:
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if filtro.strip():
                    patron = f"%{filtro.strip()}%"
                    cur.execute(
                        """
                        SELECT id, tipo_traduccion, texto_original, texto_traducido, es_favorito, fecha_hora
                        FROM historial_traducciones
                        WHERE id_usuario = %s
                          AND (texto_original ILIKE %s OR texto_traducido ILIKE %s OR tipo_traduccion ILIKE %s)
                        ORDER BY fecha_hora DESC
                        LIMIT 100
                        """,
                        (id_usuario, patron, patron, patron),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id, tipo_traduccion, texto_original, texto_traducido, es_favorito, fecha_hora
                        FROM historial_traducciones
                        WHERE id_usuario = %s
                        ORDER BY fecha_hora DESC
                        LIMIT 100
                        """,
                        (id_usuario,),
                    )
                filas = cur.fetchall()
        return True, "Historial obtenido.", [dict(f) for f in filas]
    except Exception as e:
        return False, f"Error al listar historial: {e}", []


def eliminar_historial(id_usuario: int, id_historial: int) -> Tuple[bool, str]:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM historial_traducciones WHERE id = %s AND id_usuario = %s",
                    (id_historial, id_usuario),
                )
        return True, "Registro eliminado del historial."
    except Exception as e:
        return False, f"Error al eliminar registro: {e}"
    
def eliminar_traduccion(id_usuario, id_historial):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                DELETE FROM frases_favoritas
                WHERE id_usuario = %s AND id_historial = %s
            """, (id_usuario, id_historial))

            cursor.execute("""
                DELETE FROM historial_traducciones
                WHERE id = %s AND id_usuario = %s
            """, (id_historial, id_usuario))

            conn.commit()
            return True, "Traducción eliminada correctamente."

    except Exception as e:
        conn.rollback()
        return False, f"Error al eliminar traducción: {e}"
    finally:
        conn.close()


def marcar_favorito(id_usuario, id_historial):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT texto_traducido, tipo_traduccion
                FROM historial_traducciones
                WHERE id = %s AND id_usuario = %s
            """, (id_historial, id_usuario))

            traduccion = cursor.fetchone()

            if not traduccion:
                return False, "No se encontró la traducción en el historial."

            frase = traduccion["texto_traducido"]
            categoria = traduccion["tipo_traduccion"]

            cursor.execute("""
                INSERT INTO frases_favoritas 
                (id_usuario, id_historial, frase, categoria)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id_usuario, id_historial) DO NOTHING
            """, (id_usuario, id_historial, frase, categoria))

            conn.commit()
            return True, "Frase agregada a favoritos."

    except Exception as e:
        conn.rollback()
        return False, f"Error al marcar favorito: {e}"
    finally:
        conn.close()


def obtener_estadisticas_usuario(id_usuario: int) -> Tuple[bool, str, Dict[str, int]]:
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT COUNT(*) AS total FROM historial_traducciones WHERE id_usuario = %s",
                    (id_usuario,),
                )
                total = cur.fetchone()["total"]
                cur.execute(
                    "SELECT COUNT(*) AS favoritos FROM historial_traducciones WHERE id_usuario = %s AND es_favorito = TRUE",
                    (id_usuario,),
                )
                favoritos = cur.fetchone()["favoritos"]
        return True, "Estadísticas obtenidas.", {"total": int(total), "favoritos": int(favoritos)}
    except Exception as e:
        return False, f"Error al obtener estadísticas: {e}", {"total": 0, "favoritos": 0}
