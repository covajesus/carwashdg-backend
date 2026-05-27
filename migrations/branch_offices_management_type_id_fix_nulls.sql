-- Si la columna ya existe con NULL, normalizar a Administrada (1).

UPDATE branch_offices
  SET management_type_id = 1
  WHERE management_type_id IS NULL;

ALTER TABLE branch_offices
  MODIFY COLUMN management_type_id INT NOT NULL DEFAULT 1;
