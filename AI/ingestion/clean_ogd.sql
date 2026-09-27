-- Cleans one data.gov.in dataset after its columns are mapped into table raw.
-- Rows without a scheme name are dropped; repeated names keep their first occurrence.
SELECT TRIM(name) AS name,
       NULLIF(TRIM(description), '') AS description,
       NULLIF(TRIM(eligibilityText), '') AS eligibilityText,
       NULLIF(TRIM(benefits), '') AS benefits,
       NULLIF(TRIM(ministry), '') AS ministry,
       NULLIF(TRIM(state), '') AS state
FROM raw
WHERE row_no IN (
    SELECT MIN(row_no)
    FROM raw
    WHERE TRIM(COALESCE(name, '')) <> ''
    GROUP BY LOWER(TRIM(name))
)
ORDER BY row_no;
