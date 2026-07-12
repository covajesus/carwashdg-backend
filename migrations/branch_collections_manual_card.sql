-- Manual collection: cash + card (+ card tax).
ALTER TABLE branch_collections
  ADD COLUMN cash_amount INT NOT NULL DEFAULT 0 AFTER gross_amount,
  ADD COLUMN card_gross INT NOT NULL DEFAULT 0 AFTER cash_amount,
  ADD COLUMN card_tax INT NOT NULL DEFAULT 0 AFTER card_gross;

-- If an earlier draft added card_iva, rename it:
-- ALTER TABLE branch_collections CHANGE COLUMN card_iva card_tax INT NOT NULL DEFAULT 0;

UPDATE branch_collections
SET cash_amount = gross_amount
WHERE cash_amount = 0
  AND card_gross = 0
  AND gross_amount > 0
  AND deleted_date IS NULL;
