export type SyncMode = "full" | "sirene_only" | "google_pending" | "google_refresh" | "day_replay";
export type DayReplayReference = "creation_date" | "insertion_date";

export type ListingStatus = "recent_creation" | "recent_creation_missing_contact" | "not_recent_creation";

export interface SyncRun {
  id: string;
  scopeKey: string;
  runType: string;
  status: string;
  mode: SyncMode;
  replayForDate: string | null;
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
  targetNafCodes: string[] | null;
  targetClientIds: string[] | null;
  notifyAdmins: boolean;
  dayReplayForceGoogle: boolean;
  dayReplayReference: DayReplayReference;
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
  resetGoogleState?: boolean;
  replayForDate?: string;
  replayReference?: DayReplayReference;
  nafCodes?: string[];
  initialBackfill?: boolean;
  targetClientIds?: string[];
  notifyAdmins?: boolean;
  forceGoogleReplay?: boolean;
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
  googleDepartmentCount: number;
  googleDepartmentAll: boolean;
  googleDepartments: Department[];
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

export interface Department {
  id: string;
  code: string;
  name: string;
  orderIndex: number;
  regionId: string;
}

export interface Region {
  id: string;
  code: string;
  name: string;
  orderIndex: number;
  departments: Department[];
}

export interface ClientSubscription {
  clientId: string;
  subcategoryId: string;
  createdAt: string;
  subcategory: NafSubCategory;
}

export interface StripeSubscriptionHistory {
  id: string;
  clientId: string;
  stripeSubscriptionId: string;
  stripeCustomerId: string | null;
  status: string | null;
  planKey: string | null;
  priceId: string | null;
  referrerName: string | null;
  purchasedAt: string | null;
  trialStartAt: string | null;
  trialEndAt: string | null;
  paidStartAt: string | null;
  currentPeriodStart: string | null;
  currentPeriodEnd: string | null;
  cancelAt: string | null;
  canceledAt: string | null;
  endedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ClientSubscriptionEvent {
  id: string;
  clientId: string;
  stripeSubscriptionId: string | null;
  eventType: string;
  fromPlanKey: string | null;
  toPlanKey: string | null;
  fromCategoryIds: string[] | null;
  toCategoryIds: string[] | null;
  effectiveAt: string | null;
  source: string | null;
  createdAt: string;
}

export interface Client {
  id: string;
  name: string;
  startDate: string;
  endDate: string | null;
  listingStatuses: ListingStatus[];
  includeAdminsInClientAlerts: boolean;
  useSubcategoryLabelInClientAlerts: boolean;
  emailsSentCount: number;
  lastEmailSentAt: string | null;
  createdAt: string;
  updatedAt: string;
  recipients: ClientRecipient[];
  subscriptions: ClientSubscription[];
  departments: Department[];
  stripeSubscriptions: StripeSubscriptionHistory[];
  subscriptionEvents: ClientSubscriptionEvent[];
}

export interface AdminEmailConfig {
  recipients: string[];
  includePreviousMonthDayAlerts: boolean;
}

export interface AdminStripeSettings {
  trialPeriodDays: number;
}

export interface AdminStripeSettingsUpdatePayload {
  trialPeriodDays: number;
  applyToExistingTrials: boolean;
}

export interface AdminStripeSettingsUpdateResult {
  trialPeriodDays: number;
  updatedTrials: number;
  failedTrials: number;
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

export interface GoogleFindPlaceCandidate {
  placeId: string | null;
  name: string | null;
  formattedAddress: string | null;
  matchScore: number | null;
  decision: string | null;
  decisionDetails: Record<string, unknown> | null;
}

export interface GoogleFindPlaceDebugResult {
  query: string;
  candidateCount: number;
  candidates: GoogleFindPlaceCandidate[];
}

export interface GoogleRetryConfig {
  retryWeekdays: number[];
  retryMissingContactEnabled: boolean;
  retryMissingContactFrequencyDays: number;
  defaultRules: GoogleRetryRule[];
  microRules: GoogleRetryRule[];
}

export interface SireneNewBusiness {
  siret: string;
  siren: string | null;
  nic: string | null;
  name: string | null;
  nafCode: string | null;
  nafLabel: string | null;
  dateCreation: string | null;
  isIndividual: boolean;
  leaderName: string | null;
  denominationUniteLegale: string | null;
  denominationUsuelleUniteLegale: string | null;
  denominationUsuelleEtablissement: string | null;
  enseigne1: string | null;
  enseigne2: string | null;
  enseigne3: string | null;
  complementAdresse: string | null;
  numeroVoie: string | null;
  indiceRepetition: string | null;
  typeVoie: string | null;
  libelleVoie: string | null;
  codePostal: string | null;
  libelleCommune: string | null;
  libelleCommuneEtranger: string | null;
}

export interface SireneNewBusinessesResult {
  total: number;
  returned: number;
  establishments: SireneNewBusiness[];
}
