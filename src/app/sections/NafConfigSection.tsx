import { useQuery } from "@tanstack/react-query";

import { nafApi } from "../../api";
import type { NafCategory } from "../../types";
import { NafConfigView } from "../../components/views/NafConfigView";

type Props = {
  isAuthenticated: boolean;
  onRequireToken: () => void;
  onUnauthorized: () => void;
};

export const NafConfigSection = ({ isAuthenticated, onRequireToken, onUnauthorized }: Props) => {
  const categoriesQuery = useQuery<NafCategory[]>({
    queryKey: ["naf-categories"],
    queryFn: () => nafApi.listCategories(),
  });

  const error = categoriesQuery.error instanceof Error ? categoriesQuery.error : null;

  return (
    <NafConfigView
      categories={categoriesQuery.data}
      isLoading={categoriesQuery.isLoading}
      isFetching={categoriesQuery.isFetching}
      error={error}
      onRefresh={() => categoriesQuery.refetch()}
      isAuthenticated={isAuthenticated}
      onRequireToken={onRequireToken}
      onUnauthorized={onUnauthorized}
    />
  );
};
