-- Miembros de lavadores grupales (varios nombres, una sola cuenta y compensación).
CREATE TABLE IF NOT EXISTS washer_group_members (
  id INT AUTO_INCREMENT PRIMARY KEY,
  washer_id INT NOT NULL,
  name VARCHAR(255) NOT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  added_date DATETIME NULL,
  updated_date DATETIME NULL,
  deleted_date DATETIME NULL,
  KEY idx_washer_group_members_washer (washer_id)
);
