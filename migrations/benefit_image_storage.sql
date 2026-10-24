-- Store uploaded "why choose us" photos in the configuration row.
-- Safe to re-run: each statement does nothing if that column is already MEDIUMTEXT.

SET @stmt = (
  SELECT IF(
    DATA_TYPE = 'mediumtext',
    'DO 0',
    'ALTER TABLE configurations MODIFY benefit_ecological_image MEDIUMTEXT NOT NULL'
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
    DATA_TYPE = 'mediumtext',
    'DO 0',
    'ALTER TABLE configurations MODIFY benefit_fast_image MEDIUMTEXT NOT NULL'
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
    DATA_TYPE = 'mediumtext',
    'DO 0',
    'ALTER TABLE configurations MODIFY benefit_professional_image MEDIUMTEXT NOT NULL'
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
    DATA_TYPE = 'mediumtext',
    'DO 0',
    'ALTER TABLE configurations MODIFY benefit_premium_image MEDIUMTEXT NOT NULL'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'configurations'
    AND COLUMN_NAME = 'benefit_premium_image'
);
PREPARE alter_configurations FROM @stmt;
EXECUTE alter_configurations;
DEALLOCATE PREPARE alter_configurations;
