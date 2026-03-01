"""Shared constants for Google business enrichment."""

PLACEHOLDER_TOKENS = {"ND"}
PROGRESS_BATCH_SIZE = 10
TYPE_MISMATCH_STATUS = "type_mismatch"
RECENT_NO_CONTACT_STATUS = "recent_creation_missing_contact"
PLACE_DETAILS_FIELDS = (
    "url,website,name,formatted_address,types,business_status,opening_hours,current_opening_hours,geometry,"
    "reviews,user_ratings_total,formatted_phone_number,international_phone_number"
)
