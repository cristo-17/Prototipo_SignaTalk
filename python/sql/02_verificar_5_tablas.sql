SELECT 'usuarios' AS tabla, COUNT(*) AS registros FROM usuarios
UNION ALL
SELECT 'perfiles_usuario', COUNT(*) FROM perfiles_usuario
UNION ALL
SELECT 'gestos_demo', COUNT(*) FROM gestos_demo
UNION ALL
SELECT 'historial_traducciones', COUNT(*) FROM historial_traducciones
UNION ALL
SELECT 'frases_frecuentes', COUNT(*) FROM frases_frecuentes;

-- Verificacion de datos por usuario
SELECT u.usuario, COUNT(g.id) AS gestos_por_usuario
FROM usuarios u
LEFT JOIN gestos_demo g ON g.id_usuario = u.id
GROUP BY u.usuario
ORDER BY u.usuario;

SELECT u.usuario, COUNT(f.id) AS frases_por_usuario
FROM usuarios u
LEFT JOIN frases_frecuentes f ON f.id_usuario = u.id
GROUP BY u.usuario
ORDER BY u.usuario;
