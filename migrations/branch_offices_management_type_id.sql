-- Tipo de gestión: 1 = Administrada, 2 = Subarriendo

ALTER TABLE branch_offices
  ADD COLUMN management_type_id INT NOT NULL DEFAULT 1 AFTER branch_office;
