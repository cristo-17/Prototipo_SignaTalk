from getpass import getpass
from auth_db import inicializar_bd, crear_usuario


def main():
    ok, mensaje = inicializar_bd()
    print(mensaje)
    if not ok:
        return

    usuario = input("Usuario: ").strip().lower()
    nombre = input("Nombre completo: ").strip()
    rol = input("Rol (admin/usuario) [usuario]: ").strip() or "usuario"
    password = getpass("Contraseña: ")
    repetir = getpass("Repetir contraseña: ")

    if password != repetir:
        print("Las contraseñas no coinciden.")
        return

    ok, mensaje = crear_usuario(usuario, password, nombre, rol)
    print(mensaje)


if __name__ == "__main__":
    main()
