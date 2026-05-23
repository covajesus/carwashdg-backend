CREATE TABLE IF NOT EXISTS washer_pay_settlements (
  id INT NOT NULL AUTO_INCREMENT,
  branch_office_id INT NOT NULL,
  washer_id INT NOT NULL,
  pay_date DATE NOT NULL,
  is_paid TINYINT(1) NOT NULL DEFAULT 0,
  added_date DATETIME NULL,
  updated_date DATETIME NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_washer_pay_settlement (branch_office_id, washer_id, pay_date),
  KEY idx_washer_pay_settlement_date (pay_date)
);
