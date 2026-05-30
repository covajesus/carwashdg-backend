ALTER TABLE configurations
  ADD COLUMN coin_round_status_id INT NOT NULL DEFAULT 0
  AFTER instagram_url;
