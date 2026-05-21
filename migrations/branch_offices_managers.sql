-- Asignación sucursal ↔ gerente (misma idea que branch_offices_washers)
CREATE TABLE IF NOT EXISTS branch_offices_managers (
  id INT NOT NULL AUTO_INCREMENT,
  branch_office_id INT NULL,
  manager_id INT NULL,
  added_date DATETIME NULL,
  updated_date DATETIME NULL,
  deleted_date DATETIME NULL,
  PRIMARY KEY (id)
);
