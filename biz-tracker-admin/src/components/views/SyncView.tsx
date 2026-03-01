import { SyncRunsTable } from "../SyncRunsTable";
import { SyncStateTable } from "../SyncStateTable";
import type { SyncRun, SyncState } from "../../types";

type Props = {
  runs: SyncRun[] | undefined;
  isRunsLoading: boolean;
  runsError: Error | null;
  runsLimit: number;
  onRunsLimitChange: (limit: number) => void;
  onRefreshRuns: () => void;
  onDeleteRun: (runId: string) => void;
  deletingRunId: string | null;
  isDeletingRun: boolean;
  isRunsRefreshing: boolean;
  states: SyncState[] | undefined;
  isStatesLoading: boolean;
  statesError: Error | null;
  onRefreshStates: () => void;
  isStatesRefreshing: boolean;
};

export const SyncView = ({
  runs,
  isRunsLoading,
  runsError,
  runsLimit,
  onRunsLimitChange,
  onRefreshRuns,
  onDeleteRun,
  deletingRunId,
  isDeletingRun,
  isRunsRefreshing,
  states,
  isStatesLoading,
  statesError,
  onRefreshStates,
  isStatesRefreshing,
}: Props) => {
  return (
    <section className="dashboard-section">
      <div className="section-header">
        <div>
          <h2>Synchronisations</h2>
          <p className="muted">Historique des traitements et état des curseurs.</p>
        </div>
      </div>
      <div className="section-grid two-column">
        <SyncRunsTable
          runs={runs}
          isLoading={isRunsLoading}
          error={runsError}
          limit={runsLimit}
          onLimitChange={onRunsLimitChange}
          onRefresh={onRefreshRuns}
          onDeleteRun={onDeleteRun}
          deletingRunId={deletingRunId}
          isDeletingRun={isDeletingRun}
          isRefreshing={isRunsRefreshing}
        />
        <SyncStateTable
          states={states}
          isLoading={isStatesLoading}
          error={statesError}
          onRefresh={onRefreshStates}
          isRefreshing={isStatesRefreshing}
        />
      </div>
    </section>
  );
};
