SELECT
    e.naf_code,
    ns.name AS naf_subcategory_name,
    e.siret,
    e.name AS establishment_name,
    e.google_place_id,
    e.google_place_url,
    e.google_listing_age_status,
    e.google_match_confidence,
    e.updated_at AS last_google_check
FROM establishments AS e
LEFT JOIN naf_subcategories AS ns
       ON ns.naf_code = e.naf_code
WHERE LOWER(e.google_check_status) = 'type_mismatch'
ORDER BY e.naf_code, e.updated_at DESC, e.siret;