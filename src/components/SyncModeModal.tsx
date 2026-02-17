import { KeyboardEvent, useEffect, useMemo, useState } from "react";

import { LISTING_STATUS_LABELS } from "../constants/listingStatuses";
import {
  Client,
  DayReplayReference,
  GoogleCheckStatus,
  LinkedInStatus,
  ListingStatus,
  NafCategoryStat,
  SyncMode,
} from "../types";
import {
  canonicalizeNafCode,
  denormalizeNafCode,
  describeSyncMode,
  formatNafCodesPreview,
  MAX_TARGET_NAF_CODES,
  normalizeNafCode,
  parseNafInput,
  syncModeIsGoogleOnly,
  syncModeRequiresReplayDate,
} from "../utils/sync";

const formatDateInput = (value: Date) => value.toISOString().slice(0, 10);

const MODE_OPTIONS: Array<{
  value: SyncMode;
  title: string;
  description: string;
  impact: string;
}> = [
  {
    value: "full",
    title: "Mode complet",
    description: "Télécharge les mises à jour Sirene puis déclenche les enrichissements Google Places et LinkedIn.",
    impact: "Plus long mais garantit des fiches Google et LinkedIn actualisées.",
  },
  {
    value: "sirene_only",
    title: "Mode Sirene uniquement",
    description: "Capture uniquement les évolutions Sirene. Les appels Google et LinkedIn sont ignorés.",
    impact: "Recommandé pour analyser rapidement une base ou en cas d'incident Google.",
  },
  {
    value: "google_refresh",
    title: "Google",
    description: "Ne touche pas à Sirene et relance Google sur les statuts sélectionnés.",
    impact: "Les données Google des établissements ciblés seront recalculées et écrasées.",
  },
  {
    value: "linkedin_refresh",
    title: "LinkedIn",
    description: "Relance la recherche LinkedIn sur les dirigeants physiques selon les statuts sélectionnés.",
    impact: "Ciblez précisément les statuts à rejouer (en attente, trouvés, non trouvés, en erreur).",
  },
  {
    value: "day_replay",
    title: "Rejouer une journée",
    description: "Relance la collecte Sirene + Google sur une date précise pour diagnostiquer ou compléter une journée.",
    impact: "Les alertes sont limitées aux administrateurs et n'impactent pas les curseurs.",
  },
  {
    value: "website_scrape",
    title: "Scraping site web",
    description: "Scrape les sites web des établissements ayant une fiche Google avec URL, selon les statuts sélectionnés.",
    impact: "Extrait téléphones, emails et réseaux sociaux depuis les sites web des établissements.",
  },
];

const DAY_REPLAY_REFERENCE_OPTIONS: Array<{
  value: DayReplayReference;
  title: string;
  description: string;
}> = [
  {
    value: "creation_date",
    title: "Basée sur la création Sirene",
    description: "Filtre tous les établissements dont la date de création Sirene correspond au jour ciblé.",
  },
  {
    value: "insertion_date",
    title: "Basée sur l'insertion Business tracker",
    description: "Utilise la date d'insertion dans Business tracker pour rejouer uniquement les alertes importées ce jour-là.",
  },
];

const DEFAULT_REPLAY_REFERENCE: DayReplayReference = "creation_date";

const MAX_TARGET_CLIENTS = 50;

const LINKEDIN_STATUS_OPTIONS: Array<{ value: LinkedInStatus; label: string }> = [
  { value: "pending", label: "En attente" },
  { value: "found", label: "Trouvé" },
  { value: "not_found", label: "Non trouvés" },
  { value: "error", label: "En erreur" },
  { value: "insufficient", label: "Identité insuffisante" },
];

const GOOGLE_STATUS_LABELS: Record<string, string> = {
  pending: "En attente",
  found: "Trouvé",
  not_found: "Non trouvés",
  insufficient: "Informations insuffisantes",
  type_mismatch: "Incohérent",
  non_diffusible: "Non diffusible",
};

const WEBSITE_STATUS_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "not_scraped", label: "Non scrapé" },
  { value: "scraped", label: "Déjà scrapé" },
];

const buildGoogleStatusOptions = (
  statuses: GoogleCheckStatus[],
): Array<{ value: GoogleCheckStatus; label: string }> =>
  statuses.map((status) => ({
    value: status,
    label: GOOGLE_STATUS_LABELS[status] ?? status.replace(/_/g, " "),
  }));

type ClientOption = {
  id: string;
  name: string;
  listingSummary: string;
  nafSummary: string;
  recipientCount: number;
  searchTokens: string;
};

const describeListingStatuses = (statuses?: ListingStatus[]): string => {
  if (!statuses || statuses.length === 0) {
    return "Tous les statuts Google";
  }
  const labels = statuses.map((status) => LISTING_STATUS_LABELS[status] ?? status);
  return labels.join(", ");
};

