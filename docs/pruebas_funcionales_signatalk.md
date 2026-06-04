# Pruebas funcionales de SIGNATALK - Commit 05

## Proyecto
SIGNATALK - Sistema de reconocimiento de movimientos y voz con IA.

## Objetivo
Registrar las pruebas funcionales realizadas sobre los módulos principales del prototipo, verificando que las funciones implementadas respondan correctamente desde la interfaz y la base de datos.

## Pruebas realizadas

### 1. Prueba de inicio de sesión
Se verificó que el usuario pueda ingresar al sistema mediante credenciales registradas en PostgreSQL.

Resultado:
- El sistema permite el acceso si el usuario y contraseña son correctos.
- El tipo de acceso diferencia entre administrador y usuario normal.

### 2. Prueba de formulario de usuarios
Se verificó la creación y modificación de usuarios desde la interfaz.

Resultado:
- El formulario permite registrar usuarios.
- El rol se selecciona desde una lista.
- La contraseña se valida mediante confirmación.

### 3. Prueba de formulario de perfiles
Se verificó el registro de datos personales del usuario.

Resultado:
- Se validan campos como DNI, correo y teléfono.
- Los datos se guardan en la tabla `perfiles_usuario`.

### 4. Prueba de gestos demo
Se verificó que cada usuario tenga sus propios gestos demo.

Resultado:
- Los gestos se filtran por usuario propietario.
- Al modificar un gesto, el cambio no afecta a otros usuarios.

### 5. Prueba de traducciones
Se verificó el funcionamiento de los módulos de traducción.

Resultado:
- La cámara demo se abre desde la interfaz.
- El módulo Texto a Voz reproduce el texto ingresado.
- El módulo Voz a Texto permite capturar audio y convertirlo a texto.
- Las traducciones se guardan asociadas al usuario actual.

### 6. Prueba de frases frecuentes
Se verificó que cada usuario pueda registrar sus propias frases frecuentes.

Resultado:
- Las frases se filtran por usuario propietario.
- Se pueden reproducir frases mediante texto a voz.

## Conclusión
Las pruebas funcionales permitieron comprobar que el prototipo integra interfaz gráfica, conexión a PostgreSQL, validaciones, roles y módulos de comunicación. Además, se verificó que los registros se mantengan separados por usuario mediante `id_usuario`.