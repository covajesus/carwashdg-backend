-- Quita precio del catálogo; el monto queda en tickets_branch_offices_services.total
ALTER TABLE branch_offices_services DROP COLUMN price;
