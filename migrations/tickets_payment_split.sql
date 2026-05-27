ALTER TABLE tickets
  ADD COLUMN payment_efectivo_amount INT NULL AFTER payment_type_id,
  ADD COLUMN payment_transbank_amount INT NULL AFTER payment_efectivo_amount;
