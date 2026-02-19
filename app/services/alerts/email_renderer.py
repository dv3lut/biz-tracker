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
    if director.linkedin_profile_data:
        title = director.linkedin_profile_data.get("title")
        if title and isinstance(title, str) and title.strip():
            return title.strip()
    if director.quality and director.quality.strip():
        return director.quality.strip()
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


def render_client_email(
    formatter: EstablishmentFormatter,
    establishments: Sequence[models.Establishment],
    *,
    client: models.Client,
    filters: ClientFilterSummary | None = None,
    previous_month_day_establishments: Sequence[models.Establishment] | None = None,
    previous_month_day_date: date | None = None,
    outside_departments_alert_count: int | None = None,
) -> tuple[str, str]:
    match_count = len(establishments)
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
        f"<h2 style=\"margin:0;color:{theme['text']};font-size:20px;font-weight:800;letter-spacing:-0.01em;\">Business tracker</h2>",
        "</div>",
        f"<p style=\"margin:0 0 14px;font-size:14px;color:{theme['text']};\">Bonjour,</p>",
    ]

    # Note: on n'affiche pas les filtres surveillés (NAF/statuts) dans le mail client.

    ordered_establishments = _order_establishments_by_status(establishments, ordered_statuses=section_statuses)

    def _build_item_blocks(
        establishment: models.Establishment,
        *,
        context_label: str | None = None,
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
        border_color = STATUS_COLORS.get(normalized_status, STATUS_COLORS["unknown"])["border"]
        item_bg = theme["item_bg"]
        if context_label:
            item_bg = "#eef2f7"
            border_color = "#94a3b8"
        google_url = establishment.google_place_url

        prefix = f"[{context_label}] " if context_label else ""
        item_lines = [f"- {prefix}{name}"]
        if full_address:
            item_lines.append(f"  {full_address}")
        if category_name:
            item_lines.append(f"  Catégorie : {category_name}")
        if establishment.date_creation:
            item_lines.append(
                f"  Création administrative : {_format_month_year_fr(establishment.date_creation)}"
            )
        else:
            item_lines.append("  Création administrative : N/A")
        if google_url:
            item_lines.append(f"  Fiche Google : {google_url}")
        else:
            item_lines.append("  Fiche Google : en cours de disponibilité")
        if multi_status_selection:
            status_label, _ = formatter.describe_listing_age(establishment)
            client_label = CLIENT_STATUS_LABELS.get(normalized_status, status_label)
            item_lines.append(f"  Statut fiche Google : {client_label}")

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
                f"<div style=\"margin-top:4px;color:{theme['text_muted']};font-size:13px;\">{escape(full_address)}</div>"
            )
        if category_name:
            item_html_parts.append(
                f"<div style=\"margin-top:8px;font-size:13px;\"><span style=\"color:{theme['text_muted']};\">Catégorie :</span> {escape(category_name)}</div>"
            )
        creation_label = (
            _format_month_year_fr(establishment.date_creation)
            if establishment.date_creation
            else "N/A"
        )
        item_html_parts.append(
            f"<div style=\"margin-top:8px;font-size:13px;\"><span style=\"color:{theme['text_muted']};\">Création administrative :</span> {escape(creation_label)}</div>"
        )
        if google_url:
            link = escape(google_url)
            item_html_parts.append(
                (
                    f"<div style=\"margin-top:10px;\">"
                    f"<a href=\"{link}\" style=\"display:inline-block;padding:6px 12px;"
                    f"background:{theme['brand']};color:#ffffff;text-decoration:none;border-radius:6px;"
                    f"font-weight:600;font-size:12px;\">Voir la fiche Google</a>"
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
    ) -> None:
        if items:
            html_parts.append("<ul style=\"list-style:none;padding:0;margin:0;\">")
            for establishment in items:
                item_lines, item_html = _build_item_blocks(establishment, context_label=context_label)
                lines.extend(item_lines)
                lines.append("")
                html_parts.append(item_html)
            html_parts.append("</ul>")
        if items:
            lines.append("")

    if match_count:
        # Check if we have any establishments with Google found
        has_google_establishments = any(
            (est.google_check_status or "").lower() == "found"
            for est in establishments
        )
        # Check if we have any establishments with LinkedIn-only (no Google)
        has_linkedin_only_establishments = any(
            (est.google_check_status or "").lower() != "found"
            and any(
                getattr(d, "is_physical_person", False) and getattr(d, "linkedin_profile_url", None)
                for d in (getattr(est, "directors", None) or [])
            )
            for est in establishments
        )
        
        if has_google_establishments and has_linkedin_only_establishments:
            title = "Nous avons identifié de nouvelles fiches Google My Business et profils LinkedIn :"
        elif has_linkedin_only_establishments:
            title = "Nous avons identifié de nouveaux profils LinkedIn :"
        else:
            title = "Nous avons identifié de nouvelles fiches Google My Business :"
        
        lines.append(title)
        lines.append("")
        html_parts.append(
            f"<p style=\"margin:0 0 18px;color:{theme['text_subtle']};font-size:14px;\">{escape(title)}</p>"
        )
    else:
        lines.extend([
            "Aucun nouvel établissement n'a été détecté aujourd'hui dans votre périmètre.",
            "Synthèse : 0 nouvel établissement détecté.",
            "",
        ])
        html_parts.append(
            f"<p style=\"margin:0 0 16px;color:{theme['text_subtle']};\">Aucun nouvel établissement n'a été détecté aujourd'hui dans votre périmètre.</p>"
        )
        html_parts.append(
            f"<p style=\"margin:0 0 16px;color:{theme['text_muted']};\">Synthèse : 0 nouvel établissement détecté.</p>"
        )

    if outside_departments_alert_count and outside_departments_alert_count > 0:
        plural = "s" if outside_departments_alert_count > 1 else ""
        lines.append(
            "En dehors de vos départements sélectionnés, nous avons également émis "
            f"{outside_departments_alert_count} alerte{plural} aujourd'hui sur le territoire français."
        )
        lines.append("")
        html_parts.append(
            f"<p style=\"margin:0 0 16px;color:{theme['text_muted']};\">"
            f"En dehors de vos départements sélectionnés, nous avons également émis "
            f"{outside_departments_alert_count} alerte{plural} aujourd'hui sur le territoire français."
            "</p>"
        )

    if not match_count:
        lines.append("Nous vous notifierons dès qu'un nouvel établissement correspondra à ces critères.")
        lines.append("")

    _append_establishments(ordered_establishments, show_empty_placeholder=False)

    if not match_count:
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
    lines: list[str] = [
        "Bonjour,",
        "",
        "Résumé détaillé des fiches Google détectées :",
        "",
    ]

    html_parts: list[str] = [
        "<html>",
        "<body style=\"font-family:'Helvetica Neue',Arial,sans-serif;color:#111827;line-height:1.5;\">",
        "<p>Bonjour,</p>",
        "<p>Résumé détaillé des fiches Google détectées :</p>",
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
