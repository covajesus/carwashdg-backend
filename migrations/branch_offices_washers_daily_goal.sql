-- Meta diaria y % de meta para lavadores en sucursal (omitir si ya existen las columnas).

ALTER TABLE branch_offices_washers
  ADD COLUMN daily_goal VARCHAR(255) NULL AFTER week_percentage,
  ADD COLUMN daily_goal_percentage VARCHAR(255) NULL AFTER daily_goal;
