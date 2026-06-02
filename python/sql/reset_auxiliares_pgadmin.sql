-- Ejecutar en pgAdmin dentro de la base de datos talktome_db.
-- No borra la tabla usuarios ni tus cuentas creadas.
DROP TABLE IF EXISTS frases_favoritas CASCADE;
DROP TABLE IF EXISTS retroalimentacion CASCADE;
DROP TABLE IF EXISTS historial_traducciones CASCADE;
DROP TABLE IF EXISTS configuracion_usuario CASCADE;
DROP TABLE IF EXISTS gestos_demo CASCADE;

-- La app volvera a crear estas tablas al iniciar.
