CREATE TABLE IF NOT EXISTS expenses (
  id INT NOT NULL AUTO_INCREMENT,
  expense_type VARCHAR(64) NOT NULL,
  amount INT NOT NULL,
  photo_url MEDIUMTEXT NULL,
  added_date DATETIME NULL,
  updated_date DATETIME NULL,
  deleted_date DATETIME NULL,
  PRIMARY KEY (id),
  KEY idx_expenses_type (expense_type),
  KEY idx_expenses_added_date (added_date)
);
