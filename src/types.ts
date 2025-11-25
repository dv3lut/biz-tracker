export type SyncMode = "full" | "sirene_only";

export interface SyncRun {
  id: string;
  scopeKey: string;
  runType: string;
  status: string;
  mode: SyncMode;
  startedAt: string;
  finishedAt: string | null;
  apiCallCount: number;
  googleApiCallCount: number;
  fetchedRecords: number;
  createdRecords: number;
  updatedRecords: number;
  googleQueueCount: number;
  googleEligibleCount: number;
  googleMatchedCount: number;
  googlePendingCount: number;
  googleImmediateMatchedCount: number;
  googleLateMatchedCount: number;
  lastCursor: string | null;
  queryChecksum: string | null;
  resumedFromRunId: string | null;
  notes: string | null;
  totalExpectedRecords: number | null;
  progress: number | null;
  estimatedRemainingSeconds: number | null;
  estimatedCompletionAt: string | null;
  googleEnabled: boolean;
  summary: RunSummary | null;
}

export interface SyncState {
  scopeKey: string;
  lastSuccessfulRunId: string | null;
  lastCursor: string | null;
  cursorCompleted: boolean;
  lastSyncedAt: string | null;
  lastTotal: number | null;
  lastTreatedMax: string | null;
  queryChecksum: string | null;
  updatedAt: string;
}

export interface AlertPayload {
  [key: string]: unknown;
}

export interface Alert {
  id: string;
  runId: string;
  siret: string;
  recipients: string[];
  payload: AlertPayload;
  createdAt: string;
  sentAt: string | null;
}

export interface StatsSummary {
  totalEstablishments: number;
  totalAlerts: number;
  databaseSizePretty: string | null;
  lastRun: SyncRun | null;
  lastAlert: Alert | null;
}

export interface DailyMetricPoint {
  date: string;
  value: number;
}

export interface DailyApiMetricPoint extends DailyMetricPoint {
  runCount: number;
  googleApiCallCount: number;
}

export interface DailyAlertMetricPoint {
  date: string;
  created: number;
  sent: number;
}

export interface DailyRunOutcomePoint {
  date: string;
  createdRecords: number;
  updatedRecords: number;
}

export interface DailyGoogleStatusPoint {
  date: string;
  immediateMatches: number;
  lateMatches: number;
  notFound: number;
  insufficient: number;
  pending: number;
  other: number;
}

export interface GoogleStatusBreakdown {
  found: number;
  notFound: number;
  insufficient: number;
  pending: number;
  other: number;
}

export interface GoogleListingAgeBreakdown {
  recentCreation: number;
  recentCreationMissingContact: number;
  notRecentCreation: number;
  unknown: number;
}

export interface NafSubCategoryStat {
  subcategoryId: string;
  nafCode: string;
  name: string;
  establishmentCount: number;
  googleFound: number;
  googleNotFound: number;
  googleInsufficient: number;
  googlePending: number;
  googleTypeMismatch: number;
  googleOther: number;
  listingRecent: number;
  listingRecentMissingContact: number;
  listingNotRecent: number;
  listingUnknown: number;
}

export interface NafCategoryStat {
  categoryId: string;
  name: string;
  totalEstablishments: number;
  subcategories: NafSubCategoryStat[];
}

export interface DashboardRunBreakdown {
  runId: string;
  startedAt: string;
  createdRecords: number;
  updatedRecords: number;
  apiCallCount: number;
  googleApiCallCount: number;
  googleFound: number;
  googleFoundLate: number;
  googleNotFound: number;
  googleInsufficient: number;
  googlePending: number;
  googleOther: number;
  listingRecent: number;
  listingRecentMissingContact: number;
  listingNotRecent: number;
  listingUnknown: number;
  alertsCreated: number;
  alertsSent: number;
}

export interface RunSummary {
  run: RunSummaryMeta;
  stats: RunSummaryStats;
  samples: RunSummarySamples;
  email?: RunEmailSummary;
}

export interface RunSummaryMeta {
  id: string;
  scopeKey: string;
  status: string;
  mode: SyncMode;
  startedAt: string | null;
  finishedAt: string | null;
  durationSeconds: number;
  pageCount: number;
}

export interface RunSummaryStats {
  mode: SyncMode;
  fetchedRecords: number;
  createdRecords: number;
  updatedRecords: number;
  apiCallCount: number;
  google: {
    enabled: boolean;
    apiCallCount: number;
    queueCount: number;
    eligibleCount: number;
    matchedCount: number;
    immediateMatches: number;
    lateMatches: number;
    pendingCount: number;
  };
  alerts: {
    created: number;
    sent: number;
  };
}

export interface RunSummarySamples {
  newEstablishments: RunSummaryEstablishment[];
  updatedEstablishments: RunSummaryUpdatedEstablishment[];
  googleLateMatches: RunSummaryEstablishment[];
  googleImmediateMatches: RunSummaryEstablishment[];
}

export interface RunSummaryEstablishment {
  siret: string;
  name: string | null;
  codePostal: string | null;
  libelleCommune: string | null;
  nafCode: string | null;
  googleStatus: string | null;
  googlePlaceUrl: string | null;
  googlePlaceId: string | null;
  googleMatchConfidence: number | null;
  createdRunId: string | null;
  firstSeenAt: string | null;
  lastSeenAt: string | null;
}

