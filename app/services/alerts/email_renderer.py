from __future__ import annotations

from datetime import date
from html import escape
from typing import Final, Sequence

from app.db import models
from app.services.client_service import ClientFilterSummary
from app.utils.google_listing import LISTING_AGE_STATUS_LABELS, normalize_listing_age_status

from .formatter import EstablishmentFormatter


def _get_linkedin_title_for_director(director: models.Director) -> str:
    """Get the title/poste to display for LinkedIn button.

    Priority: profileData.title > director.quality > "Dirigeant"
    """
    profile_data = getattr(director, "linkedin_profile_data", None)
    if profile_data:
        title = profile_data.get("title")
        if title and isinstance(title, str) and title.strip():
            return title.strip()
    quality = getattr(director, "quality", None)
    if quality and isinstance(quality, str) and quality.strip():
        return quality.strip()
    return "Dirigeant"


def _build_linkedin_buttons_html(
    establishment: models.Establishment,
    theme: dict[str, str],
) -> tuple[list[str], str]:
    """Build LinkedIn button(s) for directors with profiles.

    Returns:
        Tuple of (text_lines, html_block) for the LinkedIn section.
    """
    text_lines: list[str] = []
    html_parts: list[str] = []

    directors = getattr(establishment, "directors", None) or []
    directors_with_linkedin = [
        d for d in directors
        if getattr(d, "is_physical_person", False) and getattr(d, "linkedin_profile_url", None)
    ]

    if not directors_with_linkedin:
        return text_lines, ""

    for director in directors_with_linkedin:
        title = _get_linkedin_title_for_director(director)
        url = director.linkedin_profile_url
        button_text = f"Contacter le {title} sur LinkedIn"

        text_lines.append(f"  LinkedIn : {url}")

        html_parts.append(
            f"<a href=\"{escape(url)}\" style=\"display:inline-block;margin-right:8px;margin-top:4px;"
            f"padding:6px 12px;background:#0077B5;color:#ffffff;text-decoration:none;"
            f"border-radius:6px;font-weight:600;font-size:12px;\">{escape(button_text)}</a>"
        )

    if html_parts:
        html_block = (
            f"<div style=\"margin-top:10px;display:flex;flex-wrap:wrap;gap:4px;\">"
            + "".join(html_parts)
            + "</div>"
        )
        return text_lines, html_block

    return text_lines, ""


STATUS_SECTION_ORDER: Final[tuple[str, ...]] = (
    "recent_creation",
    "recent_creation_missing_contact",
    "not_recent_creation",
)

# Thème (mail client) : centraliser les couleurs pour pouvoir les ajuster facilement.
CLIENT_EMAIL_THEME: Final[dict[str, str]] = {
    "page_bg": "#f9fafb",
    "card_bg": "#ffffff",
    "card_shadow": "0 1px 3px rgba(0,0,0,0.1)",
    "border": "#e5e7eb",
    "text": "#111827",
    "text_muted": "#6b7280",
    "text_subtle": "#374151",
    "brand": "#2563eb",
    "link_muted": "#9ca3af",
    "item_bg": "#f9fafb",
}

# Labels pour les emails clients (différents de ceux pour les admins)
CLIENT_STATUS_LABELS: Final[dict[str, str]] = {
    "recent_creation": "Création récente",
    "recent_creation_missing_contact": "Création récente sans contact",
    "not_recent_creation": "Modification administrative récente",
    "unknown": "Non déterminé",
}

STATUS_TITLE_OVERRIDES: Final[dict[str, str]] = {
    "recent_creation_missing_contact": "Création récente sans contact",
    "not_recent_creation": "Modification administrative récente",
}

# Couleurs pour les badges de statut
STATUS_COLORS: Final[dict[str, dict[str, str]]] = {
    # Vert légèrement plus foncé (bordure + contraste)
    "recent_creation": {"bg": "#bbf7d0", "text": "#166534", "border": "#22c55e"},
    "recent_creation_missing_contact": {"bg": "#fef3c7", "text": "#92400e", "border": "#fcd34d"},
    "not_recent_creation": {"bg": "#dbeafe", "text": "#1e40af", "border": "#93c5fd"},
    "unknown": {"bg": "#f3f4f6", "text": "#6b7280", "border": "#d1d5db"},
}
# Couleur pour les établissements sans fiche Google (violet/indigo — distinct des autres)
NO_GOOGLE_CARD_COLOR: Final[dict[str, str]] = {
    "bg": "#f5f3ff",
    "border": "#8b5cf6",
    "text": "#5b21b6",
}
MONTH_LABELS_FR: Final[dict[int, str]] = {
    1: "janvier",
    2: "février",
    3: "mars",
    4: "avril",
    5: "mai",
    6: "juin",
    7: "juillet",
    8: "août",
    9: "septembre",
    10: "octobre",
    11: "novembre",
    12: "décembre",
}


def _format_date_fr(value: date) -> str:
    month_label = MONTH_LABELS_FR.get(value.month, str(value.month))
    return f"{value.day} {month_label} {value.year}"


def _format_month_year_fr(value: date) -> str:
    month_label = MONTH_LABELS_FR.get(value.month, str(value.month))
    return f"{month_label.capitalize()} {value.year}"