const extractClientNafCodes = (client: Client): string[] => {
  const subscriptions = client.subscriptions ?? [];
  return subscriptions
    .map((subscription) => subscription.subcategory?.nafCode)
    .filter((code): code is string => Boolean(code))
    .map((code) => canonicalizeNafCode(normalizeNafCode(code) ?? code) ?? code);
};

const describeNafSummary = (codes: string[]): string => {
  if (codes.length === 0) {
    return "Toutes catégories suivies";
  }
  const preview = codes.slice(0, 6).join(", ");
  return codes.length > 6 ? `${preview}…` : preview;
};

const buildClientOptions = (clients: Client[]): ClientOption[] => {
  return [...clients]
    .sort((a, b) => a.name.localeCompare(b.name, "fr", { sensitivity: "base" }))
    .map((client) => {
      const codes = extractClientNafCodes(client);
      const listingSummary = describeListingStatuses(client.listingStatuses);
      const nafSummary = describeNafSummary(codes);
      const tokens = `${client.name} ${listingSummary} ${codes.join(" ")}`.toLowerCase();
      return {
        id: client.id,
        name: client.name,
        listingSummary,
        nafSummary,
        recipientCount: client.recipients?.length ?? 0,
        searchTokens: tokens,
      };
    });
};

type NormalizedSubcategory = NafCategoryStat["subcategories"][number] & {
  normalizedNafCode: string;
  displayNafCode: string;
};

type NormalizedCategory = {
  categoryId: string;
  name: string;
  nafCodes: string[];
  subcategories: NormalizedSubcategory[];
};

type Props = {
  isOpen: boolean;
  initialMode: SyncMode;
  initialReplayDate?: string | null;
  initialNafCodes?: string[] | null;
  nafCategories: NafCategoryStat[];
  initialTargetClientIds?: string[] | null;
  initialNotifyAdmins?: boolean | null;
  initialForceGoogleReplay?: boolean | null;
  initialReplayReference?: DayReplayReference | null;
  initialGoogleStatuses?: GoogleCheckStatus[] | null;
  googleStatuses?: GoogleCheckStatus[];
  isGoogleStatusesLoading?: boolean;
  googleStatusesError?: string | null;
  clients: Client[];
  isClientsLoading?: boolean;
  clientsError?: string | null;
  onConfirm: (payload: {
    mode: SyncMode;
    replayForDate?: string;
    nafCodes?: string[];
    targetClientIds?: string[];
    notifyAdmins?: boolean;
    forceGoogleReplay?: boolean;
    replayReference?: DayReplayReference;
    monthsBack?: number;
    linkedinStatuses?: LinkedInStatus[];
    googleStatuses?: GoogleCheckStatus[];
    websiteStatuses?: string[];
  }) => void;
  onCancel: () => void;
  isSubmitting: boolean;
};

const normalizeList = (values?: string[] | null): string[] => {
  const normalized = Array.from(
    new Set((values ?? [])
      .map((code) => normalizeNafCode(code))
      .filter((code): code is string => Boolean(code)),
    ),
  );
  return normalized.slice(0, MAX_TARGET_NAF_CODES);
};

const normalizeClientSelection = (values?: string[] | null): string[] => {
  return Array.from(new Set(values ?? [])).slice(0, MAX_TARGET_CLIENTS);
};

const buildNormalizedCategories = (categories: NafCategoryStat[]): NormalizedCategory[] => {
  return categories
    .map((category) => {
      const normalizedSubs = category.subcategories
        .map((sub) => {
          const normalized = normalizeNafCode(sub.nafCode);
          if (!normalized) {
            return null;
          }
          return {
            ...sub,
            normalizedNafCode: normalized,
            displayNafCode: denormalizeNafCode(normalized),
          };
        })
        .filter((sub): sub is NormalizedSubcategory => Boolean(sub));

      const codes = Array.from(new Set(normalizedSubs.map((sub) => sub.normalizedNafCode)));
      return {
        categoryId: category.categoryId,
        name: category.name,
        subcategories: normalizedSubs,
        nafCodes: codes,
      };
    })
    .filter((category) => category.subcategories.length > 0);
};

