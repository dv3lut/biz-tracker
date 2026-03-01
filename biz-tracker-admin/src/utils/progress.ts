import { SyncRun } from "../types";

const clamp = (value: number): number => {
  if (Number.isNaN(value)) {
    return 0;
  }
  return Math.min(Math.max(value, 0), 1);
};

export interface SireneProgress {
  value: number | null;
  processed: number;
  total: number | null;
}

export interface GoogleProgress {
  value: number | null;
  processed: number;
  total: number | null;
  pending: number;
}

export const computeSireneProgress = (run: SyncRun): SireneProgress => {
  const total = typeof run.totalExpectedRecords === "number" && run.totalExpectedRecords > 0
    ? run.totalExpectedRecords
    : null;

  let value: number | null = null;
  if (typeof run.progress === "number") {
    value = clamp(run.progress);
  } else if (total) {
    value = clamp(run.fetchedRecords / total);
  }

  return {
    value,
    processed: run.fetchedRecords,
    total,
  };
};

export const computeGoogleProgress = (run: SyncRun): GoogleProgress => {
  if (!run.googleEnabled) {
    return {
      value: null,
      processed: 0,
      total: null,
      pending: 0,
    };
  }
  const totalCandidate = run.googleQueueCount > 0 ? run.googleQueueCount : run.googleEligibleCount;
  const total = totalCandidate > 0 ? totalCandidate : null;
  const pending = Math.max(run.googlePendingCount, 0);
  const processed = total ? Math.max(total - pending, 0) : Math.max(run.googleMatchedCount, 0);
  const value = total ? clamp(processed / total) : null;

  return {
    value,
    processed,
    total,
    pending,
  };
};

export interface LinkedInProgress {
  value: number | null;
  total: number | null;
  searched: number;
  found: number;
  notFound: number;
  error: number;
}

export const computeLinkedInProgress = (run: SyncRun): LinkedInProgress => {
  if (!run.linkedinEnabled) {
    return {
      value: null,
      total: null,
      searched: 0,
      found: 0,
      notFound: 0,
      error: 0,
    };
  }
  const total = run.linkedinQueueCount > 0 ? run.linkedinQueueCount : null;
  const searched = run.linkedinSearchedCount;
  const value = total && total > 0 ? clamp(searched / total) : null;

  return {
    value,
    total,
    searched,
    found: run.linkedinFoundCount,
    notFound: run.linkedinNotFoundCount,
    error: run.linkedinErrorCount,
  };
};
