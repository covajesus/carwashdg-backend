-- Fotos de ticket en base64 requieren más de VARCHAR(500).
-- Ejecutar una vez en producción si photo_url es VARCHAR(500) o falta la columna.

ALTER TABLE tickets
  MODIFY COLUMN photo_url MEDIUMTEXT NULL;
