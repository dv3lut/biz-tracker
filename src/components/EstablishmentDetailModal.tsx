import { useEffect } from "react";

import { EstablishmentDetail } from "../types";
import { formatDateTime } from "../utils/format";
import { SiretLink } from "./SiretLink";

type Props = {
  isOpen: boolean;
  establishment: EstablishmentDetail | null;
  isLoading: boolean;
  errorMessage: string | null;
  onClose: () => void;
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

export const EstablishmentDetailModal = ({
  isOpen,
  establishment,
  isLoading,
  errorMessage,
  onClose,
}: Props) => {
  useEffect(() => {
    if (!isOpen) {
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

  if (!isOpen) {
    return null;
  }

  const googleStatus = establishment ? establishment.googleCheckStatus : null;
  const placeUrl = establishment?.googlePlaceUrl ?? null;
  const googlePlaceId = establishment?.googlePlaceId ?? null;
  const lastChecked = establishment ? formatDateTime(establishment.googleLastCheckedAt) : "—";
  const lastFound = establishment ? formatDateTime(establishment.googleLastFoundAt) : "—";

  return (
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
                      </tr>
                    </thead>
                    <tbody>
                      {establishment.directors.map((d) => (
                        <tr key={d.id}>
                          <td>{d.typeDirigeant === "personne physique" ? "Physique" : "Morale"}</td>
                          <td>
                            {d.typeDirigeant === "personne physique"
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
                        </tr>
                      ))}
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
  );
};