def _section_title_for_status(status: str) -> str:
    """Retourne le titre de section pour les emails clients."""
    if status in STATUS_TITLE_OVERRIDES:
        return STATUS_TITLE_OVERRIDES[status]
    return CLIENT_STATUS_LABELS.get(status, status)


def _format_listing_status_labels(statuses: list[str]) -> list[str]:
    """Formate les labels de statut pour l'affichage dans les emails clients."""
    return [CLIENT_STATUS_LABELS.get(status, status) for status in statuses]


def _get_status_badge_html(status: str, label: str) -> str:
    """Génère un badge HTML coloré pour un statut."""
    colors = STATUS_COLORS.get(status, STATUS_COLORS["unknown"])
    return (
        f'<span style="display:inline-block;padding:3px 10px;border-radius:10px;'
        f'background:{colors["bg"]};color:{colors["text"]};border:1px solid {colors["border"]};'
        f'font-size:12px;font-weight:500;">{escape(label)}</span>'
    )


def _order_establishments_by_status(
    establishments: Sequence[models.Establishment],
    *,
    ordered_statuses: Sequence[str],
) -> list[models.Establishment]:
    ordered: list[models.Establishment] = []
    remaining: list[models.Establishment] = []
    buckets: dict[str, list[models.Establishment]] = {status: [] for status in ordered_statuses}
    for establishment in establishments:
        normalized_status = normalize_listing_age_status(getattr(establishment, "google_listing_age_status", None))
        if normalized_status in buckets:
            buckets[normalized_status].append(establishment)
        else:
            remaining.append(establishment)
    for status in ordered_statuses:
        ordered.extend(buckets.get(status, []))
    ordered.extend(remaining)
    return ordered


def get_client_listing_status_label(status: str | None) -> str:
    """Retourne le label client pour un statut de fiche Google.
    
    Cette fonction est exportée pour être utilisée dans d'autres modules
    (ex: export_service) qui ont besoin des labels clients.
    """
    normalized = normalize_listing_age_status(status)
    return CLIENT_STATUS_LABELS.get(normalized, CLIENT_STATUS_LABELS["unknown"])


