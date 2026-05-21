-- Nombre del servicio escrito a mano (servicios adicionales; branch_office_service_id = 0).

ALTER TABLE tickets_branch_offices_services
  ADD COLUMN additional_service VARCHAR(255) NULL
  AFTER washer_id;
