CREATE TABLE IF NOT EXISTS branch_collections (
  id INT NOT NULL AUTO_INCREMENT,
  branch_office_id INT NOT NULL,
  collection_date DATE NOT NULL,
  gross_amount INT NOT NULL DEFAULT 0,
  added_date DATETIME NULL,
  updated_date DATETIME NULL,
  deleted_date DATETIME NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_branch_collections_branch_date (branch_office_id, collection_date),
  KEY idx_branch_collections_branch (branch_office_id),
  KEY idx_branch_collections_date (collection_date)
);
