import { useMemo } from "react";

import { DashboardMetrics } from "../../types";

export type RunOutcomeChartEntry = {
  key: string;
  label: string;
  created: number;
  updated: number;
};

export type ApiActivityChartEntry = {
  key: string;
  label: string;
  apiCalls: number;
  googleApiCalls: number;
  runCount: number;
};

export type AlertsChartEntry = {
  key: string;
  label: string;
  sent: number;
  pending: number;
};

export type GoogleStatusChartEntry = {
  key: string;
  label: string;
  immediate: number;
  late: number;
  notFound: number;
  insufficient: number;
  pending: number;
  other: number;
};

const shortDate = (value: string): string => {
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("fr-FR", {
    day: "2-digit",
    month: "2-digit",
  }).format(date);
};

const sumValues = (entries: Array<{ value?: number }>) =>
  entries.reduce((acc, entry) => acc + Number(entry.value ?? 0), 0);

export const useDashboardChartData = (metrics: DashboardMetrics | undefined, days: number) => {
  return useMemo(() => {
    const clampedWindow = Math.max(Math.min(days, 30), 1);

    const runOutcomeSeries = metrics ? metrics.dailyRunOutcomes.slice(-clampedWindow) : [];
    const apiVolumeSeries = metrics ? metrics.dailyApiCalls.slice(-clampedWindow) : [];
    const alertSeries = metrics ? metrics.dailyAlerts.slice(-clampedWindow) : [];
    const googleStatusSeries = metrics ? metrics.dailyGoogleStatuses.slice(-clampedWindow) : [];

    const runOutcomeChartData: RunOutcomeChartEntry[] = runOutcomeSeries.map((item) => ({
      key: item.date,
      label: shortDate(item.date),
      created: item.createdRecords,
      updated: item.updatedRecords,
    }));

    const apiActivityChartData: ApiActivityChartEntry[] = apiVolumeSeries.map((item) => ({
      key: item.date,
      label: shortDate(item.date),
      apiCalls: item.value,
      googleApiCalls: item.googleApiCallCount,
      runCount: item.runCount,
    }));

    const alertsChartData: AlertsChartEntry[] = alertSeries.map((item) => ({
      key: item.date,
      label: shortDate(item.date),
      sent: item.sent,
      pending: Math.max(item.created - item.sent, 0),
    }));

    const googleStatusChartData: GoogleStatusChartEntry[] = googleStatusSeries.map((item) => ({
      key: item.date,
      label: shortDate(item.date),
      immediate: item.immediateMatches,
      late: item.lateMatches,
      notFound: item.notFound,
      insufficient: item.insufficient,
      pending: item.pending,
      other: item.other,
    }));

    const hasRunOutcomeData = runOutcomeChartData.some((entry) => entry.created > 0 || entry.updated > 0);
    const hasApiData = apiActivityChartData.some((entry) => entry.apiCalls > 0 || entry.googleApiCalls > 0);
    const hasAlertsData = alertsChartData.some((entry) => entry.sent > 0 || entry.pending > 0);
    const hasGoogleStatusData = googleStatusChartData.some(
      (entry) => sumValues([
        { value: entry.immediate },
        { value: entry.late },
        { value: entry.notFound },
        { value: entry.insufficient },
        { value: entry.pending },
        { value: entry.other },
      ]) > 0,
    );

    return {
      runOutcomeChartData,
      apiActivityChartData,
      alertsChartData,
      googleStatusChartData,
      hasRunOutcomeData,
      hasApiData,
      hasAlertsData,
      hasGoogleStatusData,
    };
  }, [metrics, days]);
};
