-- Vincula números de rifa con cliente y ticket (omitir si las columnas ya existen).

ALTER TABLE raffles_numbers
  ADD COLUMN customer_id INT NULL AFTER raffle_id,
  ADD COLUMN ticket_id INT NULL AFTER customer_id;
