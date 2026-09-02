-- Expense types catalog with Caja/Banco classification.
-- Also removes per-expense classification (moved onto the type).

CREATE TABLE IF NOT EXISTS expense_types (
  id INT NOT NULL AUTO_INCREMENT,
  code VARCHAR(64) NOT NULL,
  name VARCHAR(255) NOT NULL,
  classification VARCHAR(16) NOT NULL DEFAULT 'bank',
  admin_only TINYINT(1) NOT NULL DEFAULT 0,
  requires_photo TINYINT(1) NOT NULL DEFAULT 1,
  added_date DATETIME NULL,
  updated_date DATETIME NULL,
  deleted_date DATETIME NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_expense_types_code (code)
);

INSERT INTO expense_types (code, name, classification, admin_only, requires_photo, added_date, updated_date)
SELECT 'insumos', 'Insumos y químicos', 'bank', 0, 1, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM expense_types WHERE code = 'insumos');

INSERT INTO expense_types (code, name, classification, admin_only, requires_photo, added_date, updated_date)
SELECT 'servicios_basicos', 'Servicios básicos (luz, agua, gas)', 'bank', 0, 1, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM expense_types WHERE code = 'servicios_basicos');

INSERT INTO expense_types (code, name, classification, admin_only, requires_photo, added_date, updated_date)
SELECT 'mantenimiento', 'Mantenimiento y equipos', 'bank', 0, 1, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM expense_types WHERE code = 'mantenimiento');

INSERT INTO expense_types (code, name, classification, admin_only, requires_photo, added_date, updated_date)
SELECT 'nomina', 'Nómina y sueldos', 'bank', 0, 1, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM expense_types WHERE code = 'nomina');

INSERT INTO expense_types (code, name, classification, admin_only, requires_photo, added_date, updated_date)
SELECT 'arriendo', 'Arriendo', 'bank', 1, 0, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM expense_types WHERE code = 'arriendo');

INSERT INTO expense_types (code, name, classification, admin_only, requires_photo, added_date, updated_date)
SELECT 'marketing', 'Marketing y publicidad', 'bank', 0, 1, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM expense_types WHERE code = 'marketing');

INSERT INTO expense_types (code, name, classification, admin_only, requires_photo, added_date, updated_date)
SELECT 'transporte', 'Transporte y combustible', 'bank', 0, 1, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM expense_types WHERE code = 'transporte');

INSERT INTO expense_types (code, name, classification, admin_only, requires_photo, added_date, updated_date)
SELECT 'prestamo', 'Préstamo', 'bank', 0, 1, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM expense_types WHERE code = 'prestamo');

INSERT INTO expense_types (code, name, classification, admin_only, requires_photo, added_date, updated_date)
SELECT 'otros', 'Otros', 'bank', 0, 1, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM expense_types WHERE code = 'otros');

SET @stmt = (
  SELECT IF(
    COUNT(*) = 0,
    "ALTER TABLE expenses ADD COLUMN expense_type_id INT NULL AFTER expense_type",
    'DO 0'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'expenses'
    AND COLUMN_NAME = 'expense_type_id'
);
PREPARE alter_expenses_type_id FROM @stmt;
EXECUTE alter_expenses_type_id;
DEALLOCATE PREPARE alter_expenses_type_id;

UPDATE expenses e
INNER JOIN expense_types t
  ON t.code = e.expense_type
 AND t.deleted_date IS NULL
SET e.expense_type_id = t.id
WHERE e.expense_type_id IS NULL
  AND e.expense_type IS NOT NULL
  AND e.expense_type <> '';

SET @drop_class = (
  SELECT IF(
    COUNT(*) > 0,
    "ALTER TABLE expenses DROP COLUMN expense_classification_id",
    'DO 0'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'expenses'
    AND COLUMN_NAME = 'expense_classification_id'
);
PREPARE drop_expense_class FROM @drop_class;
EXECUTE drop_expense_class;
DEALLOCATE PREPARE drop_expense_class;

DROP TABLE IF EXISTS expense_classifications;
