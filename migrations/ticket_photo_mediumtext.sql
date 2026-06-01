-- Fotos en base64 superan TEXT (~64 KB). Esta foto puede superar 200 KB.
-- Ejecutar UNA VEZ en el MySQL de producción:

ALTER TABLE tickets
  MODIFY COLUMN photo_url MEDIUMTEXT NULL;
