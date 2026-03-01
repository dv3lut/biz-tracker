WITH params AS (
    SELECT
        0.40::numeric AS min_confidence,  -- ⇐ remplace par ta borne basse
        0.80::numeric AS max_confidence   -- ⇐ remplace par ta borne haute
)
SELECT
    e.naf_code,
    ns.name AS naf_subcategory_name,
    e.siret,
    e.name AS establishment_name,
    e.google_match_confidence,
    e.google_place_id,
    e.google_place_url,
    e.google_listing_age_status,
    e.libelle_commune,
    e.code_postal,
    e.updated_at AS last_google_check
FROM establishments AS e
CROSS JOIN params AS p
LEFT JOIN naf_subcategories AS ns
       ON ns.naf_code = e.naf_code
WHERE LOWER(e.google_check_status) = 'not_found'
  AND e.google_match_confidence BETWEEN p.min_confidence AND p.max_confidence
ORDER BY e.naf_code, e.google_match_confidence DESC, e.updated_at DESC;