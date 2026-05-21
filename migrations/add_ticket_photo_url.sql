-- Foto del vehículo al crear ticket (URL pública servida por el admin).
ALTER TABLE tickets
  ADD COLUMN photo_url VARCHAR(500) NULL AFTER license_plate_id;
