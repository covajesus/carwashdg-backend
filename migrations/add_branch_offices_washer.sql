CREATE TABLE IF NOT EXISTS branch_offices_washers (
  id INT NOT NULL AUTO_INCREMENT,
  branch_office_id INT NULL,
  washer_id INT NULL,
  added_date DATETIME NULL,
  updated_date DATETIME NULL,
  deleted_date DATETIME NULL,
  PRIMARY KEY (id),
  KEY idx_branch_offices_washers_washer (washer_id),
  KEY idx_branch_offices_washers_branch (branch_office_id)
);
