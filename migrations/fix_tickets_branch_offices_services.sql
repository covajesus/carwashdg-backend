-- Asegura PK autoincrement y columnas correctas en líneas de ticket.
-- Nombre de tabla: tickets_branch_offices_services

ALTER TABLE tickets_branch_offices_services
  MODIFY COLUMN id INT NOT NULL AUTO_INCREMENT,
  MODIFY COLUMN ticket_id INT NULL,
  MODIFY COLUMN branch_office_service_id INT NULL,
  MODIFY COLUMN washer_id INT NULL,
  MODIFY COLUMN total INT NULL COMMENT 'Precio del servicio al momento del ticket',
  MODIFY COLUMN added_date DATETIME NULL,
  MODIFY COLUMN updated_date VARCHAR(255) NULL,
  MODIFY COLUMN deleted_date DATETIME NULL;

-- Rellena total en líneas antiguas desde el catálogo vigente (opcional, ejecutar una vez)
-- UPDATE tickets_branch_offices_services t
-- INNER JOIN branch_offices_services b ON b.id = t.branch_office_service_id
-- SET t.total = ROUND(b.price)
-- WHERE t.total IS NULL AND t.deleted_date IS NULL AND t.branch_office_service_id IS NOT NULL;
