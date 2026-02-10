import { useEffect, useState } from "react";

import { linkedInApi } from "../api";
import { Director, EstablishmentDetail, LinkedInCheckResponse, LinkedInDebugResponse } from "../types";
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

export const EstablishmentDetailModal = ({
  isOpen,
  establishment,
  isLoading,
  errorMessage,
  onClose,
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

  useEffect(() => {
    if (!isOpen) {
      setLinkedInLoadingIds(new Set());
      setLinkedInErrors({});
      setLinkedInDebugLoadingIds(new Set());
      setLinkedInDebugErrors({});
      setLinkedInCheckModal(null);
      setLinkedInDebugModal(null);
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

  if (!isOpen) {
    return null;
  }

  const googleStatus = establishment ? establishment.googleCheckStatus : null;
  const placeUrl = establishment?.googlePlaceUrl ?? null;
  const googlePlaceId = establishment?.googlePlaceId ?? null;
  const lastChecked = establishment ? formatDateTime(establishment.googleLastCheckedAt) : "—";
  const lastFound = establishment ? formatDateTime(establishment.googleLastFoundAt) : "—";

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
              <h3>Identité</h3>
              <dl className="data-grid">
                <dt>SIRET</dt>
                <dd>
                  <SiretLink value={establishment.siret} />
                </dd>
                <dt>SIREN</dt>
                <dd>{establishment.siren}</dd>
                <dt>NIC</dt>
                <dd>{formatValue(establishment.nic)}</dd>
                <dt>Nom</dt>
                <dd>{formatValue(establishment.name)}</dd>
                <dt>Enseigne</dt>
                <dd>{formatValue(establishment.enseigne1 || establishment.enseigne2 || establishment.enseigne3)}</dd>
                <dt>NAF</dt>
                <dd>
                  {formatValue(establishment.nafCode)}
                  {establishment.nafLibelle ? ` (${establishment.nafLibelle})` : ""}
                </dd>
                <dt>Catégorie juridique</dt>
                <dd>{formatValue(establishment.categorieJuridique)}</dd>
                <dt>Catégorie entreprise</dt>
                <dd>{formatValue(establishment.categorieEntreprise)}</dd>
                <dt>Entreprise individuelle</dt>
                <dd>{establishment.isSoleProprietorship ? "Oui" : "Non"}</dd>
                <dt>Tranche effectifs</dt>
                <dd>{formatValue(establishment.trancheEffectifs)}</dd>
                <dt>Année effectifs</dt>
                <dd>{formatValue(establishment.anneeEffectifs)}</dd>
                <dt>Unité légale</dt>
                <dd>{formatValue(establishment.legalUnitName)}</dd>
              </dl>
            </section>

            {establishment.directors.length > 0 && (
              <section>
                <h3>Dirigeants ({establishment.directors.length})</h3>
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
              </section>
            )}

            <section>
              <h3>Localisation</h3>
              <dl className="data-grid">
                <dt>Adresse</dt>
                <dd>
                  <span className="preformatted">{buildAddress(establishment)}</span>
                </dd>
                <dt>Distribution spéciale</dt>
                <dd>{formatValue(establishment.distributionSpeciale)}</dd>
                <dt>Code commune</dt>
                <dd>{formatValue(establishment.codeCommune)}</dd>
                <dt>Code cedex</dt>
                <dd>{formatValue(establishment.codeCedex)}</dd>
                <dt>Pays</dt>
                <dd>{formatValue(establishment.libellePays)}</dd>
              </dl>
            </section>

            <section>
              <h3>Synchronisation</h3>
              <dl className="data-grid">
                <dt>Date création</dt>
                <dd>{formatValue(establishment.dateCreation)}</dd>
                <dt>Date début activité</dt>
                <dd>{formatValue(establishment.dateDebutActivite)}</dd>
                <dt>Première vue</dt>
                <dd>{formatDateTime(establishment.firstSeenAt)}</dd>
                <dt>Dernière vue</dt>
                <dd>{formatDateTime(establishment.lastSeenAt)}</dd>
                <dt>Run d'origine</dt>
                <dd>{formatValue(establishment.createdRunId)}</dd>
                <dt>Dernier run</dt>
                <dd>{formatValue(establishment.lastRunId)}</dd>
                <dt>Dernier traitement établissement</dt>
                <dd>{formatDateTime(establishment.dateDernierTraitementEtablissement)}</dd>
                <dt>Dernier traitement unité légale</dt>
                <dd>{formatDateTime(establishment.dateDernierTraitementUniteLegale)}</dd>
              </dl>
            </section>

            <section>
              <h3>Informations Google</h3>
              <dl className="data-grid">
                <dt>Statut</dt>
                <dd>{formatValue(googleStatus)}</dd>
                <dt>Dernier contrôle</dt>
                <dd>{lastChecked}</dd>
                <dt>Dernière détection</dt>
                <dd>{lastFound}</dd>
                <dt>Place ID</dt>
                <dd>{formatValue(googlePlaceId)}</dd>
                <dt>URL Google</dt>
                <dd>
                  {placeUrl ? (
                    <a href={placeUrl} target="_blank" rel="noreferrer">
                      Ouvrir la fiche Google
                    </a>
                  ) : (
                    "—"
                  )}
                </dd>
              </dl>
            </section>

            <section>
              <h3>Données brutes</h3>
              <pre className="payload">{JSON.stringify(establishment, null, 2)}</pre>
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
