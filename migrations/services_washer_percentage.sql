-- Per-service washer commission %. 0 (or NULL) = use washer day/Sunday %.
ALTER TABLE services
  ADD COLUMN washer_percentage VARCHAR(255) NULL DEFAULT '0'
  AFTER description;
