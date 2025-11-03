export interface SyncRun {
  id: string;
  scopeKey: string;
  runType: string;
  status: string;
  startedAt: string;
  finishedAt: string | null;
  apiCallCount: number;
  fetchedRecords: number;
  createdRecords: number;
  lastCursor: string | null;
  queryChecksum: string | null;
  resumedFromRunId: string | null;
  notes: string | null;
  maxRecords: number | null;
  totalExpectedRecords: number | null;
  progress: number | null;
  estimatedRemainingSeconds: number | null;
  estimatedCompletionAt: string | null;
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
  lastFullRun: SyncRun | null;
  lastIncrementalRun: SyncRun | null;
  lastAlert: Alert | null;
}

export interface SyncRequestPayload {
  resume: boolean;
  maxRecords: number | null;
}

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
}
