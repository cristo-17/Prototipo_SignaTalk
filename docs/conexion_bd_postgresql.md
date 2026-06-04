# Conexión a PostgreSQL
git add docs\conexion_bd_postgresql.md

La aplicación SIGNATALK utiliza PostgreSQL como base de datos local para almacenar usuarios, perfiles, gestos demo, traducciones y frases frecuentes.

La conexión se gestiona desde el archivo `auth_db.py`, donde se configuran los datos del servidor local:

- Host: 127.0.0.1
- Puerto: 5432
- Base de datos: talktome_db
- Usuario: postgres

Las operaciones principales se realizan mediante consultas SQL para insertar, consultar y modificar registros desde la interfaz.