def _build_client_scope_summary(
    client: models.Client,
    theme: dict[str, str],
) -> tuple[list[str], str]:
    """Construit un résumé texte + HTML du périmètre surveillé (départements + catégories)."""
    # France a 101 depts (96 métro + 5 DOM). Seuil conservateur pour détecter "tous sélectionnés".
    _FRANCE_DEPT_THRESHOLD = 95
    client_depts = getattr(client, "departments", []) or []
    all_france = len(client_depts) == 0 or len(client_depts) >= _FRANCE_DEPT_THRESHOLD

    # Groupement par région (si périmètre spécifique)
    region_groups: dict[str, list[tuple[str, str]]] = {}
    if not all_france:
        for dept in client_depts:
            region = getattr(dept, "region", None)
            region_name = getattr(region, "name", "Autres") if region else "Autres"
            region_groups.setdefault(region_name, []).append((dept.code, dept.name))
        for key in region_groups:
            region_groups[key].sort(key=lambda x: x[0].zfill(3))

    # Catégories (via abonnements)
    seen_cats: set[str] = set()
    category_labels: list[str] = []
    client_category_ids = {str(v) for v in getattr(client, "category_ids", []) or []}
    for subscription in getattr(client, "subscriptions", []) or []:
        subcategory = getattr(subscription, "subcategory", None)
        if not subcategory or not getattr(subcategory, "is_active", True):
            continue
        for category in getattr(subcategory, "categories", []) or []:
            cat_id = getattr(category, "id", None)
            if client_category_ids and cat_id is not None and str(cat_id) not in client_category_ids:
                continue
            cat_name = getattr(category, "name", None)
            if cat_name and cat_name not in seen_cats:
                seen_cats.add(cat_name)
                category_labels.append(cat_name)
    category_labels.sort()

    if all_france and not category_labels:
        return [], ""

    sorted_regions = sorted(region_groups.keys())

    # --- Version texte ---
    text_lines: list[str] = []
    if all_france:
        text_lines.append("🌍 Couverture : France entière")
    else:
        region_text_parts = []
        for region_name in sorted_regions:
            depts = region_groups[region_name]
            dept_str = ", ".join(f"{code} {name}" for code, name in depts)
            region_text_parts.append(f"{region_name} ({len(depts)}) : {dept_str}")
        text_lines.append("📍 Périmètre : " + " | ".join(region_text_parts))
    if category_labels:
        text_lines.append(f"🏷️ Catégories : {' · '.join(category_labels)}")
    text_lines.append("")

    # --- Version HTML ---
    html_rows: list[str] = []

    # Ligne départements
    if all_france:
        html_rows.append(
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">'
            f'<span style="font-size:15px;line-height:1;">🌍</span>'
            f'<span style="font-size:13px;color:{theme["text_subtle"]};font-weight:600;">'
            f'France entière</span>'
            f'<span style="font-size:11px;color:{theme["text_muted"]};">'
            f'— tous les départements sont surveillés</span>'
            f'</div>'
        )
    else:
        details_parts: list[str] = []
        for region_name in sorted_regions:
            depts = region_groups[region_name]
            count = len(depts)
            dept_pills_html = "".join(
                f'<span style="display:inline-block;margin:2px 4px 2px 0;padding:2px 8px;'
                f'background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;'
                f'border-radius:10px;font-size:10px;font-weight:500;">'
                f'{escape(code)}&thinsp;<span style="font-weight:400;">{escape(name)}</span></span>'
                for code, name in depts
            )
            details_parts.append(
                f'<details style="display:inline-block;margin:2px 5px 4px 0;vertical-align:top;">'
                f'<summary style="'
                f'cursor:pointer;list-style:none;-webkit-appearance:none;'
                f'display:inline-flex;align-items:center;gap:5px;'
                f'padding:3px 8px 3px 10px;'
                f'background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;'
                f'border-radius:12px;font-size:11px;font-weight:500;'
                f'user-select:none;outline:none;'
                f'">'
                f'{escape(region_name)}'
                f'<span style="background:#1d4ed8;color:#fff;border-radius:10px;'
                f'padding:1px 6px;font-size:10px;font-weight:700;line-height:1.4;">'
                f'{count}</span>'
                f'</summary>'
                f'<div style="margin-top:5px;padding:8px 10px;background:#f0f7ff;'
                f'border:1px solid #dbeafe;border-radius:6px;line-height:2;">'
                f'{dept_pills_html}'
                f'</div>'
                f'</details>'
            )
        html_rows.append(
            f'<div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:6px;">'
            f'<span style="font-size:11px;text-transform:uppercase;letter-spacing:0.07em;'
            f'color:{theme["text_muted"]};white-space:nowrap;padding-top:5px;min-width:84px;">'
            f'📍 Périmètre</span>'
            f'<div style="flex:1;">{"".join(details_parts)}</div>'
            f'</div>'
        )

    # Ligne catégories
    if category_labels:
        cat_pills = "".join(
            f'<span style="display:inline-block;margin:2px 4px 2px 0;padding:2px 9px;'
            f'background:#f5f3ff;color:#5b21b6;border:1px solid #c4b5fd;'
            f'border-radius:12px;font-size:11px;font-weight:500;">{escape(cat)}</span>'
            for cat in category_labels
        )
        html_rows.append(
            f'<div style="display:flex;align-items:flex-start;gap:10px;">'
            f'<span style="font-size:11px;text-transform:uppercase;letter-spacing:0.07em;'
            f'color:{theme["text_muted"]};white-space:nowrap;padding-top:3px;min-width:84px;">'
            f'🏷️ Catégories</span>'
            f'<div style="flex:1;line-height:2;">{cat_pills}</div>'
            f'</div>'
        )

    html_block = (
        f'<div style="margin-bottom:20px;padding:12px 14px;background:#f9fafb;'
        f'border-radius:8px;border:1px solid #e5e7eb;">'
        f'<div style="font-size:11px;text-transform:uppercase;letter-spacing:0.08em;'
        f'color:{theme["text_muted"]};font-weight:600;margin-bottom:8px;">'
        f'🔍 Périmètre surveillé</div>'
        + "".join(html_rows)
        + '</div>'
    )
    return text_lines, html_block


