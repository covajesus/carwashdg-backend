-- Activar meta manualmente (aplica base + % meta aunque no se alcance la venta del día)
ALTER TABLE washer_pay_settlements
  ADD COLUMN manual_goal_met TINYINT(1) NOT NULL DEFAULT 0
  AFTER is_paid;
