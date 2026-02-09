import { useQuery } from "@tanstack/react-query";

import { nafApi, regionsApi } from "../../api";
import type { NafCategory, NafSubCategory, Region } from "../../types";
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

  const subcategoriesQuery = useQuery<NafSubCategory[]>({
    queryKey: ["naf-subcategories"],
    queryFn: () => nafApi.listSubCategories(),
  });

  const regionsQuery = useQuery<Region[]>({
    queryKey: ["regions"],
    queryFn: () => regionsApi.list(),
    staleTime: 5 * 60 * 1000,
  });

  const error = categoriesQuery.error instanceof Error ? categoriesQuery.error : null;

  return (
    <NafConfigView
      categories={categoriesQuery.data}
      allSubcategories={subcategoriesQuery.data}
      isLoading={categoriesQuery.isLoading}
      isFetching={categoriesQuery.isFetching}
      error={error}
      onRefresh={() => {
        categoriesQuery.refetch();
        subcategoriesQuery.refetch();
      }}
      regions={regionsQuery.data}
      isAuthenticated={isAuthenticated}
      onRequireToken={onRequireToken}
      onUnauthorized={onUnauthorized}
    />
  );
};
