from __future__ import annotations

from html import escape
from typing import Final, Sequence

from app.db import models
from app.services.client_service import ClientFilterSummary
from app.utils.google_listing import LISTING_AGE_STATUS_LABELS, normalize_listing_age_status

from .formatter import EstablishmentFormatter


STATUS_SECTION_ORDER: Final[tuple[str, ...]] = (
    "recent_creation",
    "recent_creation_missing_contact",
    "not_recent_creation",
)

STATUS_TITLE_OVERRIDES: Final[dict[str, str]] = {
    "recent_creation_missing_contact": "Création récente sans contact",
}


def _section_title_for_status(status: str) -> str:
    if status in STATUS_TITLE_OVERRIDES:
        return STATUS_TITLE_OVERRIDES[status]
    return LISTING_AGE_STATUS_LABELS.get(status, status)


def _format_listing_status_labels(statuses: list[str]) -> list[str]:
    return [LISTING_AGE_STATUS_LABELS.get(status, status) for status in statuses]


def render_client_email(
    formatter: EstablishmentFormatter,
    establishments: Sequence[models.Establishment],
    *,
    filters: ClientFilterSummary | None = None,
) -> tuple[str, str]:
    match_count = len(establishments)
    selected_statuses = list(filters.listing_statuses) if filters and filters.listing_statuses else list(STATUS_SECTION_ORDER)
    section_statuses = [status for status in STATUS_SECTION_ORDER if status in selected_statuses]
    if not section_statuses:
        section_statuses = list(STATUS_SECTION_ORDER)
    multi_status_selection = len(section_statuses) > 1

    lines: list[str] = ["Bonjour,", ""]
    html_parts: list[str] = [
        "<html>",
        "<body style=\"font-family:'Helvetica Neue',Arial,sans-serif;color:#111827;line-height:1.5;\">",
        "<p>Bonjour,</p>",
    ]

    summary_lines: list[str] = []
    summary_html: list[str] = []
    if filters:
        if filters.listing_statuses:
            labels = ", ".join(_format_listing_status_labels(filters.listing_statuses))
            summary_lines.append(f"Statuts Google surveillés : {labels}")
            summary_html.append(
                f"<p style=\"margin:0;\"><strong>Statuts Google surveillés :</strong> {escape(labels)}</p>"
            )
        if filters.naf_codes:
            naf_codes = ", ".join(filters.naf_codes)
            summary_lines.append(f"Codes NAF ciblés : {naf_codes}")
            summary_html.append(
                f"<p style=\"margin:4px 0 0;\"><strong>Codes NAF ciblés :</strong> {escape(naf_codes)}</p>"
            )

    grouped_by_status: dict[str, list[models.Establishment]] = {status: [] for status in section_statuses}
    fallback_bucket: list[models.Establishment] = []
    for establishment in establishments:
        normalized_status = normalize_listing_age_status(establishment.google_listing_age_status)
        if normalized_status in grouped_by_status:
            grouped_by_status[normalized_status].append(establishment)
        else:
            fallback_bucket.append(establishment)
    if fallback_bucket and section_statuses:
        grouped_by_status.setdefault(section_statuses[0], []).extend(fallback_bucket)

    def _build_item_blocks(establishment: models.Establishment) -> tuple[list[str], str]:
        name = establishment.name or "(nom indisponible)"
        full_address = formatter.format_full_address(establishment)
        category_name, subcategory_name = formatter.resolve_category_and_subcategory(establishment.naf_code)
        if not category_name:
            category_name = establishment.naf_libelle
        google_url = establishment.google_place_url

        item_lines = [f"- {name}"]
        if full_address:
            item_lines.append(f"  {full_address}")
        if category_name:
            item_lines.append(f"  Catégorie : {category_name}")
        if subcategory_name:
            item_lines.append(f"  Sous-catégorie : {subcategory_name}")
        if google_url:
            item_lines.append(f"  Fiche Google : {google_url}")
        else:
            item_lines.append("  Fiche Google : en cours de disponibilité")
        if multi_status_selection:
            status_label, _ = formatter.describe_listing_age(establishment)
            item_lines.append(f"  Statut fiche Google : {status_label}")

        item_html_parts = [f"<strong>{escape(name)}</strong>"]
        if full_address:
            item_html_parts.append(f"<div>{escape(full_address)}</div>")
        if category_name:
            item_html_parts.append(f"<div>Catégorie : {escape(category_name)}</div>")
        if subcategory_name:
            item_html_parts.append(f"<div>Sous-catégorie : {escape(subcategory_name)}</div>")
        if google_url:
            link = escape(google_url)
            item_html_parts.append(
                f"<div><a href=\"{link}\" style=\"color:#2563eb;text-decoration:none;\">Voir la fiche Google</a></div>"
            )
        else:
            item_html_parts.append(
                "<div style=\"color:#6b7280;\">Lien Google indisponible pour le moment</div>"
            )
        if multi_status_selection:
            status_label, _ = formatter.describe_listing_age(establishment)
            item_html_parts.append(f"<div>Statut fiche Google : {escape(status_label)}</div>")
        item_html = "<li style=\"margin-bottom:16px;\">" + "".join(item_html_parts) + "</li>"
        return item_lines, item_html

    def _append_establishments(
        items: Sequence[models.Establishment],
        *,
        show_empty_placeholder: bool,
    ) -> None:
        if items:
            html_parts.append("<ul style=\"padding-left:18px;margin:0;\">")
            for establishment in items:
                item_lines, item_html = _build_item_blocks(establishment)
                lines.extend(item_lines)
                lines.append("")
                html_parts.append(item_html)
            html_parts.append("</ul>")
        elif show_empty_placeholder:
            lines.append("  0 nouvel établissement détecté.")
            html_parts.append(
                "<p style=\"color:#6b7280;margin:4px 0 16px;\">0 nouvel établissement détecté.</p>"
            )
        if items or show_empty_placeholder:
            lines.append("")

    if match_count:
        lines.append("Nous avons identifié de nouvelles fiches Google My Business pour vos établissements :")
        lines.append("")
        html_parts.append(
            "<p>Nous avons identifié de nouvelles fiches Google My Business pour vos établissements :</p>"
        )
    else:
        lines.extend([
            "Aucun nouvel établissement n'a été détecté aujourd'hui dans votre périmètre.",
            "Synthèse : 0 nouvel établissement détecté.",
            "",
        ])
        html_parts.append(
            "<p>Aucun nouvel établissement n'a été détecté aujourd'hui dans votre périmètre.</p>"
        )
        html_parts.append(
            "<p style=\"color:#6b7280;\">Synthèse : 0 nouvel établissement détecté.</p>"
        )

    if summary_lines:
        lines.extend(summary_lines)
        lines.append("")
    if not match_count:
        lines.append("Nous vous notifierons dès qu'un nouvel établissement correspondra à ces critères.")
        lines.append("")

    if multi_status_selection:
        for status in section_statuses:
            section_title = _section_title_for_status(status)
            section_establishments = grouped_by_status.get(status, [])
            lines.append(section_title)
            html_parts.append(
                f"<h3 style=\"font-size:18px;margin:24px 0 8px;\">{escape(section_title)}</h3>"
            )
            _append_establishments(section_establishments, show_empty_placeholder=True)
    else:
        combined_establishments: list[models.Establishment] = []
        for status in section_statuses:
            combined_establishments.extend(grouped_by_status.get(status, []))
        _append_establishments(combined_establishments, show_empty_placeholder=False)

    if summary_html:
        html_parts.append(
            "<div style=\"margin-top:16px;padding:12px;background:#f3f4f6;border-radius:8px;\">"
            + "".join(summary_html)
            + "</div>"
        )
    if not match_count:
        html_parts.append(
            "<p style=\"margin-top:16px;\">Nous vous notifierons dès qu'un nouvel établissement correspondra à ces critères.</p>"
        )

    lines.extend(["Cordialement,", "L'équipe Business tracker"])

    html_parts.extend([
        "<p style=\"margin-top:24px;\">Cordialement,<br/>L'équipe Business tracker</p>",
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
        creation_date = establishment.date_creation.isoformat() if establishment.date_creation else "N/A"
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
        ident_section.append(f"Création&nbsp;: {escape(creation_date)}")

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
