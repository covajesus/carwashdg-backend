-- Gastos por sucursal.

ALTER TABLE expenses
  ADD COLUMN branch_office_id INT NULL AFTER expense_date,
  ADD KEY idx_expenses_branch_office (branch_office_id);