def render_client_email(
    formatter: EstablishmentFormatter,
    establishments: Sequence[models.Establishment],
    *,
    client: models.Client,
    filters: ClientFilterSummary | None = None,
    previous_month_day_establishments: Sequence[models.Establishment] | None = None,
    previous_month_day_date: date | None = None,
    outside_google_count: int | None = None,
    outside_no_google_count: int | None = None,
    no_google_establishments: Sequence[models.Establishment] | None = None,
) -> tuple[str, str]:
    match_count = len(establishments)
    no_google_count = len(no_google_establishments or [])
    total_count = match_count + no_google_count

    selected_statuses = list(filters.listing_statuses) if filters and filters.listing_statuses else list(STATUS_SECTION_ORDER)
    section_statuses = [status for status in STATUS_SECTION_ORDER if status in selected_statuses]
    if not section_statuses:
        section_statuses = list(STATUS_SECTION_ORDER)
    multi_status_selection = len(section_statuses) > 1

    lines: list[str] = ["Bonjour,", ""]
    theme = CLIENT_EMAIL_THEME
    html_parts: list[str] = [
        "<html>",
        "<head><meta charset=\"UTF-8\"></head>",
        (
            "<body "
            f"style=\"font-family:'Helvetica Neue',Arial,sans-serif;color:{theme['text']};"
            f"line-height:1.55;background:{theme['page_bg']};margin:0;padding:20px;\">"
        ),
        (
            "<div "
            f"style=\"max-width:700px;margin:0 auto;background:{theme['card_bg']};"
            f"border-radius:12px;box-shadow:{theme['card_shadow']};padding:28px;\">"
        ),
        "<div style=\"display:flex;align-items:center;gap:10px;margin-bottom:18px;\">",
        f"<h2 style=\"margin:0;color:{theme['brand']};font-size:22px;font-weight:800;letter-spacing:-0.01em;\">📊 Business tracker</h2>",
        "</div>",
        f"<p style=\"margin:0 0 14px;font-size:14px;color:{theme['text']};\">Bonjour,</p>",
    ]

    # Note: filtres NAF/statuts affichés dans le bloc périmètre ci-dessous.

    ordered_establishments = _order_establishments_by_status(establishments, ordered_statuses=section_statuses)
    ordered_no_google = list(no_google_establishments or [])

    def _build_item_blocks(
        establishment: models.Establishment,
        *,
        context_label: str | None = None,
        is_no_google_card: bool = False,
    ) -> tuple[list[str], str]:
        name = establishment.name or "(nom indisponible)"
        full_address = formatter.format_full_address(establishment)
        client_categories, client_subcategories = formatter.resolve_client_category_labels(
            client,
            establishment.naf_code,
        )
        category_name = ", ".join(client_categories) if client_categories else None
        subcategory_name = ", ".join(client_subcategories) if client_subcategories else None
        if not category_name and not subcategory_name:
            category_name, subcategory_name = formatter.resolve_category_and_subcategory(establishment.naf_code)
        if not category_name:
            category_name = establishment.naf_libelle
        use_subcategory = getattr(client, "use_subcategory_label_in_client_alerts", False)
        naf_code_label = establishment.naf_code or ""
        if use_subcategory:
            label = subcategory_name or category_name
            if label:
                category_name = f"{label} ({naf_code_label})" if naf_code_label else label
        normalized_status = normalize_listing_age_status(establishment.google_listing_age_status)
        if is_no_google_card:
            item_bg = NO_GOOGLE_CARD_COLOR["bg"]
            border_color = NO_GOOGLE_CARD_COLOR["border"]
        elif context_label:
            item_bg = "#eef2f7"
            border_color = "#94a3b8"
        else:
            border_color = STATUS_COLORS.get(normalized_status, STATUS_COLORS["unknown"])["border"]
            item_bg = theme["item_bg"]
        google_url = establishment.google_place_url

        # --- Dirigeants (personnes physiques uniquement) ---
        directors = getattr(establishment, "directors", None) or []
        physical_directors = [d for d in directors if getattr(d, "is_physical_person", False)]

        # ── Lignes texte ──────────────────────────────────
        prefix = f"[{context_label}] " if context_label else ""
        item_lines = [f"- {prefix}{name}"]
        if full_address:
            item_lines.append(f"  {full_address}")
        if category_name:
            item_lines.append(f"  Catégorie : {category_name}")
        if getattr(establishment, "is_sole_proprietorship", False):
            item_lines.append("  Type : Entreprise individuelle")
        for director in physical_directors:
            first_names = (getattr(director, "first_names", None) or "").strip()
            last_name = (getattr(director, "last_name", None) or "").strip()
            quality = (getattr(director, "quality", None) or "Dirigeant").strip()
            # Texte : prénom(s) en casse normale, NOM en majuscules
            if first_names and last_name:
                director_name_text = f"{first_names} {last_name.upper()}"
            elif last_name:
                director_name_text = last_name.upper()
            elif first_names:
                director_name_text = first_names
            else:
                director_name_text = quality
            birth_month = getattr(director, "birth_month", None)
            birth_year = getattr(director, "birth_year", None)
            birth_info = ""
            if birth_month and birth_year:
                month_label = MONTH_LABELS_FR.get(birth_month, str(birth_month))
                birth_info = f" — né(e) en {month_label} {birth_year}"
            elif birth_year:
                birth_info = f" — né(e) en {birth_year}"
            item_lines.append(f"  👤 {director_name_text} ({quality}){birth_info}")
        if establishment.date_creation:
            item_lines.append(
                f"  Création administrative : {_format_month_year_fr(establishment.date_creation)}"
            )
        else:
            item_lines.append("  Création administrative : N/A")
        if is_no_google_card:
            item_lines.append("  Statut : Modification administrative récente")
        else:
            if google_url:
                item_lines.append(f"  Fiche Google : {google_url}")
            else:
                item_lines.append("  Fiche Google : en cours de disponibilité")
            if multi_status_selection:
                status_label, _ = formatter.describe_listing_age(establishment)
                client_label = CLIENT_STATUS_LABELS.get(normalized_status, status_label)
                item_lines.append(f"  Statut fiche Google : {client_label}")

        # ── HTML ──────────────────────────────────────────
        item_html_parts: list[str] = []
        if context_label:
            item_html_parts.append(
                f"<div style=\"font-size:11px;text-transform:uppercase;letter-spacing:0.08em;"
                f"color:{theme['text_muted']};margin-bottom:6px;\">{escape(context_label)}</div>"
            )
        item_html_parts.append(
            f"<strong style=\"font-size:15px;color:{theme['text']};\">{escape(name)}</strong>"
        )
        if full_address:
            item_html_parts.append(
                f"<div style=\"margin-top:4px;color:{theme['text_muted']};font-size:13px;\">📍 {escape(full_address)}</div>"
            )
        if category_name:
            item_html_parts.append(
                f"<div style=\"margin-top:8px;font-size:13px;\"><span style=\"color:{theme['text_muted']};\">🏢 Catégorie :</span> {escape(category_name)}</div>"
            )
        if getattr(establishment, "is_sole_proprietorship", False):
            item_html_parts.append(
                f"<div style=\"margin-top:6px;\">"
                f"<span style=\"display:inline-block;padding:2px 8px;border-radius:5px;"
                f"background:#ede9fe;color:#5b21b6;border:1px solid #a78bfa;"
                f"font-size:11px;font-weight:600;\">✦ Entreprise individuelle</span>"
                f"</div>"
            )
        if physical_directors:
            item_html_parts.append(
                f"<div style=\"margin-top:10px;padding-top:8px;border-top:1px dashed {theme['border']};\">"
                f"<div style=\"font-size:11px;text-transform:uppercase;letter-spacing:0.08em;"
                f"color:{theme['text_muted']};margin-bottom:4px;\">👥 Dirigeant(s)</div>"
            )
            for director in physical_directors:
                first_names = (getattr(director, "first_names", None) or "").strip()
                last_name = (getattr(director, "last_name", None) or "").strip()
                quality = (getattr(director, "quality", None) or "Dirigeant").strip()
                # HTML : prénom(s) en poids normal, NOM en gras majuscules
                if first_names and last_name:
                    name_html = (
                        f"{escape(first_names)} "
                        f"<strong style=\"letter-spacing:0.02em;\">{escape(last_name.upper())}</strong>"
                    )
                    director_name = f"{first_names} {last_name.upper()}"  # pour quality_display check
                elif last_name:
                    name_html = f"<strong style=\"letter-spacing:0.02em;\">{escape(last_name.upper())}</strong>"
                    director_name = last_name.upper()
                elif first_names:
                    name_html = escape(first_names)
                    director_name = first_names
                else:
                    name_html = escape(quality)
                    director_name = quality
                birth_month = getattr(director, "birth_month", None)
                birth_year = getattr(director, "birth_year", None)
                birth_info = ""
                if birth_month and birth_year:
                    month_label = MONTH_LABELS_FR.get(birth_month, str(birth_month))
                    birth_info = f" — né(e) en {month_label} {birth_year}"
                elif birth_year:
                    birth_info = f" — né(e) en {birth_year}"
                quality_display = f" ({escape(quality)})" if quality and quality != director_name else ""
                birth_display = escape(birth_info) if birth_info else ""
                item_html_parts.append(
                    f"<div style=\"font-size:12px;color:{theme['text_subtle']};margin-top:3px;\">"
                    f"{name_html}"
                    f"<span style=\"color:{theme['text_muted']};\">{quality_display}{birth_display}</span>"
                    f"</div>"
                )
            item_html_parts.append("</div>")
        creation_label = (
            _format_month_year_fr(establishment.date_creation)
            if establishment.date_creation
            else "N/A"
        )
        item_html_parts.append(
            f"<div style=\"margin-top:8px;font-size:13px;\"><span style=\"color:{theme['text_muted']};\">📅 Création :</span> {escape(creation_label)}</div>"
        )
        if is_no_google_card:
            badge_html = (
                f'<span style="display:inline-block;padding:3px 10px;border-radius:10px;'
                f'background:{NO_GOOGLE_CARD_COLOR["bg"]};color:{NO_GOOGLE_CARD_COLOR["text"]};'
                f'border:1px solid {NO_GOOGLE_CARD_COLOR["border"]};'
                f'font-size:12px;font-weight:500;">📋 Modification administrative récente</span>'
            )
            item_html_parts.append(f"<div style=\"margin-top:10px;\">Statut : {badge_html}</div>")
        else:
            if google_url:
                link = escape(google_url)
                item_html_parts.append(
                    (
                        f"<div style=\"margin-top:10px;\">"
                        f"<a href=\"{link}\" style=\"display:inline-block;padding:6px 12px;"
                        f"background:{theme['brand']};color:#ffffff;text-decoration:none;border-radius:6px;"
                        f"font-weight:600;font-size:12px;\">🗺️ Voir la fiche Google</a>"
                        f"</div>"
                    )
                )
            else:
                item_html_parts.append(
                    f"<div style=\"margin-top:12px;color:{theme['link_muted']};font-style:italic;font-size:12px;\">Lien Google indisponible pour le moment</div>"
                )
            if multi_status_selection:
                status_label, _ = formatter.describe_listing_age(establishment)
                client_label = CLIENT_STATUS_LABELS.get(normalized_status, status_label)
                badge = _get_status_badge_html(normalized_status, client_label)
                item_html_parts.append(f"<div style=\"margin-top:10px;\">Statut : {badge}</div>")

        # Add LinkedIn buttons for directors with profiles
        linkedin_text_lines, linkedin_html = _build_linkedin_buttons_html(establishment, theme)
        if linkedin_text_lines:
            item_lines.extend(linkedin_text_lines)
        if linkedin_html:
            item_html_parts.append(linkedin_html)

        item_html = (
            f"<li style=\"margin-bottom:20px;padding:14px;background:{item_bg};border-radius:8px;"
            f"border-left:4px solid {border_color};\">"
            + "".join(item_html_parts)
            + "</li>"
        )
        return item_lines, item_html

    def _append_establishments(
        items: Sequence[models.Establishment],
        *,
        show_empty_placeholder: bool,
        context_label: str | None = None,
        is_no_google_card: bool = False,
    ) -> None:
        if items:
            html_parts.append("<ul style=\"list-style:none;padding:0;margin:0;\">")
            for establishment in items:
                item_lines, item_html = _build_item_blocks(
                    establishment,
                    context_label=context_label,
                    is_no_google_card=is_no_google_card,
                )
                lines.extend(item_lines)
                lines.append("")
                html_parts.append(item_html)
            html_parts.append("</ul>")
        if items:
            lines.append("")

    # --- Bloc périmètre surveillé (départements + catégories) ---
    scope_text_lines, scope_html = _build_client_scope_summary(client, theme)
    if scope_text_lines:
        lines.extend(scope_text_lines)
    if scope_html:
        html_parts.append(scope_html)

    if total_count > 0:
        # Résumé introductif avec chiffres en gras et emojis
        etab_pl = "s" if total_count > 1 else ""
        etab_new = "nouveaux" if total_count > 1 else "nouvel"
        etab_word = f"établissement{etab_pl}"
        verb = "ont" if total_count > 1 else "a"
        intro_line = (
            f"🎯 {total_count} {etab_new} {etab_word} {verb} été identifié{etab_pl} "
            f"dans votre périmètre aujourd'hui."
        )
        lines.append(intro_line)
        if match_count > 0 and no_google_count > 0:
            fiche_pl = "s" if match_count > 1 else ""
            no_g_pl = "s" if no_google_count > 1 else ""
            lines.append(f"  • 🗺️ {match_count} fiche{fiche_pl} Google My Business")
            lines.append(f"  • 📋 {no_google_count} établissement{no_g_pl} sans fiche Google")
        outside_total = (outside_google_count or 0) + (outside_no_google_count or 0)
        if outside_total > 0:
            out_text_parts: list[str] = []
            if outside_google_count:
                fiche_out_pl = "s" if outside_google_count > 1 else ""
                out_text_parts.append(f"🗺️ {outside_google_count} fiche{fiche_out_pl} Google")
            if outside_no_google_count:
                no_g_out_pl = "s" if outside_no_google_count > 1 else ""
                out_text_parts.append(f"📋 {outside_no_google_count} sans fiche Google")
            lines.append(f"  🌍 Hors périmètre — territoire entier : {' · '.join(out_text_parts)}")
        lines.append("")

        # Bloc HTML d'intro
        count_html = f"<strong style=\"color:{theme['brand']};font-size:20px;\">{total_count}</strong>"
        intro_suffix = (
            f" {etab_new} {etab_word} {verb} été identifié{etab_pl} dans votre périmètre aujourd'hui."
        )
        if match_count > 0 and no_google_count > 0:
            fiche_pl = "s" if match_count > 1 else ""
            no_g_pl = "s" if no_google_count > 1 else ""
            detail_html = (
                f"<ul style=\"margin:8px 0 0;padding-left:18px;font-size:13px;color:{theme['text_subtle']};\">"
                f"<li>🗺️ <strong>{match_count}</strong> fiche{fiche_pl} Google My Business</li>"
                f"<li>📋 <strong>{no_google_count}</strong> établissement{no_g_pl} sans fiche Google</li>"
                f"</ul>"
            )
        elif match_count > 0:
            fiche_pl = "s" if match_count > 1 else ""
            detail_html = (
                f"<p style=\"margin:6px 0 0;font-size:13px;color:{theme['text_subtle']};\">"
                f"🗺️ <strong>{match_count}</strong> fiche{fiche_pl} Google My Business identifiée{fiche_pl}</p>"
            )
        else:
            no_g_pl = "s" if no_google_count > 1 else ""
            detail_html = (
                f"<p style=\"margin:6px 0 0;font-size:13px;color:{theme['text_subtle']};\">"
                f"📋 <strong>{no_google_count}</strong> établissement{no_g_pl} sans fiche Google détecté{no_g_pl}</p>"
            )
        _outside_total = (outside_google_count or 0) + (outside_no_google_count or 0)
        _outside_card_html = ""
        if _outside_total > 0:
            _out_html_parts: list[str] = []
            if outside_google_count:
                _fiche_out_pl = "s" if outside_google_count > 1 else ""
                _out_html_parts.append(
                    f"🗺️&nbsp;<strong>{outside_google_count}</strong>&nbsp;fiche{_fiche_out_pl} Google My Business"
                )
            if outside_no_google_count:
                _no_g_out_pl = "s" if outside_no_google_count > 1 else ""
                _out_html_parts.append(
                    f"📋&nbsp;<strong>{outside_no_google_count}</strong>&nbsp;établissement{_no_g_out_pl} sans fiche Google"
                )
            _out_items_html = "&nbsp;&nbsp;·&nbsp;&nbsp;".join(_out_html_parts)
            _outside_card_html = (
                f"<div style=\"margin-top:12px;padding-top:10px;border-top:1px dashed #cbd5e1;\">"
                f"<div style=\"font-size:12px;color:#64748b;font-weight:600;margin-bottom:3px;\">🌍 Sur l'ensemble du territoire français ce jour :</div>"
                f"<div style=\"font-size:12px;color:#475569;\">{_out_items_html}</div>"
                f"</div>"
            )
        html_parts.append(
            f"<div style=\"margin:0 0 20px;padding:16px;background:#f0f9ff;"
            f"border-radius:10px;border-left:4px solid {theme['brand']};\">"
            f"<p style=\"margin:0;font-size:15px;color:{theme['text']};\">"
            f"🎯 {count_html}{escape(intro_suffix)}"
            f"</p>"
            f"{detail_html}"
            f"{_outside_card_html}"
            f"</div>"
        )
        # En-tête de section Google
        if match_count > 0:
            fiche_pl = "s" if match_count > 1 else ""
            det_pl = "s" if match_count > 1 else ""
            section_title = (
                f"🗺️ {match_count} fiche{fiche_pl} Google My Business "
                f"identifiée{det_pl}"
            )
            lines.append(section_title)
            lines.append("")
            html_parts.append(
                f"<h3 style=\"margin:0 0 12px;font-size:15px;color:{theme['text']};font-weight:700;\">"
                f"{escape(section_title)}"
                f"</h3>"
            )
    else:
        lines.extend([
            "Aucun nouvel établissement n'a été détecté aujourd'hui dans votre périmètre.",
            "",
        ])
        html_parts.append(
            f"<p style=\"margin:0 0 16px;color:{theme['text_subtle']};\">Aucun nouvel établissement n'a été détecté aujourd'hui dans votre périmètre.</p>"
        )

    _append_establishments(ordered_establishments, show_empty_placeholder=False)

    # Section pour les établissements sans fiche Google
    if no_google_count > 0:
        no_g_pl = "s" if no_google_count > 1 else ""
        no_g_new = "nouveaux" if no_google_count > 1 else "nouvel"
        no_g_word = f"établissement{no_g_pl}"
        no_google_section_title = (
            f"📋 {no_google_count} {no_g_new} {no_g_word} — Modification administrative récente"
        )
        lines.append("")
        lines.append(no_google_section_title)
        lines.append("")
        html_parts.append(
            f"<div style=\"margin-top:28px;margin-bottom:14px;padding-bottom:10px;"
            f"border-bottom:2px solid {theme['border']};\">"
            f"<h3 style=\"margin:0 0 4px;font-size:15px;color:{theme['text']};font-weight:700;\">"
            f"📋 <strong>{no_google_count}</strong> {no_g_new} {no_g_word}"
            f"</h3>"
            f"<p style=\"margin:0;font-size:12px;color:{theme['text_muted']};\">Fiche Google non identifiée à ce jour · "
            f"Modification administrative récente</p>"
            f"</div>"
        )
        _append_establishments(ordered_no_google, show_empty_placeholder=False, is_no_google_card=True)

    if total_count == 0:
        lines.append("Nous vous notifierons dès qu'un nouvel établissement correspondra à ces critères.")
        lines.append("")

    if total_count == 0:
        html_parts.append(
            f"<p style=\"margin-top:24px;color:{theme['text_subtle']};\">Nous vous notifierons dès qu'un nouvel établissement correspondra à ces critères.</p>"
        )

    if previous_month_day_date is not None:
        previous_label = _format_date_fr(previous_month_day_date)
        lines.append("\n".join([
            "—" * 52,
            f"Pour rappel, voici les alertes qui ont été générées le {previous_label} :",
            "—" * 52,
            "",
        ]).strip("\n"))
        html_parts.append(
            f"<div style=\"margin:28px 0 16px;padding:14px 16px;border:1px dashed {theme['border']};"
            f"border-radius:10px;background:{theme['item_bg']};\">"
            f"<p style=\"margin:0 0 6px;font-size:12px;color:{theme['text_muted']};text-transform:uppercase;letter-spacing:0.08em;\">"
            "Rappel mensuel"
            "</p>"
            f"<h3 style=\"margin:0;font-size:15px;color:{theme['text']};\">"
            f"Alertes générées le {escape(previous_label)}"
            "</h3>"
            "</div>"
        )
        previous_items = list(previous_month_day_establishments or [])
        if previous_items:
            ordered_previous_items = _order_establishments_by_status(
                previous_items,
                ordered_statuses=section_statuses,
            )
            _append_establishments(
                ordered_previous_items,
                show_empty_placeholder=False,
                context_label="Rappel mensuel",
            )
        else:
            lines.append("Aucune alerte n'a été générée ce jour-là.")
            lines.append("")
            html_parts.append(
                f"<p style=\"margin:0 0 16px;color:{theme['text_muted']};\">"
                "Aucune alerte n'a été générée ce jour-là.</p>"
            )

    lines.extend(["Cordialement,", "L'équipe Business tracker"])

    html_parts.extend([
        f"<div style=\"margin-top:32px;padding-top:18px;border-top:1px solid {theme['border']};color:{theme['text_muted']};font-size:13px;\">",
        "<p style=\"margin:0;\">Cordialement,</p>",
        f"<p style=\"margin:4px 0 0;font-weight:700;color:{theme['brand']};\">L'équipe Business tracker</p>",
        "</div>",
        "</div>",
        "</body>",
        "</html>",
    ])

    text_body = "\n".join(lines).strip()
    html_body = "\n".join(html_parts)
    return text_body, html_body


