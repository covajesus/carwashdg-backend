-- Porcentajes / valores del lavador por sucursal

ALTER TABLE branch_offices_washers
  ADD COLUMN sunday_percentage VARCHAR(255) NULL AFTER washer_id,
  ADD COLUMN week_percentage VARCHAR(255) NULL AFTER sunday_percentage;
