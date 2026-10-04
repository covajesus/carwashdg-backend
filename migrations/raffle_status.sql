-- Public site raffle visibility. 1 = visible, 0 = hidden.
-- Existing sites stay visible until an admin turns the raffle off.
-- Safe to re-run: does nothing if the column already exists.

SET @stmt = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE configurations ADD COLUMN raffle_status_id INT NOT NULL DEFAULT 1',
    'DO 0'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'configurations'
    AND COLUMN_NAME = 'raffle_status_id'
);
PREPARE alter_configurations FROM @stmt;
EXECUTE alter_configurations;
DEALLOCATE PREPARE alter_configurations;