def render_admin_email(
    formatter: EstablishmentFormatter,
    establishments: Sequence[models.Establishment],
) -> tuple[str, str]:
    has_google_establishments = any(
        (getattr(establishment, "google_check_status", "") or "").lower() == "found"
        for establishment in establishments
    )
    has_linkedin_only_establishments = any(
        (getattr(establishment, "google_check_status", "") or "").lower() != "found"
        and any(
            getattr(director, "is_physical_person", False)
            and getattr(director, "linkedin_profile_url", None)
            for director in (getattr(establishment, "directors", None) or [])
        )
        for establishment in establishments
    )

    if has_google_establishments and has_linkedin_only_establishments:
        intro = "Résumé détaillé des fiches Google et profils LinkedIn détectés :"
    elif has_linkedin_only_establishments and not has_google_establishments:
        intro = "Résumé détaillé des profils LinkedIn détectés :"
    else:
        intro = "Résumé détaillé des fiches Google détectées :"

    lines: list[str] = [
        "Bonjour,",
        "",
        intro,
        "",
    ]

    html_parts: list[str] = [
        "<html>",
        "<body style=\"font-family:'Helvetica Neue',Arial,sans-serif;color:#111827;line-height:1.5;\">",
        "<p>Bonjour,</p>",
        f"<p>{escape(intro)}</p>",
        "<table style=\"width:100%;border-collapse:collapse;margin-top:8px;\">",
        "<thead>",
        "<tr>",
        "<th style=\"text-align:left;padding:12px;border-bottom:1px solid #e5e7eb;\">Établissement</th>",
        "<th style=\"text-align:left;padding:12px;border-bottom:1px solid #e5e7eb;\">Identifiants</th>",
        "<th style=\"text-align:left;padding:12px;border-bottom:1px solid #e5e7eb;\">Google</th>",
        "</tr>",
        "</thead>",
        "<tbody>",
    ]

    for establishment in establishments:
        lines.extend(formatter.format_lines(establishment, include_google=True))
        linkedin_text_lines, linkedin_html = _build_linkedin_buttons_html(establishment, CLIENT_EMAIL_THEME)
        if linkedin_text_lines:
            lines.extend(linkedin_text_lines)
        lines.append("")

        name = establishment.name or "(nom indisponible)"
        street_line, commune_line = formatter.format_address_lines(establishment)
        siret_display, siret_url = formatter.get_siret_display_and_url(establishment.siret)
        naf_code = establishment.naf_code or "N/A"
        naf_label = establishment.naf_libelle or ""
        creation_date = (
            _format_month_year_fr(establishment.date_creation)
            if establishment.date_creation
            else "N/A"
        )
        google_url = establishment.google_place_url
        google_id = establishment.google_place_id or ""
        subcategory_label = formatter.format_subcategory_label(establishment.naf_code)

        address_section = [f"<strong>{escape(name)}</strong>"]
        if street_line:
            address_section.append(f"<div>{escape(street_line)}</div>")
        if commune_line:
            address_section.append(f"<div>{escape(commune_line)}</div>")

        if siret_url:
            ident_section = [
                f"SIRET&nbsp;: <a href=\"{escape(siret_url)}\" style=\"color:#2563eb;text-decoration:none;\">{escape(siret_display)}</a>"
            ]
        else:
            ident_section = [f"SIRET&nbsp;: {escape(siret_display)}"]
        ident_section.append(f"NAF&nbsp;: {escape(naf_code)}")
        if naf_label:
            ident_section.append(escape(naf_label))
        if subcategory_label:
            ident_section.append(f"Catégorie&nbsp;: {escape(subcategory_label)}")
        ident_section.append(f"Création administrative&nbsp;: {escape(creation_date)}")

        google_section: list[str] = []
        if google_url:
            link = escape(google_url)
            google_section.append(
                f"<a href=\"{link}\" style=\"color:#2563eb;text-decoration:none;\">Ouvrir la fiche</a>"
            )
        else:
            google_section.append("Lien indisponible")
        if google_id:
            google_section.append(f"ID&nbsp;: {escape(google_id)}")
        status_label, _ = formatter.describe_listing_age(establishment)
        status_line = f"Statut&nbsp;: {escape(status_label)}"
        google_section.append(status_line)
        if linkedin_html:
            google_section.append(linkedin_html)

        html_parts.append(
            "<tr>"
            + "<td style=\"vertical-align:top;padding:12px;border-bottom:1px solid #f3f4f6;\">"
            + "".join(address_section)
            + "</td>"
            + "<td style=\"vertical-align:top;padding:12px;border-bottom:1px solid #f3f4f6;\">"
            + "<br/>".join(ident_section)
            + "</td>"
            + "<td style=\"vertical-align:top;padding:12px;border-bottom:1px solid #f3f4f6;\">"
            + "<br/>".join(google_section)
            + "</td>"
            + "</tr>"
        )

    lines.extend([
        "Bien à vous,",
        "L'équipe Business tracker",
    ])

    html_parts.extend([
        "</tbody>",
        "</table>",
        "<p style=\"margin-top:24px;\">Bien à vous,<br/>L'équipe Business tracker</p>",
        "</body>",
        "</html>",
    ])

    text_body = "\n".join(lines).strip()
    html_body = "\n".join(html_parts)
    return text_body, html_body
