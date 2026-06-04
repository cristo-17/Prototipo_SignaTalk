# Avance funcional de SIGNATALK

## Proyecto
SIGNATALK - Sistema de reconocimiento de movimientos y voz con IA.

## Resumen del avance implementado

En esta versión se consolidó una base funcional del sistema SIGNATALK, integrando interfaz gráfica, conexión a base de datos PostgreSQL, validaciones de formularios, control de roles y módulos principales de comunicación.

## Funcionalidades implementadas

### 1. Login con control de rol
Se implementó una pantalla de inicio de sesión conectada a PostgreSQL, donde el usuario puede ingresar como administrador o como usuario normal.  
El sistema valida las credenciales y verifica el rol antes de permitir el acceso.

### 2. Conexión a PostgreSQL
La aplicación se conecta a una base de datos local PostgreSQL mediante el archivo `auth_db.py`.  
Desde ahí se gestionan las operaciones de consulta, inserción y actualización de datos.

### 3. Cinco formularios conectados a cinco tablas
El sistema cuenta con cinco formularios principales conectados a tablas reales de PostgreSQL:

| Formulario | Tabla |
|---|---|
| Usuarios | usuarios |
| Perfiles de usuario | perfiles_usuario |
| Gestos demo | gestos_demo |
| Traducciones | historial_traducciones |
| Frases frecuentes | frases_frecuentes |

### 4. Validaciones en formularios
Se agregaron validaciones para evitar registros incompletos o incorrectos, como:

- Validación de DNI.
- Validación de correo.
- Validación de teléfono.
- Confirmación de contraseña.
- Campos obligatorios.
- Restricción de selección en campos como rol y tipo de acceso.

### 5. Separación de datos por usuario
Los registros de perfiles, gestos demo, traducciones y frases frecuentes se asocian al usuario propietario mediante `id_usuario`.  
Esto permite que cada usuario visualice y modifique únicamente sus propios datos, mientras que el administrador puede visualizar el propietario de cada registro.

### 6. Formulario de traducciones
El formulario de traducciones integra los módulos principales del proyecto:

- Cámara / LSP demo.
- Texto a voz.
- Voz a texto.
- Guardado de traducciones en historial.

### 7. Frases frecuentes
Se agregó un formulario para registrar frases frecuentes, permitiendo guardar mensajes útiles para la comunicación diaria y reproducirlos mediante texto a voz.

### 8. Diferencia entre administrador y usuario
El rol administrador puede gestionar usuarios y visualizar datos generales del sistema.  
El usuario normal trabaja únicamente con sus propios registros.

## Objetivo del commit
Este documento se agrega como evidencia del avance funcional realizado en el proyecto, sin modificar la lógica ni la interfaz actual del sistema.

## Relación con el control de versiones
Este avance permite demostrar el uso de Git para registrar cambios importantes del proyecto mediante commits, manteniendo trazabilidad del desarrollo.