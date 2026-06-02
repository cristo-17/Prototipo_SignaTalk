-- Consultas para mostrar en pgAdmin durante la exposición

SELECT id, usuario, nombre_completo, rol, activo, creado_en, ultimo_login
FROM usuarios
ORDER BY id DESC;

SELECT *
FROM configuracion_usuario
ORDER BY id DESC;

SELECT *
FROM gestos_demo
ORDER BY id;

SELECT h.id, u.usuario, h.tipo_traduccion, h.texto_original, h.texto_traducido, h.es_favorito, h.fecha_hora
FROM historial_traducciones h
JOIN usuarios u ON u.id = h.id_usuario
ORDER BY h.fecha_hora DESC;

SELECT f.id, u.usuario, f.frase, f.categoria, f.fecha_creacion
FROM frases_favoritas f
JOIN usuarios u ON u.id = f.id_usuario
ORDER BY f.fecha_creacion DESC;
