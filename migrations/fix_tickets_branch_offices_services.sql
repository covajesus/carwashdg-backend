-- Asegura PK autoincrement y columnas correctas en líneas de ticket.
-- Nombre de tabla: tickets_branch_offices_services

ALTER TABLE tickets_branch_offices_services
  MODIFY COLUMN id INT NOT NULL AUTO_INCREMENT,
  MODIFY COLUMN ticket_id INT NULL,
  MODIFY COLUMN branch_office_service_id INT NULL,
  MODIFY COLUMN washer_id INT NULL,
  MODIFY COLUMN added_date DATETIME NULL,
  MODIFY COLUMN updated_date VARCHAR(255) NULL,
  MODIFY COLUMN deleted_date DATETIME NULL;
