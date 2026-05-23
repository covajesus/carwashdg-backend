-- Servicios de catálogo van directo a tickets_branch_offices_services (service_id).
-- Elimina la tabla intermedia branch_offices_services.

ALTER TABLE tickets_branch_offices_services
  ADD COLUMN service_id INT NULL AFTER ticket_id;

UPDATE tickets_branch_offices_services t
JOIN branch_offices_services b ON b.id = t.branch_office_service_id
SET t.service_id = b.service_id
WHERE t.branch_office_service_id IS NOT NULL
  AND t.branch_office_service_id > 0;

ALTER TABLE tickets_branch_offices_services
  DROP COLUMN branch_office_service_id;

DROP TABLE IF EXISTS branch_offices_services;
