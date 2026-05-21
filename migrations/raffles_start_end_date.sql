-- Fechas de vigencia del sorteo (omitir si las columnas ya existen).

ALTER TABLE raffles
  ADD COLUMN start_date DATETIME NULL AFTER raffle,
  ADD COLUMN end_date DATETIME NULL AFTER start_date;
