-- Grupos diarios de lavadores (solo el día actual; no persisten al día siguiente).
CREATE TABLE IF NOT EXISTS washer_daily_groups (
  id INT AUTO_INCREMENT PRIMARY KEY,
  branch_office_id INT NOT NULL,
  group_date DATE NOT NULL,
  name VARCHAR(255) NOT NULL,
  added_date DATETIME NULL,
  updated_date DATETIME NULL,
  deleted_date DATETIME NULL,
  KEY idx_wdg_branch_date (branch_office_id, group_date)
);

CREATE TABLE IF NOT EXISTS washer_daily_group_members (
  id INT AUTO_INCREMENT PRIMARY KEY,
  group_id INT NOT NULL,
  washer_id INT NOT NULL,
  added_date DATETIME NULL,
  deleted_date DATETIME NULL,
  KEY idx_wdgm_group (group_id),
  KEY idx_wdgm_washer (washer_id)
);

ALTER TABLE tickets_branch_offices_services
  ADD COLUMN washer_daily_group_id INT NULL AFTER washer_id;
