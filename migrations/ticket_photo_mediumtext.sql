-- Fotos de ticket en base64: ampliar columna (VARCHAR(500) es insuficiente).
-- Ejecutar una vez en producción.

ALTER TABLE tickets
  MODIFY COLUMN photo_url TEXT NULL;
