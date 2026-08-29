-- Supervisor: same branch-scoped access as Encargado, but Tickets stays on today.
-- Encargado (rol_id = 2) remains unrestricted by date in the Tickets screen.
--
-- Existing Encargados whose names contain "David" or "Azumy" remain Encargados.
-- All other active Encargados become Supervisors.

INSERT INTO rols (id, rol, added_date, updated_date)
SELECT 4, 'Supervisor', NOW(), NOW()
WHERE NOT EXISTS (
  SELECT 1
  FROM rols
  WHERE id = 4
);

UPDATE rols
SET rol = 'Supervisor',
    updated_date = NOW()
WHERE id = 4;

UPDATE users
SET rol_id = 4,
    updated_date = NOW()
WHERE rol_id = 2
  AND deleted_date IS NULL
  AND LOWER(TRIM(full_name)) NOT LIKE '%david%'
  AND LOWER(TRIM(full_name)) NOT LIKE '%azumy%';
