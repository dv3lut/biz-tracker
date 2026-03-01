import { useCallback, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, syncApi } from "../../api";
import type { SyncRun, SyncState } from "../../types";
import { SyncView } from "../../components/views/SyncView";
import { useRefreshIndicator } from "../../hooks/useRefreshIndicator";

type Props = {
  onUnauthorized: () => void;
};

export const SyncSection = ({ onUnauthorized }: Props) => {
  const queryClient = useQueryClient();
  const [runsLimit, setRunsLimit] = useState(20);

  const syncRunsQuery = useQuery<SyncRun[]>({
    queryKey: ["sync-runs", runsLimit],
    queryFn: () => syncApi.fetchRuns(runsLimit),
  });

  const syncStateQuery = useQuery<SyncState[]>({
    queryKey: ["sync-state"],
    queryFn: () => syncApi.fetchState(),
  });

  const showError = useCallback(
    (error: unknown) => {
      if (error instanceof ApiError && error.status === 403) {
        onUnauthorized();
        return;
      }
      console.error(error);
    },
    [onUnauthorized],
  );

  const deleteRunMutation = useMutation({
    mutationFn: (runId: string) => syncApi.deleteRun(runId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sync-runs"] });
      queryClient.invalidateQueries({ queryKey: ["sync-state"] });
      queryClient.invalidateQueries({ queryKey: ["stats-summary"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-metrics"] });
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      queryClient.invalidateQueries({ queryKey: ["establishments"] });
    },
    onError: showError,
  });

  const handleDeleteRun = useCallback(
    (runId: string) => {
      deleteRunMutation.mutate(runId);
    },
    [deleteRunMutation],
  );

  const runsIsRefreshing = useRefreshIndicator(syncRunsQuery.isFetching && !syncRunsQuery.isLoading);
  const statesIsRefreshing = useRefreshIndicator(syncStateQuery.isFetching && !syncStateQuery.isLoading);

  const deletingRunId = useMemo(() => {
    if (!deleteRunMutation.isPending) {
      return null;
    }
    return (deleteRunMutation.variables as string | undefined) ?? null;
  }, [deleteRunMutation.isPending, deleteRunMutation.variables]);

  const runsError = syncRunsQuery.error instanceof Error ? syncRunsQuery.error : null;
  const statesError = syncStateQuery.error instanceof Error ? syncStateQuery.error : null;

  return (
    <SyncView
      runs={syncRunsQuery.data}
      isRunsLoading={syncRunsQuery.isLoading}
      runsError={runsError}
      runsLimit={runsLimit}
      onRunsLimitChange={setRunsLimit}
      onRefreshRuns={() => syncRunsQuery.refetch()}
      onDeleteRun={handleDeleteRun}
      deletingRunId={deletingRunId}
      isDeletingRun={deleteRunMutation.isPending}
      isRunsRefreshing={runsIsRefreshing}
      states={syncStateQuery.data}
      isStatesLoading={syncStateQuery.isLoading}
      statesError={statesError}
      onRefreshStates={() => syncStateQuery.refetch()}
      isStatesRefreshing={statesIsRefreshing}
    />
  );
};
