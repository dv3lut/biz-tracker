from __future__ import annotations

from html import escape
from typing import Sequence

from app.db import models

from .formatter import EstablishmentFormatter


def render_client_email(
    formatter: EstablishmentFormatter,
    establishments: Sequence[models.Establishment],
) -> tuple[str, str]:
    lines: list[str] = [
        "Bonjour,",
        "",
        "Nous avons identifié de nouvelles fiches Google My Business pour vos établissements :",
        "",
    ]

    html_parts: list[str] = [
        "<html>",
        "<body style=\"font-family:'Helvetica Neue',Arial,sans-serif;color:#111827;line-height:1.5;\">",
        "<p>Bonjour,</p>",
        "<p>Nous avons identifié de nouvelles fiches Google My Business pour vos établissements :</p>",
        "<ul style=\"padding-left:18px;margin:0;\">",
    ]

    for establishment in establishments:
        name = establishment.name or "(nom indisponible)"
        street_line, commune_line = formatter.format_address_lines(establishment)
        google_url = establishment.google_place_url
        subcategory_label = formatter.format_subcategory_label(establishment.naf_code)

        lines.append(f"- {name}")
        if street_line:
            lines.append(f"  {street_line}")
        if commune_line:
            lines.append(f"  {commune_line}")
        if subcategory_label:
            lines.append(f"  Catégorie : {subcategory_label}")
        if google_url:
            lines.append(f"  Fiche Google : {google_url}")
        else:
            lines.append("  Fiche Google : en cours de disponibilité")
        status_label, origin = formatter.describe_listing_age(establishment)
        if google_url:
            if origin:
                lines.append(f"  Statut fiche Google : {status_label} (origine {origin})")
            else:
                lines.append(f"  Statut fiche Google : {status_label}")
        lines.append("")

        item_html = [
            f"<strong>{escape(name)}</strong>",
        ]
        if street_line:
            item_html.append(f"<div>{escape(street_line)}</div>")
        if commune_line:
            item_html.append(f"<div>{escape(commune_line)}</div>")
        if subcategory_label:
            item_html.append(
                f"<div style=\"color:#93c5fd;\">Sous-catégorie : {escape(subcategory_label)}</div>"
            )
        if google_url:
            link = escape(google_url)
            item_html.append(
                f"<div><a href=\"{link}\" style=\"color:#2563eb;text-decoration:none;\">Voir la fiche Google</a></div>"
            )
        else:
            item_html.append(
                "<div style=\"color:#6b7280;\">Lien Google indisponible pour le moment</div>"
            )
        status_label, origin = formatter.describe_listing_age(establishment)
        status_parts = [f"Statut fiche Google : {escape(status_label)}"]
        if origin:
            status_parts.append(f"<span style=\"color:#9ca3af;\">(origine {escape(origin)})</span>")
        item_html.append(f"<div>{' '.join(status_parts)}</div>")
        html_parts.append(
            "<li style=\"margin-bottom:16px;\">" + "".join(item_html) + "</li>"
        )

    lines.extend([
        "Cordialement,",
        "L'équipe Biz Tracker",
    ])

    html_parts.extend([
        "</ul>",
        "<p style=\"margin-top:24px;\">Cordialement,<br/>L'équipe Biz Tracker</p>",
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
        status_label, origin = formatter.describe_listing_age(establishment)
        status_line = f"Statut&nbsp;: {escape(status_label)}"
        if origin:
            status_line += f" (origine {escape(origin)})"
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
        "L'équipe Biz Tracker",
    ])

    html_parts.extend([
        "</tbody>",
        "</table>",
        "<p style=\"margin-top:24px;\">Bien à vous,<br/>L'équipe Biz Tracker</p>",
        "</body>",
        "</html>",
    ])

    text_body = "\n".join(lines).strip()
    html_body = "\n".join(html_parts)
    return text_body, html_body
