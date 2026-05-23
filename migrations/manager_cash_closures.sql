-- Cierre de caja diario por encargado (rol 2).
-- status_id: 0 = caja abierta, 1 = caja cerrada (ya vio ganancias ese día).

CREATE TABLE IF NOT EXISTS manager_cash_closures (
  id INT NOT NULL AUTO_INCREMENT,
  manager_id INT NOT NULL,
  closure_date DATE NOT NULL,
  status_id INT NOT NULL DEFAULT 0,
  added_date DATETIME NULL,
  updated_date DATETIME NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_manager_cash_closure_day (manager_id, closure_date),
  KEY idx_manager_cash_closure_date (closure_date),
  KEY idx_manager_cash_closure_status (status_id)
);
