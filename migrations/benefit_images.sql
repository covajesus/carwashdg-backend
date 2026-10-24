-- Public "why choose us" card images. Empty means the site uses its local photo.
-- Safe to re-run: each statement does nothing if that column already exists.

SET @stmt = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE configurations ADD COLUMN benefit_ecological_image VARCHAR(2048) NOT NULL DEFAULT ''''',
    'DO 0'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'configurations'
    AND COLUMN_NAME = 'benefit_ecological_image'
);
PREPARE alter_configurations FROM @stmt;
EXECUTE alter_configurations;
DEALLOCATE PREPARE alter_configurations;

SET @stmt = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE configurations ADD COLUMN benefit_fast_image VARCHAR(2048) NOT NULL DEFAULT ''''',
    'DO 0'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'configurations'
    AND COLUMN_NAME = 'benefit_fast_image'
);
PREPARE alter_configurations FROM @stmt;
EXECUTE alter_configurations;
DEALLOCATE PREPARE alter_configurations;

SET @stmt = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE configurations ADD COLUMN benefit_professional_image VARCHAR(2048) NOT NULL DEFAULT ''''',
    'DO 0'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'configurations'
    AND COLUMN_NAME = 'benefit_professional_image'
);
PREPARE alter_configurations FROM @stmt;
EXECUTE alter_configurations;
DEALLOCATE PREPARE alter_configurations;

SET @stmt = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE configurations ADD COLUMN benefit_premium_image VARCHAR(2048) NOT NULL DEFAULT ''''',
    'DO 0'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'configurations'
    AND COLUMN_NAME = 'benefit_premium_image'
);
PREPARE alter_configurations FROM @stmt;
EXECUTE alter_configurations;
DEALLOCATE PREPARE alter_configurations;
