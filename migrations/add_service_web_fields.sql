-- Campos para la web pública (carousel de servicios)
ALTER TABLE services
  ADD COLUMN description VARCHAR(500) NOT NULL DEFAULT '' AFTER service,
  ADD COLUMN category VARCHAR(100) NOT NULL DEFAULT '' AFTER description,
  ADD COLUMN image VARCHAR(500) NOT NULL DEFAULT '' AFTER category;
