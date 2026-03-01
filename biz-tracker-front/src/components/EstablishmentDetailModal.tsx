import { ReactNode, useEffect, useState } from "react";

import { googleApi, linkedInApi } from "../api";
import {
  Director,
  EstablishmentDetail,
  LinkedInCheckResponse,
  LinkedInDebugResponse,
  ScrapedContact,
  WebsiteScrapeStatus,
} from "../types";
import { formatDateTime } from "../utils/format";
import { buildLinkedInSearchQuery, openLinkedInSearchForDirector } from "../utils/linkedinSearch";
import { SiretLink } from "./SiretLink";
import { LinkedInCheckModal } from "./LinkedInCheckModal";
import { LinkedInDebugModal } from "./LinkedInDebugModal";

type Props = {
  isOpen: boolean;
  establishment: EstablishmentDetail | null;
  isLoading: boolean;
  errorMessage: string | null;
  onClose: () => void;
  onRefreshEstablishment?: (siret: string) => Promise<void> | void;
  onDirectorLinkedInUpdated?: (directorId: string, update: Partial<Director>) => void;
};

const formatValue = (value: string | number | null | undefined): string => {
  if (value === null || value === undefined) {
    return "—";
  }
  if (typeof value === "number") {
    return String(value);
  }
  const trimmed = value.trim();
  return trimmed.length === 0 ? "—" : trimmed;
};

const buildAddress = (establishment: EstablishmentDetail | null): string => {
  if (!establishment) {
    return "—";
  }
  const lines: string[] = [];
  const voieParts = [
    establishment.numeroVoie,
    establishment.indiceRepetition,
    establishment.typeVoie,
    establishment.libelleVoie,
  ].filter((item): item is string => Boolean(item && item.trim()));
  if (establishment.complementAdresse) {
    lines.push(establishment.complementAdresse);
  }
  if (voieParts.length > 0) {
    lines.push(voieParts.join(" "));
  }
  const communeParts = [
    establishment.codePostal,
    establishment.libelleCommune,
  ].filter((item): item is string => Boolean(item && item.trim()));
  if (communeParts.length > 0) {
    lines.push(communeParts.join(" "));
  }
  const foreignParts = [
    establishment.libelleCommuneEtranger,
    establishment.libellePays,
  ].filter((item): item is string => Boolean(item && item.trim()));
  if (foreignParts.length > 0) {
    lines.push(foreignParts.join(" "));
  }
  if (lines.length === 0) {
    return "—";
  }
  return lines.join("\n");
};

const getLinkedInErrorMessage = (data: Record<string, unknown> | null | undefined): string | null => {
  if (!data) {
    return null;
  }
  const candidate = data.message || data.error || data.statusMessage || data.errorMessage;
  return typeof candidate === "string" && candidate.trim().length > 0 ? candidate : null;
};

const computeWebsiteScrapeStatus = (establishment: EstablishmentDetail | null): WebsiteScrapeStatus => {
  const website = establishment?.googleContactWebsite?.trim();
  if (!website) {
    return "no_website";
  }
  if (!establishment?.websiteScrapedAt) {
    return "pending";
  }
  const hasContacts = (establishment.scrapedContacts ?? []).length > 0;
  const hasLegacyInfo = [
    establishment.websiteScrapedMobilePhones,
    establishment.websiteScrapedNationalPhones,
    establishment.websiteScrapedEmails,
    establishment.websiteScrapedFacebook,
    establishment.websiteScrapedInstagram,
    establishment.websiteScrapedTwitter,
    establishment.websiteScrapedLinkedin,
  ].some((value) => Boolean(value && value.trim()));
  return hasContacts || hasLegacyInfo ? "found" : "no_info";
};

const websiteScrapeStatusLabel = (status: WebsiteScrapeStatus): string => {
  switch (status) {
    case "pending":
      return "En attente";
    case "found":
      return "Infos trouvées";
    case "no_info":
      return "Aucune info";
    case "no_website":
      return "Sans site web";
    default:
      return status;
  }
};