export interface RunSummaryUpdatedEstablishment extends RunSummaryEstablishment {
  changedFields: string[];
}

export interface RunEmailSummary {
  sent: boolean;
  recipients: string[];
  subject: string | null;
  reason?: string | null;
}

export interface DashboardMetrics {
  latestRun: SyncRun | null;
  latestRunBreakdown: DashboardRunBreakdown | null;
  dailyNewBusinesses: DailyMetricPoint[];
  dailyApiCalls: DailyApiMetricPoint[];
  dailyAlerts: DailyAlertMetricPoint[];
  dailyRunOutcomes: DailyRunOutcomePoint[];
  dailyGoogleStatuses: DailyGoogleStatusPoint[];
  googleStatusBreakdown: GoogleStatusBreakdown;
  listingAgeBreakdown: GoogleListingAgeBreakdown;
  establishmentStatusBreakdown: Record<string, number>;
  nafCategoryBreakdown: NafCategoryStat[];
}

export interface SyncRequestPayload {
  checkForUpdates?: boolean;
  mode?: SyncMode;
}

export type EstablishmentIndividualFilter = "all" | "individual" | "non_individual";

export interface Establishment {
  siret: string;
  siren: string;
  name: string;
  nafCode: string | null;
  nafLibelle: string | null;
  etatAdministratif: string | null;
  codePostal: string | null;
  libelleCommune: string | null;
  dateCreation: string | null;
  dateDebutActivite: string | null;
  firstSeenAt: string | null;
  lastSeenAt: string | null;
  updatedAt: string | null;
  createdRunId: string | null;
  lastRunId: string | null;
  googlePlaceId: string | null;
  googlePlaceUrl: string | null;
  googleLastCheckedAt: string | null;
  googleLastFoundAt: string | null;
  googleCheckStatus: string;
  googleMatchConfidence: number | null;
  googleListingOriginAt: string | null;
  googleListingOriginSource: string | null;
  googleListingAgeStatus: string | null;
  googleContactPhone: string | null;
  googleContactEmail: string | null;
  googleContactWebsite: string | null;
  isSoleProprietorship: boolean;
}

export interface EstablishmentDetail extends Establishment {
  nic: string | null;
  denominationUniteLegale: string | null;
  denominationUsuelleUniteLegale: string | null;
  denominationUsuelleEtablissement: string | null;
  enseigne1: string | null;
  enseigne2: string | null;
  enseigne3: string | null;
  categorieJuridique: string | null;
  categorieEntreprise: string | null;
  trancheEffectifs: string | null;
  anneeEffectifs: number | null;
  nomUsage: string | null;
  nom: string | null;
  prenom1: string | null;
  prenom2: string | null;
  prenom3: string | null;
  prenom4: string | null;
  prenomUsuel: string | null;
  pseudonyme: string | null;
  sexe: string | null;
  dateDernierTraitementEtablissement: string | null;
  dateDernierTraitementUniteLegale: string | null;
  complementAdresse: string | null;
  numeroVoie: string | null;
  indiceRepetition: string | null;
  typeVoie: string | null;
  libelleVoie: string | null;
  distributionSpeciale: string | null;
  libelleCommuneEtranger: string | null;
  codeCommune: string | null;
  codeCedex: string | null;
  libelleCedex: string | null;
  codePays: string | null;
  libellePays: string | null;
}

export interface EmailTestPayload {
  subject?: string;
  body?: string;
  recipients?: string[];
}

export interface EmailTestResult {
  sent: boolean;
  provider: string;
  subject: string;
  recipients: string[];
}

export interface ClientRecipient {
  id: string;
  email: string;
  createdAt: string;
}

export interface NafSubCategory {
  id: string;
  categoryId: string;
  name: string;
  description: string | null;
  nafCode: string;
  priceCents: number;
  priceEur: number;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface NafCategory {
  id: string;
  name: string;
  description: string | null;
  keywords: string[];
  createdAt: string;
  updatedAt: string;
  subcategories: NafSubCategory[];
}

export interface ClientSubscription {
  clientId: string;
  subcategoryId: string;
  createdAt: string;
  subcategory: NafSubCategory;
}

export interface Client {
  id: string;
  name: string;
  startDate: string;
  endDate: string | null;
  emailsSentCount: number;
  lastEmailSentAt: string | null;
  createdAt: string;
  updatedAt: string;
  recipients: ClientRecipient[];
  subscriptions: ClientSubscription[];
}

export interface AdminEmailConfig {
  recipients: string[];
}

export interface GoogleCheckResult {
  found: boolean;
  emailSent: boolean;
  message: string;
  placeId: string | null;
  placeUrl: string | null;
  checkStatus: string;
  establishment: Establishment;
}

export interface GoogleRetryRule {
  maxAgeDays: number | null;
  frequencyDays: number;
}

export interface GoogleRetryConfig {
  retryWeekdays: number[];
  defaultRules: GoogleRetryRule[];
  microRules: GoogleRetryRule[];
}