export const SyncModeModal = ({
  isOpen,
  initialMode,
  initialReplayDate,
  initialNafCodes,
  nafCategories,
  initialTargetClientIds,
  initialNotifyAdmins,
  initialForceGoogleReplay,
  initialReplayReference,
  initialGoogleStatuses,
  googleStatuses: availableGoogleStatuses = [],
  isGoogleStatusesLoading = false,
  googleStatusesError,
  clients,
  isClientsLoading = false,
  clientsError,
  onConfirm,
  onCancel,
  isSubmitting,
}: Props) => {
  const [mode, setMode] = useState<SyncMode>(initialMode);
  const [replayDate, setReplayDate] = useState<string>(() => {
    if (initialReplayDate) {
      return initialReplayDate;
    }
    return formatDateInput(new Date());
  });
  const [formError, setFormError] = useState<string | null>(null);
  const [nafInput, setNafInput] = useState<string>("");
  const [selectedNafCodes, setSelectedNafCodes] = useState<string[]>(() => normalizeList(initialNafCodes));
  const [selectedClientIds, setSelectedClientIds] = useState<string[]>(() => normalizeClientSelection(initialTargetClientIds));
  const [notifyAdmins, setNotifyAdmins] = useState<boolean>(initialNotifyAdmins ?? true);
  const [forceGoogleReplay, setForceGoogleReplay] = useState<boolean>(initialForceGoogleReplay ?? false);
  const [replayReference, setReplayReference] = useState<DayReplayReference>(initialReplayReference ?? DEFAULT_REPLAY_REFERENCE);
  const [monthsBack, setMonthsBack] = useState<number | null>(null);
  const [clientSearch, setClientSearch] = useState<string>("");
  const [recipientError, setRecipientError] = useState<string | null>(null);
  const [linkedinEnabled, setLinkedinEnabled] = useState<boolean>(false);
  const [linkedinStatuses, setLinkedinStatuses] = useState<LinkedInStatus[]>(["pending"]);
  const [selectedGoogleStatuses, setSelectedGoogleStatuses] = useState<GoogleCheckStatus[]>([]);
  const [selectedWebsiteStatuses, setSelectedWebsiteStatuses] = useState<string[]>(["not_scraped"]);
  const supportsClientTargeting = mode === "day_replay" || mode === "full";

  useEffect(() => {
    if (isOpen) {
      setMode(initialMode);
      setReplayDate(initialReplayDate || formatDateInput(new Date()));
      setSelectedNafCodes(normalizeList(initialNafCodes));
      setNafInput("");
      setFormError(null);
      setSelectedClientIds(normalizeClientSelection(initialTargetClientIds));
      setNotifyAdmins(initialNotifyAdmins ?? true);
      setForceGoogleReplay(initialForceGoogleReplay ?? false);
      setReplayReference(initialReplayReference ?? DEFAULT_REPLAY_REFERENCE);
      setMonthsBack(null);
      setClientSearch("");
      setRecipientError(null);
      setLinkedinEnabled(initialMode === "linkedin_refresh");
      setLinkedinStatuses(["pending"]);
      setSelectedWebsiteStatuses(["not_scraped"]);
      if (initialGoogleStatuses && initialGoogleStatuses.length > 0) {
        setSelectedGoogleStatuses([...initialGoogleStatuses]);
      } else if (availableGoogleStatuses.length > 0) {
        const pending = availableGoogleStatuses.find(
          (status) => status.toLowerCase() === "pending",
        );
        setSelectedGoogleStatuses(pending ? [pending] : [availableGoogleStatuses[0]]);
      } else {
        setSelectedGoogleStatuses([]);
      }
    }
  }, [
    initialMode,
    initialReplayDate,
    initialNafCodes,
    initialTargetClientIds,
    initialNotifyAdmins,
    initialForceGoogleReplay,
    initialReplayReference,
    initialGoogleStatuses,
    isOpen,
    availableGoogleStatuses,
  ]);

  useEffect(() => {
    if (!syncModeRequiresReplayDate(mode)) {
      setFormError(null);
    }
    if (!supportsClientTargeting) {
      setRecipientError(null);
    }
    // Reset monthsBack si on passe sur un mode non-Sirene
    if (mode !== "full" && mode !== "sirene_only") {
      setMonthsBack(null);
    }
    if (mode !== "linkedin_refresh") {
      setLinkedinEnabled(false);
    } else {
      setLinkedinEnabled(true);
      setLinkedinStatuses((current) => (current.length > 0 ? current : ["pending"]));
    }
    if (mode === "google_refresh" && selectedGoogleStatuses.length === 0 && availableGoogleStatuses.length > 0) {
      const pending = availableGoogleStatuses.find((status) => status.toLowerCase() === "pending");
      setSelectedGoogleStatuses(pending ? [pending] : [availableGoogleStatuses[0]]);
    }
  }, [mode, selectedGoogleStatuses, availableGoogleStatuses, supportsClientTargeting]);



  useEffect(() => {
    if (supportsClientTargeting && (mode === "full" || notifyAdmins || selectedClientIds.length > 0)) {
      setRecipientError(null);
    }
  }, [mode, notifyAdmins, selectedClientIds, supportsClientTargeting]);

  const googleStatusOptions = useMemo(
    () => buildGoogleStatusOptions(availableGoogleStatuses),
    [availableGoogleStatuses],
  );
  const clientOptions = useMemo(() => buildClientOptions(clients), [clients]);
  const clientLookup = useMemo(() => new Map(clients.map((client) => [client.id, client])), [clients]);
  const filteredClients = useMemo(() => {
    const query = clientSearch.trim().toLowerCase();
    if (!query) {
      return clientOptions;
    }
    return clientOptions.filter((client) => client.searchTokens.includes(query));
  }, [clientOptions, clientSearch]);
  const selectedClientCount = selectedClientIds.length;
  const clientSlotsLeft = Math.max(0, MAX_TARGET_CLIENTS - selectedClientCount);
  const clientLimitReached = clientSlotsLeft === 0;
  const selectedClientChips = useMemo(
    () =>
      selectedClientIds.map((clientId) => ({
        id: clientId,
        name: clientLookup.get(clientId)?.name ?? "Client inconnu",
      })),
    [clientLookup, selectedClientIds],
  );

  const normalizedCategories = useMemo(() => buildNormalizedCategories(nafCategories), [nafCategories]);
  const allSelectableCodes = useMemo(() => {
    const set = new Set<string>();
    normalizedCategories.forEach((category) => {
      category.nafCodes.forEach((code) => set.add(code));
    });
    return Array.from(set);
  }, [normalizedCategories]);
  const limitedSelectableCodes = allSelectableCodes.slice(0, MAX_TARGET_NAF_CODES);
  const selectedSet = useMemo(() => new Set(selectedNafCodes), [selectedNafCodes]);
  const isAllSelected =
    limitedSelectableCodes.length > 0 && limitedSelectableCodes.every((code) => selectedSet.has(code));
  const selectedCount = selectedNafCodes.length;
  const remainingSlots = Math.max(0, MAX_TARGET_NAF_CODES - selectedCount);
  const modeHighlights = useMemo(() => {
    const notes: Array<{ tone: "warning" | "info"; title: string; detail: string }> = [];
    if (mode === "sirene_only") {
      notes.push({
        tone: "warning",
        title: "Google désactivé",
        detail: "Ce run ignore complètement les correspondances Google et n'enverra aucune alerte.",
      });
    }
    if (syncModeIsGoogleOnly(mode)) {
      notes.push({
        tone: "info",
        title: "Collecte Sirene non exécutée",
        detail: "Seuls les établissements déjà connus seront traités côté Google.",
      });
    }
    if (mode === "google_refresh") {
      notes.push({
        tone: "warning",
        title: "Relance Google ciblée",
        detail: "Les fiches Google des statuts sélectionnés sont recalculées et écrasent les données existantes.",
      });
    }
    if (mode === "day_replay") {
      notes.push({
        tone: "info",
        title: "Destinataires ciblés",
        detail: "Choisissez les clients à notifier et/ou les administrateurs sans avancer les curseurs.",
      });
    }
    return notes;
  }, [mode]);

  const addNafCodes = (codes: string[]) => {
    const normalized = Array.from(
      new Set(codes.map((code) => normalizeNafCode(code)).filter((code): code is string => Boolean(code))),
    );
    if (normalized.length === 0) {
      setFormError("Merci de saisir des codes NAF valides (ex: 5610A).");
      return;
    }

    setSelectedNafCodes((current) => {
      const currentSet = new Set(current);
      const unique = normalized.filter((code) => !currentSet.has(code));
      if (unique.length === 0) {
        setFormError("Ces codes sont déjà sélectionnés.");
        return current;
      }
      const slots = MAX_TARGET_NAF_CODES - current.length;
      if (slots <= 0) {
        setFormError(`Maximum ${MAX_TARGET_NAF_CODES} codes NAF atteints.`);
        return current;
      }
      const allowed = unique.slice(0, slots);
      if (allowed.length < unique.length) {
        setFormError(
          `Maximum ${MAX_TARGET_NAF_CODES} codes NAF ; seules ${slots} nouvelles sélections ont été conservées.`,
        );
      } else {
        setFormError(null);
      }
      return [...current, ...allowed];
    });
  };

  const removeNafCodes = (codes: string[]) => {
    const normalized = Array.from(
      new Set(codes.map((code) => normalizeNafCode(code)).filter((code): code is string => Boolean(code))),
    );
    if (normalized.length === 0) {
      return;
    }
    setSelectedNafCodes((current) => {
      const next = current.filter((code) => !normalized.includes(code));
      if (next.length !== current.length) {
        setFormError(null);
      }
      return next;
    });
  };

  const handleToggleSelectAll = (checked: boolean) => {
    if (checked) {
      addNafCodes(limitedSelectableCodes);
    } else {
      removeNafCodes(limitedSelectableCodes);
    }
  };

  const handleCategoryChange = (categoryCodes: string[], checked: boolean) => {
    if (checked) {
      addNafCodes(categoryCodes);
    } else {
      removeNafCodes(categoryCodes);
    }
  };

  const handleSubcategoryChange = (code: string, checked: boolean) => {
    if (checked) {
      addNafCodes([code]);
    } else {
      removeNafCodes([code]);
    }
  };

  const handleManualAdd = () => {
    const parsed = parseNafInput(nafInput);
    if (parsed.length === 0) {
      setFormError("Merci de saisir des codes NAF valides (ex: 5610A).\u00A0");
      return;
    }
    addNafCodes(parsed);
    setNafInput("");
  };

  const handleNafInputKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" || event.key === "," || event.key === ";") {
      event.preventDefault();
      handleManualAdd();
    }
  };

  const handleClientToggle = (clientId: string, checked: boolean) => {
    setSelectedClientIds((current) => {
      if (checked) {
        if (current.includes(clientId)) {
          return current;
        }
        if (current.length >= MAX_TARGET_CLIENTS) {
          setRecipientError(`Maximum ${MAX_TARGET_CLIENTS} clients ciblés.`);
          return current;
        }
        setRecipientError(null);
        return [...current, clientId];
      }
      setRecipientError(null);
      return current.filter((value) => value !== clientId);
    });
  };

  const handleClearSelectedClients = () => {
    setSelectedClientIds([]);
    setRecipientError(null);
  };

  const handleSubmit = () => {
    const requiresReplayDate = syncModeRequiresReplayDate(mode);
    if (requiresReplayDate && !replayDate) {
      setFormError("Merci de sélectionner une date à rejouer.");
      return;
    }
    setFormError(null);
    if (mode === "day_replay" && !notifyAdmins && selectedClientIds.length === 0) {
      setRecipientError("Sélectionnez au moins un client ou activez l'envoi administrateur.");
      return;
    }
    if (mode === "linkedin_refresh") {
      if (!linkedinEnabled) {
        setFormError("Merci d'activer la relance LinkedIn.");
        return;
      }
      if (linkedinStatuses.length === 0) {
        setFormError("Sélectionnez au moins un statut LinkedIn à relancer.");
        return;
      }
    }
    if (mode === "google_refresh") {
      if (selectedGoogleStatuses.length === 0) {
        setFormError("Sélectionnez au moins un statut Google à relancer.");
        return;
      }
    }
    if (mode === "website_scrape") {
      if (selectedWebsiteStatuses.length === 0) {
        setFormError("Sélectionnez au moins un statut de scraping.");
        return;
      }
    }

    const nafCodesPayload =
      selectedNafCodes.length > 0 ? selectedNafCodes.map((code) => denormalizeNafCode(code)) : undefined;
    const payload: Parameters<typeof onConfirm>[0] = {
      mode,
      replayForDate: requiresReplayDate ? replayDate : undefined,
      nafCodes: nafCodesPayload,
    };

    // Ajouter monthsBack pour les modes Sirene (full ou sirene_only)
    if ((mode === "full" || mode === "sirene_only") && monthsBack !== null && monthsBack > 0) {
      payload.monthsBack = monthsBack;
    }

    if (supportsClientTargeting && selectedClientIds.length > 0) {
      payload.targetClientIds = selectedClientIds;
    }

    if (mode === "day_replay") {
      payload.notifyAdmins = notifyAdmins;
      payload.forceGoogleReplay = forceGoogleReplay;
      payload.replayReference = replayReference;
    }

    if (mode === "linkedin_refresh") {
      payload.linkedinStatuses = linkedinEnabled ? linkedinStatuses : [];
    }

    if (mode === "google_refresh") {
      payload.googleStatuses = selectedGoogleStatuses;
    }

    if (mode === "website_scrape") {
      payload.websiteStatuses = selectedWebsiteStatuses.length > 0 ? selectedWebsiteStatuses : ["not_scraped"];
    }

    onConfirm(payload);
  };

  const isCategoryFullySelected = (codes: string[]) => codes.length > 0 && codes.every((code) => selectedSet.has(code));
  const isCategoryPartial = (codes: string[]) =>
    codes.some((code) => selectedSet.has(code)) && !isCategoryFullySelected(codes);

  if (!isOpen) {
    return null;
  }

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true">
      <div className="modal sync-mode-modal">
        <header className="modal-header">
          <div>
            <h2>Choisir le mode de synchronisation</h2>
            <p className="muted small">Sélectionnez la portée avant de lancer un nouveau traitement.</p>
          </div>
          <button type="button" className="ghost" onClick={onCancel} disabled={isSubmitting}>
            Fermer
          </button>
        </header>

        <div className="modal-content sync-mode-content">
          <section className="mode-panel">
            <header className="panel-header">
              <div>
                <h3>Mode de traitement</h3>
                <p className="muted small">Choisissez le périmètre exact avant de déclencher la synchro.</p>
              </div>
              <span className="pill">{mode === "day_replay" ? "Diagnostic" : "Production"}</span>
            </header>
            <div className="mode-options">
              {MODE_OPTIONS.map((option) => {
                const isSelected = option.value === mode;
                return (
                  <label key={option.value} className={`mode-option${isSelected ? " selected" : ""}`}>
                    <div className="mode-option-body">
                      <div className="mode-option-text">
                        <strong>{option.title}</strong>
                        <p className="muted small">{option.description}</p>
                      </div>
                      <input
                        type="radio"
                        name="sync-mode"
                        value={option.value}
                        checked={isSelected}
                        onChange={() => setMode(option.value)}
                        disabled={isSubmitting}
                        className="mode-option-control"
                      />
                    </div>
                    <p className="muted small mode-option-impact">{option.impact}</p>
                    {option.value === "google_refresh" && isSelected ? (
                      <div className="form-control">
                        {isGoogleStatusesLoading ? (
                          <p className="muted small">Chargement des statuts Google...</p>
                        ) : googleStatusOptions.length > 0 ? (
                          <details className="google-status-dropdown" open>
                            <summary>Statuts Google à relancer</summary>
                            <div className="google-status-options">
                              {googleStatusOptions.map((status) => (
                                <label key={status.value} className="google-status-option">
                                  <input
                                    type="checkbox"
                                    checked={selectedGoogleStatuses.includes(status.value)}
                                    onChange={(event) => {
                                      const checked = event.target.checked;
                                      setSelectedGoogleStatuses((current) => {
                                        if (checked) {
                                          return current.includes(status.value)
                                            ? current
                                            : [...current, status.value];
                                        }
                                        return current.filter((value) => value !== status.value);
                                      });
                                    }}
                                    disabled={isSubmitting}
                                  />
                                  <span>{status.label}</span>
                                </label>
                              ))}
                            </div>
                          </details>
                        ) : (
                          <p className="muted small">Aucun statut Google disponible en base.</p>
                        )}
                        {googleStatusesError ? (
                          <p className="muted small">{googleStatusesError}</p>
                        ) : null}
                      </div>
                    ) : null}
                    {option.value === "linkedin_refresh" && isSelected ? (
                      <div className="form-control">
                        <label className="linkedin-toggle">
                          <input
                            type="checkbox"
                            checked={linkedinEnabled}
                            onChange={(event) => setLinkedinEnabled(event.target.checked)}
                            disabled={isSubmitting}
                          />
                          <span>LinkedIn</span>
                        </label>
                        {linkedinEnabled ? (
                          <details className="linkedin-status-dropdown" open>
                            <summary>Statuts à relancer</summary>
                            <div className="linkedin-status-options">
                              {LINKEDIN_STATUS_OPTIONS.map((status) => (
                                <label key={status.value} className="linkedin-status-option">
                                  <input
                                    type="checkbox"
                                    checked={linkedinStatuses.includes(status.value)}
                                    onChange={(event) => {
                                      const checked = event.target.checked;
                                      setLinkedinStatuses((current) => {
                                        if (checked) {
                                          return current.includes(status.value)
                                            ? current
                                            : [...current, status.value];
                                        }
                                        return current.filter((value) => value !== status.value);
                                      });
                                    }}
                                    disabled={isSubmitting}
                                  />
                                  <span>{status.label}</span>
                                </label>
                              ))}
                            </div>
                          </details>
                        ) : null}
                      </div>
                    ) : null}
                    {option.value === "website_scrape" && isSelected ? (
                      <div className="form-control">
                        <details className="google-status-dropdown" open>
                          <summary>Statuts de scraping à cibler</summary>
                          <div className="google-status-options">
                            {WEBSITE_STATUS_OPTIONS.map((status) => (
                              <label key={status.value} className="google-status-option">
                                <input
                                  type="checkbox"
                                  checked={selectedWebsiteStatuses.includes(status.value)}
                                  onChange={(event) => {
                                    const checked = event.target.checked;
                                    setSelectedWebsiteStatuses((current) => {
                                      if (checked) {
                                        return current.includes(status.value)
                                          ? current
                                          : [...current, status.value];
                                      }
                                      return current.filter((value) => value !== status.value);
                                    });
                                  }}
                                  disabled={isSubmitting}
                                />
                                <span>{status.label}</span>
                              </label>
                            ))}
                          </div>
                        </details>
                      </div>
                    ) : null}
                    {option.value === "day_replay" && isSelected ? (
                      <div className="form-control">
                        <label htmlFor="replay-date" className="muted small">
                          Choisissez la date à rejouer:
                        </label>
                        <input
                          id="replay-date"
                          type="date"
                          value={replayDate}
                          max={formatDateInput(new Date())}
                          onChange={(event) => setReplayDate(event.target.value)}
                          disabled={isSubmitting}
                        />
                        <label>
                          <input
                            type="checkbox"
                            checked={forceGoogleReplay}
                            onChange={(event) => setForceGoogleReplay(event.target.checked)}
                            disabled={isSubmitting}
                          />
                          <span>Forcer les appels Google</span>
                        </label>
                        <p className="muted small">
                          Activez cette option pour relancer Google même si les fiches existent déjà pour cette date.
                        </p>
                        <div className="replay-reference-group">
                          <p className="muted small">Point de référence temporel :</p>
                          <div className="replay-reference-options">
                            {DAY_REPLAY_REFERENCE_OPTIONS.map((refOption) => (
                              <label key={refOption.value} className="replay-reference-option">
                                <input
                                  type="radio"
                                  name="replay-reference"
                                  value={refOption.value}
                                  checked={replayReference === refOption.value}
                                  onChange={() => setReplayReference(refOption.value)}
                                  disabled={isSubmitting}
                                />
                                <div>
                                  <strong>{refOption.title}</strong>
                                  <p className="muted small">{refOption.description}</p>
                                </div>
                              </label>
                            ))}
                          </div>
                        </div>
                      </div>
                    ) : null}
                  </label>
                );
              })}
            </div>
            <div className="mode-summary-card">
              <p className="label">Mode sélectionné</p>
              <p className="value">{describeSyncMode(mode)}</p>
              <p className="muted small">
                {selectedCount > 0
                  ? `${selectedCount} code(s) NAF ciblés · ${remainingSlots} emplacement(s) disponible(s)`
                  : "Aucun filtrage NAF — run global"}
              </p>
              {(mode === "full" || mode === "sirene_only") ? (
                <div className="form-control months-back-control">
                  <label htmlFor="months-back" className="muted small">
                    Nombre de mois dans le passé (optionnel) :
                  </label>
                  <input
                    id="months-back"
                    type="number"
                    min={1}
                    max={24}
                    placeholder="Synchro incrémentale"
                    value={monthsBack ?? ""}
                    onChange={(event) => {
                      const value = event.target.value;
                      if (value === "") {
                        setMonthsBack(null);
                      } else {
                        const parsed = parseInt(value, 10);
                        if (!isNaN(parsed) && parsed >= 1 && parsed <= 24) {
                          setMonthsBack(parsed);
                        }
                      }
                    }}
                    disabled={isSubmitting}
                  />
                  <p className="muted small">
                    {monthsBack
                      ? `Récupère les établissements créés dans les ${monthsBack} dernier(s) mois.`
                      : "Sans valeur, seules les nouvelles créations du jour seront synchronisées (synchro incrémentale)."}
                  </p>
                </div>
              ) : null}
            </div>
            {modeHighlights.length > 0 ? (
              <div className="mode-highlights">
                {modeHighlights.map((note, index) => (
                  <div key={`${note.title}-${index}`} className={`mode-highlight ${note.tone}`}>
                    <strong>{note.title}</strong>
                    <p className="muted small">{note.detail}</p>
                  </div>
                ))}
              </div>
            ) : null}
          </section>

          <section className="sync-target-panel">
            <header className="panel-header">
              <div>
                <h3>Cibler certains codes NAF</h3>
                <p className="muted small">Optionnel — limite la synchro aux catégories cochées ou saisies manuellement.</p>
              </div>
              <div className="selection-counter">
                <strong>{selectedCount}</strong>
                <span>/ {MAX_TARGET_NAF_CODES}</span>
                <p className="muted small">{remainingSlots} restant(s)</p>
              </div>
            </header>
            <div className="naf-filter-section">
              <div className="naf-filter-header">
                <label className="naf-select-all">
                  <span>Tout sélectionner (max {MAX_TARGET_NAF_CODES} codes)</span>
                  <input
                    type="checkbox"
                    checked={isAllSelected}
                    onChange={(event) => handleToggleSelectAll(event.target.checked)}
                    disabled={isSubmitting || limitedSelectableCodes.length === 0}
                  />
                </label>
                <span className="muted small">
                  {selectedCount} code(s) · {remainingSlots} place(s) restantes
                </span>
              </div>

              {normalizedCategories.length > 0 ? (
                <div className="naf-category-grid">
                  {normalizedCategories.map((category) => {
                    const isFull = isCategoryFullySelected(category.nafCodes);
                    const isPartial = isCategoryPartial(category.nafCodes);
                    return (
                      <div key={category.categoryId} className="naf-category">
                        <label className="naf-category-header">
                          <div>
                            <strong>{category.name}</strong>
                            <p className="muted small">{category.nafCodes.length} code(s)</p>
                          </div>
                          <input
                            type="checkbox"
                            checked={isFull}
                            data-partial={isPartial ? "true" : undefined}
                            onChange={(event) => handleCategoryChange(category.nafCodes, event.target.checked)}
                            disabled={isSubmitting || category.nafCodes.length === 0}
                          />
                        </label>
                        <div className="naf-subcategory-list">
                          {category.subcategories.map((sub) => (
                            <label key={sub.subcategoryId} className="naf-subcategory">
                              <div>
                                <strong>{sub.name}</strong>
                                <span className="muted small">{sub.displayNafCode}</span>
                              </div>
                              <input
                                type="checkbox"
                                checked={selectedSet.has(sub.normalizedNafCode)}
                                onChange={(event) => handleSubcategoryChange(sub.normalizedNafCode, event.target.checked)}
                                disabled={isSubmitting}
                              />
                            </label>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="muted small">Aucun filtrage NAF disponible pour l’instant.</p>
              )}

              <div className="naf-manual-card">
                <div className="naf-manual-add">
                  <label htmlFor="naf-filter-input">Ajouter un ou plusieurs codes (facultatif)</label>
                  <div className="naf-input-row">
                    <input
                      id="naf-filter-input"
                      type="text"
                      placeholder="Ex: 5610A, 7022Z"
                      value={nafInput}
                      onChange={(event) => setNafInput(event.target.value)}
                      onKeyDown={handleNafInputKeyDown}
                      disabled={isSubmitting}
                    />
                    <button type="button" className="ghost" onClick={handleManualAdd} disabled={isSubmitting}>
                      Ajouter
                    </button>
                  </div>
                  <p className="muted small">Séparez les codes par des virgules, espaces ou points-virgules.</p>
                </div>

                {selectedNafCodes.length > 0 ? (
                  <div className="naf-selection-preview">
                    <div className="naf-chip-list">
                      {selectedNafCodes.map((code) => (
                        <span key={code} className="naf-chip">
                          {canonicalizeNafCode(code) ?? code}
                          <button
                            type="button"
                            aria-label={`Retirer ${code}`}
                            onClick={() => removeNafCodes([code])}
                            disabled={isSubmitting}
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                    <p className="muted small">Prévisualisation : {formatNafCodesPreview(selectedNafCodes, 8)}</p>
                  </div>
                ) : (
                  <p className="muted small">Aucun code sélectionné pour le moment.</p>
                )}
              </div>
            </div>
            {formError ? <p className="muted small error">{formError}</p> : null}
          </section>

          {supportsClientTargeting ? (
            <section className="recipient-target-panel">
              <header className="panel-header">
                <div>
                  <h3>{mode === "day_replay" ? "Destinataires du rejeu" : "Destinataires des alertes"}</h3>
                  <p className="muted small">
                    {mode === "day_replay"
                      ? `Choisissez jusqu'à ${MAX_TARGET_CLIENTS} clients et/ou les administrateurs pour recevoir les alertes.`
                      : `Choisissez jusqu'à ${MAX_TARGET_CLIENTS} clients à notifier. Sans sélection, tous les clients actifs seront notifiés.`}
                  </p>
                </div>
                <div className="selection-counter">
                  <strong>{selectedClientCount}</strong>
                  <span>/ {MAX_TARGET_CLIENTS}</span>
                  <p className="muted small">{clientSlotsLeft} restant(s)</p>
                </div>
              </header>

              <div className="recipient-card">
                {mode === "day_replay" ? (
                  <label className="recipient-option admin">
                    <div>
                      <strong>Administrateurs</strong>
                      <p className="muted small">
                        Envoie un récapitulatif global de tous les établissements correspondant aux filtres ci-dessus.
                      </p>
                    </div>
                    <input
                      type="checkbox"
                      checked={notifyAdmins}
                      onChange={(event) => setNotifyAdmins(event.target.checked)}
                      disabled={isSubmitting}
                    />
                  </label>
                ) : null}

                <div className="recipient-list-header">
                  <div>
                    <strong>Clients actifs</strong>
                    <p className="muted small">
                      {clientOptions.length} disponible(s) — sélection actuelle {selectedClientCount}
                    </p>
                  </div>
                  <input
                    type="search"
                    placeholder="Rechercher un client"
                    value={clientSearch}
                    onChange={(event) => setClientSearch(event.target.value)}
                    disabled={isSubmitting || clientOptions.length === 0}
                  />
                </div>

                {isClientsLoading ? (
                  <p className="muted small">Chargement des clients…</p>
                ) : clientsError ? (
                  <p className="muted small error">{clientsError}</p>
                ) : clientOptions.length === 0 ? (
                  <p className="muted small">Aucun client actif pour le moment.</p>
                ) : filteredClients.length === 0 ? (
                  <p className="muted small">Aucun client ne correspond à votre recherche.</p>
                ) : (
                  <div className="recipient-list">
                    {filteredClients.map((client) => {
                      const isSelected = selectedClientIds.includes(client.id);
                      return (
                        <label
                          key={client.id}
                          className={`recipient-option${isSelected ? " selected" : ""}`}
                        >
                          <div>
                            <strong>{client.name}</strong>
                            <p className="muted small">{client.listingSummary}</p>
                            <p className="muted small">{client.nafSummary}</p>
                            <p className="muted small">{client.recipientCount} destinataire(s)</p>
                          </div>
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={(event) => handleClientToggle(client.id, event.target.checked)}
                            disabled={isSubmitting || (!isSelected && clientLimitReached)}
                          />
                        </label>
                      );
                    })}
                  </div>
                )}

                {selectedClientChips.length > 0 ? (
                  <div className="recipient-selection-preview">
                    <div className="recipient-chip-list">
                      {selectedClientChips.map((chip) => (
                        <span key={chip.id} className="recipient-chip">
                          {chip.name}
                          <button
                            type="button"
                            aria-label={`Retirer ${chip.name}`}
                            onClick={() => handleClientToggle(chip.id, false)}
                            disabled={isSubmitting}
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                    <button
                      type="button"
                      className="ghost"
                      onClick={handleClearSelectedClients}
                      disabled={isSubmitting}
                    >
                      Effacer la sélection
                    </button>
                  </div>
                ) : null}
              </div>

              {recipientError ? <p className="muted small error">{recipientError}</p> : null}
            </section>
          ) : null}
        </div>

        <footer className="modal-footer">
          <button type="button" className="ghost" onClick={onCancel} disabled={isSubmitting}>
            Annuler
          </button>
          <button type="button" className="primary" onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting ? "Déclenchement…" : "Lancer la synchro"}
          </button>
        </footer>
      </div>
    </div>
  );
};