export const EstablishmentDetailModal = ({
  isOpen,
  establishment,
  isLoading,
  errorMessage,
  onClose,
  onRefreshEstablishment,
  onDirectorLinkedInUpdated,
}: Props) => {
  const [linkedInLoadingIds, setLinkedInLoadingIds] = useState<Set<string>>(new Set());
  const [linkedInErrors, setLinkedInErrors] = useState<Record<string, string>>({});
  const [linkedInDebugLoadingIds, setLinkedInDebugLoadingIds] = useState<Set<string>>(new Set());
  const [linkedInDebugErrors, setLinkedInDebugErrors] = useState<Record<string, string>>({});
  const [linkedInCheckModal, setLinkedInCheckModal] = useState<
    { director: Director; result: LinkedInCheckResponse } | null
  >(null);
  const [linkedInDebugModal, setLinkedInDebugModal] = useState<
    { director: Director; result: LinkedInDebugResponse } | null
  >(null);
  const [isScrapingWebsite, setIsScrapingWebsite] = useState(false);
  const [websiteScrapeMessage, setWebsiteScrapeMessage] = useState<string | null>(null);
  const [websiteScrapeError, setWebsiteScrapeError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) {
      setLinkedInLoadingIds(new Set());
      setLinkedInErrors({});
      setLinkedInDebugLoadingIds(new Set());
      setLinkedInDebugErrors({});
      setLinkedInCheckModal(null);
      setLinkedInDebugModal(null);
      setIsScrapingWebsite(false);
      setWebsiteScrapeMessage(null);
      setWebsiteScrapeError(null);
      return;
    }
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handler);
    return () => {
      window.removeEventListener("keydown", handler);
    };
  }, [isOpen, onClose]);

  const handleLinkedInSearch = async (director: Director) => {
    const directorId = director.id;
    setLinkedInLoadingIds((prev) => new Set(prev).add(directorId));
    setLinkedInErrors((prev) => {
      const next = { ...prev };
      delete next[directorId];
      return next;
    });

    try {
      const result = await linkedInApi.checkDirectorLinkedIn(directorId);
      if (onDirectorLinkedInUpdated) {
        onDirectorLinkedInUpdated(directorId, {
          linkedinProfileUrl: result.linkedinProfileUrl,
          linkedinProfileData: result.linkedinProfileData,
          linkedinCheckStatus: result.linkedinCheckStatus,
          linkedinLastCheckedAt: result.linkedinLastCheckedAt,
        });
      }
      setLinkedInCheckModal({ director, result });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Erreur inconnue";
      setLinkedInErrors((prev) => ({ ...prev, [directorId]: message }));
    } finally {
      setLinkedInLoadingIds((prev) => {
        const next = new Set(prev);
        next.delete(directorId);
        return next;
      });
    }
  };

  const handleLinkedInDebug = async (director: Director) => {
    const directorId = director.id;
    setLinkedInDebugLoadingIds((prev) => new Set(prev).add(directorId));
    setLinkedInDebugErrors((prev) => {
      const next = { ...prev };
      delete next[directorId];
      return next;
    });

    try {
      const result = await linkedInApi.debugDirectorLinkedIn(directorId);
      setLinkedInDebugModal({ director, result });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Erreur inconnue";
      setLinkedInDebugErrors((prev) => ({ ...prev, [directorId]: message }));
    } finally {
      setLinkedInDebugLoadingIds((prev) => {
        const next = new Set(prev);
        next.delete(directorId);
        return next;
      });
    }
  };

  const handleManualWebsiteScrape = async () => {
    if (!establishment) {
      return;
    }
    setIsScrapingWebsite(true);
    setWebsiteScrapeError(null);
    setWebsiteScrapeMessage(null);

    try {
      const result = await googleApi.scrapeWebsite(establishment.siret);
      setWebsiteScrapeMessage(result.message || "Scraping du site relancé.");
      if (onRefreshEstablishment) {
        await onRefreshEstablishment(establishment.siret);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Erreur inconnue";
      setWebsiteScrapeError(message);
    } finally {
      setIsScrapingWebsite(false);
    }
  };

  if (!isOpen) {
    return null;
  }

  const googleStatus = establishment ? establishment.googleCheckStatus : null;
  const placeUrl = establishment?.googlePlaceUrl ?? null;
  const googlePlaceId = establishment?.googlePlaceId ?? null;
  const lastChecked = establishment ? formatDateTime(establishment.googleLastCheckedAt) : "—";
  const lastFound = establishment ? formatDateTime(establishment.googleLastFoundAt) : "—";
  const websiteScrapeStatus = computeWebsiteScrapeStatus(establishment);
  const detailRows: Array<{ label: string; value: ReactNode }> = establishment
    ? [
        { label: "SIRET", value: <SiretLink value={establishment.siret} /> },
        { label: "SIREN", value: formatValue(establishment.siren) },
        { label: "NIC", value: formatValue(establishment.nic) },
        { label: "Nom", value: formatValue(establishment.name) },
        {
          label: "Enseigne",
          value: formatValue(establishment.enseigne1 || establishment.enseigne2 || establishment.enseigne3),
        },
        {
          label: "NAF",
          value: `${formatValue(establishment.nafCode)}${establishment.nafLibelle ? ` (${establishment.nafLibelle})` : ""}`,
        },
        { label: "Catégorie juridique", value: formatValue(establishment.categorieJuridique) },
        { label: "Catégorie entreprise", value: formatValue(establishment.categorieEntreprise) },
        { label: "Entreprise individuelle", value: establishment.isSoleProprietorship ? "Oui" : "Non" },
        { label: "Tranche effectifs", value: formatValue(establishment.trancheEffectifs) },
        { label: "Année effectifs", value: formatValue(establishment.anneeEffectifs) },
        { label: "Unité légale", value: formatValue(establishment.legalUnitName) },
        { label: "Adresse", value: <span className="preformatted">{buildAddress(establishment)}</span> },
        { label: "Distribution spéciale", value: formatValue(establishment.distributionSpeciale) },
        { label: "Code commune", value: formatValue(establishment.codeCommune) },
        { label: "Code cedex", value: formatValue(establishment.codeCedex) },
        { label: "Pays", value: formatValue(establishment.libellePays) },
        { label: "Date création", value: formatValue(establishment.dateCreation) },
        { label: "Date début activité", value: formatValue(establishment.dateDebutActivite) },
        { label: "Première vue", value: formatDateTime(establishment.firstSeenAt) },
        { label: "Dernière vue", value: formatDateTime(establishment.lastSeenAt) },
        { label: "Run d'origine", value: formatValue(establishment.createdRunId) },
        { label: "Dernier run", value: formatValue(establishment.lastRunId) },
        {
          label: "Dernier traitement établissement",
          value: formatDateTime(establishment.dateDernierTraitementEtablissement),
        },
        {
          label: "Dernier traitement unité légale",
          value: formatDateTime(establishment.dateDernierTraitementUniteLegale),
        },
        { label: "Statut Google", value: formatValue(googleStatus) },
        { label: "Dernier contrôle Google", value: lastChecked },
        { label: "Dernière détection Google", value: lastFound },
        { label: "Place ID", value: formatValue(googlePlaceId) },
        {
          label: "URL Google",
          value: placeUrl ? (
            <a href={placeUrl} target="_blank" rel="noreferrer">
              Ouvrir la fiche Google
            </a>
          ) : (
            "—"
          ),
        },
      ]
    : [];

  return (
    <>
      <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
        <div className="modal" onClick={(event) => event.stopPropagation()}>
        <header className="modal-header">
          <div>
            <h2>Fiche établissement</h2>
            {establishment ? (
              <p className="muted small">
                SIRET <SiretLink value={establishment.siret} className="muted small" />
              </p>
            ) : (
              <p className="muted small">Chargement en cours…</p>
            )}
          </div>
          <button type="button" className="ghost" onClick={onClose}>
            Fermer
          </button>
        </header>

        {isLoading && <p>Chargement de la fiche…</p>}
        {errorMessage && !isLoading && <p className="feedback error">{errorMessage}</p>}

        {!isLoading && !errorMessage && establishment && (
          <div className="modal-content">
            <section>
              <h3>Actions dirigeants (LinkedIn)</h3>
              {establishment.directors.length === 0 ? (
                <p className="muted">Aucun dirigeant rattaché.</p>
              ) : (
                <div className="table-wrapper">
                  <table>
                    <thead>
                      <tr>
                        <th>Type</th>
                        <th>Nom</th>
                        <th>Qualité</th>
                        <th>Naissance</th>
                        <th>LinkedIn</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {establishment.directors.map((d) => {
                        const isPhysical = d.typeDirigeant === "personne physique";
                        const isLinkedInLoading = linkedInLoadingIds.has(d.id);
                        const linkedInError = linkedInErrors[d.id];
                        const isLinkedInDebugLoading = linkedInDebugLoadingIds.has(d.id);
                        const linkedInDebugError = linkedInDebugErrors[d.id];
                        const linkedInSearchQuery = buildLinkedInSearchQuery(establishment, d);
                        const linkedInStatusMessage =
                          isPhysical && d.linkedinCheckStatus === "error"
                            ? getLinkedInErrorMessage(d.linkedinProfileData)
                            : null;
                        return (
                          <tr key={d.id}>
                            <td>{isPhysical ? "Physique" : "Morale"}</td>
                            <td>
                              {isPhysical
                                ? [d.firstNames, d.lastName].filter(Boolean).join(" ") || "—"
                                : d.denomination || "—"}
                            </td>
                            <td>{formatValue(d.quality)}</td>
                            <td>
                              {d.birthMonth && d.birthYear
                                ? `${String(d.birthMonth).padStart(2, "0")}/${d.birthYear}`
                                : d.birthYear
                                  ? String(d.birthYear)
                                  : "—"}
                            </td>
                            <td>
                              {isPhysical ? (
                                d.linkedinProfileUrl ? (
                                  <a href={d.linkedinProfileUrl} target="_blank" rel="noreferrer" className="badge badge--success">
                                    Profil trouvé
                                  </a>
                                ) : d.linkedinCheckStatus === "not_found" ? (
                                  <span className="badge badge--muted">Non trouvé</span>
                                ) : d.linkedinCheckStatus === "error" ? (
                                  <span className="badge badge--error">Erreur</span>
                                ) : d.linkedinCheckStatus === "insufficient" ? (
                                  <span className="badge badge--warning">Données insuffisantes</span>
                                ) : d.linkedinCheckStatus === "skipped_nd" ? (
                                  <span className="badge badge--muted">Non diffusible</span>
                                ) : (
                                  <span className="badge badge--pending">En attente</span>
                                )
                              ) : (
                                <span className="muted">—</span>
                              )}
                              {isPhysical ? (
                                <div className="muted small" style={{ marginTop: 6 }}>
                                  Dernier check : {formatDateTime(d.linkedinLastCheckedAt)}
                                  <br />
                                  Statut : {d.linkedinCheckStatus}
                                  {linkedInStatusMessage ? (
                                    <>
                                      <br />
                                      Détail : {linkedInStatusMessage}
                                    </>
                                  ) : null}
                                </div>
                              ) : null}
                            </td>
                            <td>
                              {isPhysical && (
                                <>
                                  <button
                                    type="button"
                                    className="small"
                                    onClick={() => handleLinkedInSearch(d)}
                                    disabled={isLinkedInLoading}
                                  >
                                    {isLinkedInLoading ? "Recherche…" : "Rechecker LinkedIn"}
                                  </button>
                                  <button
                                    type="button"
                                    className="small ghost"
                                    onClick={() => openLinkedInSearchForDirector(establishment, d)}
                                    disabled={!linkedInSearchQuery}
                                  >
                                    Recherche LinkedIn
                                  </button>
                                  <button
                                    type="button"
                                    className="small ghost"
                                    onClick={() => handleLinkedInDebug(d)}
                                    disabled={isLinkedInDebugLoading}
                                  >
                                    {isLinkedInDebugLoading ? "Debug…" : "Debug LinkedIn"}
                                  </button>
                                  {linkedInError && (
                                    <span className="feedback error small">{linkedInError}</span>
                                  )}
                                  {linkedInDebugError && (
                                    <span className="feedback error small">{linkedInDebugError}</span>
                                  )}
                                </>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section>
              <h3>Scraping du site web</h3>
              <dl className="data-grid">
                <dt>Site web</dt>
                <dd>
                  {establishment.googleContactWebsite ? (
                    <a href={establishment.googleContactWebsite} target="_blank" rel="noreferrer">
                      {establishment.googleContactWebsite}
                    </a>
                  ) : (
                    "—"
                  )}
                </dd>
                <dt>Statut scraping</dt>
                <dd>{websiteScrapeStatusLabel(websiteScrapeStatus)}</dd>
                <dt>Dernier scraping</dt>
                <dd>{formatDateTime(establishment.websiteScrapedAt)}</dd>
              </dl>

              {(() => {
                const contacts = establishment.scrapedContacts ?? [];
                const mobilePhones = contacts.filter((c: ScrapedContact) => c.contactType === "mobile_phone");
                const nationalPhones = contacts.filter((c: ScrapedContact) => c.contactType === "national_phone");
                const emails = contacts.filter((c: ScrapedContact) => c.contactType === "email");
                const hasContacts = mobilePhones.length > 0 || nationalPhones.length > 0 || emails.length > 0;
                const hasSocials = Boolean(
                  establishment.websiteScrapedFacebook ||
                  establishment.websiteScrapedInstagram ||
                  establishment.websiteScrapedTwitter ||
                  establishment.websiteScrapedLinkedin
                );

                if (!hasContacts && !hasSocials) {
                  return establishment.websiteScrapedAt ? (
                    <p className="muted" style={{ marginTop: 8 }}>Aucune information de contact trouvée.</p>
                  ) : null;
                }

                return (
                  <div style={{ marginTop: 12 }}>
                    {mobilePhones.length > 0 && (
                      <>
                        <h4 style={{ margin: "8px 0 4px" }}>Téléphones mobiles</h4>
                        <div className="table-wrapper">
                          <table className="data-table">
                            <thead><tr><th>Numéro</th><th>Libellé</th></tr></thead>
                            <tbody>
                              {mobilePhones.map((c: ScrapedContact) => (
                                <tr key={c.id}>
                                  <td><a href={`tel:${c.value}`}>{c.value}</a></td>
                                  <td>{c.label || "—"}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </>
                    )}
                    {nationalPhones.length > 0 && (
                      <>
                        <h4 style={{ margin: "8px 0 4px" }}>Téléphones fixes</h4>
                        <div className="table-wrapper">
                          <table className="data-table">
                            <thead><tr><th>Numéro</th><th>Libellé</th></tr></thead>
                            <tbody>
                              {nationalPhones.map((c: ScrapedContact) => (
                                <tr key={c.id}>
                                  <td><a href={`tel:${c.value}`}>{c.value}</a></td>
                                  <td>{c.label || "—"}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </>
                    )}
                    {emails.length > 0 && (
                      <>
                        <h4 style={{ margin: "8px 0 4px" }}>Emails</h4>
                        <div className="table-wrapper">
                          <table className="data-table">
                            <thead><tr><th>Email</th><th>Libellé</th></tr></thead>
                            <tbody>
                              {emails.map((c: ScrapedContact) => (
                                <tr key={c.id}>
                                  <td><a href={`mailto:${c.value}`}>{c.value}</a></td>
                                  <td>{c.label || "—"}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </>
                    )}
                    {hasSocials && (
                      <dl className="data-grid" style={{ marginTop: 8 }}>
                        {establishment.websiteScrapedFacebook && (
                          <><dt>Facebook</dt><dd><a href={establishment.websiteScrapedFacebook} target="_blank" rel="noreferrer">{establishment.websiteScrapedFacebook}</a></dd></>
                        )}
                        {establishment.websiteScrapedInstagram && (
                          <><dt>Instagram</dt><dd><a href={establishment.websiteScrapedInstagram} target="_blank" rel="noreferrer">{establishment.websiteScrapedInstagram}</a></dd></>
                        )}
                        {establishment.websiteScrapedTwitter && (
                          <><dt>Twitter/X</dt><dd><a href={establishment.websiteScrapedTwitter} target="_blank" rel="noreferrer">{establishment.websiteScrapedTwitter}</a></dd></>
                        )}
                        {establishment.websiteScrapedLinkedin && (
                          <><dt>LinkedIn</dt><dd><a href={establishment.websiteScrapedLinkedin} target="_blank" rel="noreferrer">{establishment.websiteScrapedLinkedin}</a></dd></>
                        )}
                      </dl>
                    )}
                  </div>
                );
              })()}
              <div style={{ marginTop: 12 }}>
                <button type="button" className="small" onClick={handleManualWebsiteScrape} disabled={isScrapingWebsite}>
                  {isScrapingWebsite ? "Scraping..." : "Re-scraper le site"}
                </button>
                {websiteScrapeMessage ? <p className="feedback success">{websiteScrapeMessage}</p> : null}
                {websiteScrapeError ? <p className="feedback error">{websiteScrapeError}</p> : null}
              </div>
            </section>

            <section>
              <h3>Détails établissement</h3>
              <div className="table-wrapper">
                <table className="data-table">
                  <tbody>
                    {detailRows.map((row) => (
                      <tr key={row.label}>
                        <th style={{ width: "35%", textAlign: "left" }}>{row.label}</th>
                        <td>{row.value}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        )}
        </div>
      </div>
      {linkedInCheckModal ? (
        <LinkedInCheckModal
          directorName={
            linkedInCheckModal.director.typeDirigeant === "personne physique"
              ? [linkedInCheckModal.director.firstNames, linkedInCheckModal.director.lastName]
                  .filter(Boolean)
                  .join(" ")
              : linkedInCheckModal.director.denomination || "—"
          }
          companyName={linkedInCheckModal.result.companyName}
          result={linkedInCheckModal.result}
          onClose={() => setLinkedInCheckModal(null)}
        />
      ) : null}
      {linkedInDebugModal ? (
        <LinkedInDebugModal
          directorName={
            linkedInDebugModal.director.typeDirigeant === "personne physique"
              ? [linkedInDebugModal.director.firstNames, linkedInDebugModal.director.lastName]
                  .filter(Boolean)
                  .join(" ")
              : linkedInDebugModal.director.denomination || "—"
          }
          result={linkedInDebugModal.result}
          onClose={() => setLinkedInDebugModal(null)}
        />
      ) : null}
    </>
  );
};
