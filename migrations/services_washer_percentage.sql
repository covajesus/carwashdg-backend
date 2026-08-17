-- Per-service washer commission %. 0 (or NULL) = use washer day/Sunday %.
-- Safe to re-run: does nothing if the column already exists.
SET @stmt = (
  SELECT IF(
    COUNT(*) = 0,
    "ALTER TABLE services ADD COLUMN washer_percentage VARCHAR(255) NULL DEFAULT '0' AFTER description",
    'DO 0'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'services'
    AND COLUMN_NAME = 'washer_percentage'
);
PREPARE alter_services FROM @stmt;
EXECUTE alter_services;
DEALLOCATE PREPARE alter_services;

UPDATE services SET washer_percentage = '0' WHERE washer_percentage IS NULL;
