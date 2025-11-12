import { EstablishmentsSection } from "../EstablishmentsSection";
import type { Establishment } from "../../types";

type Props = {
  establishments: Establishment[] | undefined;
  isLoading: boolean;
  error: Error | null;
  limit: number;
  page: number;
  query: string;
  hasNextPage: boolean;
  onLimitChange: (limit: number) => void;
  onPageChange: (page: number) => void;
  onQueryChange: (query: string) => void;
  onRefresh: () => void;
  onDeleteEstablishment: (siret: string) => void;
  deletingSiret: string | null;
  isDeletingOne: boolean;
  feedbackMessage: string | null;
  errorMessage: string | null;
  onTriggerGoogleCheck: (siret: string) => void;
  isCheckingGoogle: boolean;
  checkingGoogleSiret: string | null;
  onSelectEstablishment: (siret: string) => void;
};

export const EstablishmentsView = ({
  establishments,
  isLoading,
  error,
  limit,
  page,
  query,
  hasNextPage,
  onLimitChange,
  onPageChange,
  onQueryChange,
  onRefresh,
  onDeleteEstablishment,
  deletingSiret,
  isDeletingOne,
  feedbackMessage,
  errorMessage,
  onTriggerGoogleCheck,
  isCheckingGoogle,
  checkingGoogleSiret,
  onSelectEstablishment,
}: Props) => {
  return (
    <section className="dashboard-section">
      <div className="section-header">
        <div>
          <h2>Etablissements</h2>
          <p className="muted">Recherche et suppression sécurisée des établissements.</p>
        </div>
      </div>
      <div className="section-grid">
        <EstablishmentsSection
          establishments={establishments}
          isLoading={isLoading}
          error={error}
          limit={limit}
          page={page}
          query={query}
          hasNextPage={hasNextPage}
          onLimitChange={onLimitChange}
          onPageChange={onPageChange}
          onQueryChange={onQueryChange}
          onRefresh={onRefresh}
          onDeleteEstablishment={onDeleteEstablishment}
          deletingSiret={deletingSiret}
          isDeletingOne={isDeletingOne}
          feedbackMessage={feedbackMessage}
          errorMessage={errorMessage}
          onTriggerGoogleCheck={onTriggerGoogleCheck}
          isCheckingGoogle={isCheckingGoogle}
          checkingGoogleSiret={checkingGoogleSiret}
          onSelectEstablishment={onSelectEstablishment}
        />
      </div>
    </section>
  );
};
