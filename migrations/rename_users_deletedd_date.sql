-- Local dev fix: align users soft-delete column with production (deleted_date).
ALTER TABLE users
  CHANGE COLUMN deletedd_date deleted_date DATETIME NULL;
