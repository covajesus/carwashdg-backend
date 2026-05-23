-- Fecha del gasto (día contable), distinta de added_date (alta en sistema).
-- Omitir si la columna ya existe.

ALTER TABLE expenses
  ADD COLUMN expense_date DATE NULL AFTER amount;

UPDATE expenses
SET expense_date = DATE(added_date)
WHERE expense_date IS NULL AND added_date IS NOT NULL;

ALTER TABLE expenses
  ADD KEY idx_expenses_expense_date (expense_date);
