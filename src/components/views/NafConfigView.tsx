import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { ApiError, nafApi, type NafCategoryPayload, type NafSubCategoryCreatePayload, type NafSubCategoryUpdatePayload } from "../../api";
import type { NafCategory, NafSubCategory, Region } from "../../types";
import { useRefreshIndicator } from "../../hooks/useRefreshIndicator";
import { NafCategoriesSection } from "../NafCategoriesSection";
import { NafCategoryModal, type NafCategoryFormPayload } from "../NafCategoryModal";
import { NafSubCategoryModal, type NafSubCategoryFormPayload } from "../NafSubCategoryModal";

 type CategoryModalState = { mode: "create" | "edit"; category: NafCategory | null } | null;
type SubCategoryModalState =
  | { mode: "create"; subcategory: null; initialCategoryId?: string }
  | { mode: "edit"; subcategory: NafSubCategory }
  | null;

type Props = {
  categories: NafCategory[] | undefined;
  isLoading: boolean;
  isFetching: boolean;
  error: Error | null;
  onRefresh: () => void;
  regions: Region[] | undefined;
  isAuthenticated: boolean;
  onRequireToken: () => void;
  onUnauthorized: () => void;
};

export const NafConfigView = ({
  categories,
  isLoading,
  isFetching,
  error,
  onRefresh,
  regions,
  isAuthenticated,
  onRequireToken,
  onUnauthorized,
}: Props) => {
  const queryClient = useQueryClient();
  const [categoryModalState, setCategoryModalState] = useState<CategoryModalState>(null);
  const [subcategoryModalState, setSubCategoryModalState] = useState<SubCategoryModalState>(null);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [deletingCategoryId, setDeletingCategoryId] = useState<string | null>(null);
  const [deletingSubCategoryId, setDeletingSubCategoryId] = useState<string | null>(null);

  const isRefreshing = useRefreshIndicator(isFetching && !isLoading, { delay: 300, minVisible: 250 });

  useEffect(() => {
    if (!feedbackMessage) {
      return;
    }
    const timeout = window.setTimeout(() => setFeedbackMessage(null), 4000);
    return () => window.clearTimeout(timeout);
  }, [feedbackMessage]);

  useEffect(() => {
    if (!errorMessage) {
      return;
    }
    const timeout = window.setTimeout(() => setErrorMessage(null), 4000);
    return () => window.clearTimeout(timeout);
  }, [errorMessage]);

  const ensureAuthenticated = useCallback(() => {
    if (!isAuthenticated) {
      onRequireToken();
      return false;
    }
    return true;
  }, [isAuthenticated, onRequireToken]);

  const invalidateCategories = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["naf-categories"] });
  }, [queryClient]);

  const handleMutationError = useCallback(
    (error: unknown) => {
      if (error instanceof ApiError && error.status === 403) {
        onUnauthorized();
        return;
      }
      const message = error instanceof ApiError ? error.message : "La mise à jour NAF a échoué.";
      setErrorMessage(message);
      setFeedbackMessage(null);
    },
    [onUnauthorized],
  );

  const createCategoryMutation = useMutation({
    mutationFn: (payload: NafCategoryPayload) => nafApi.createCategory(payload),
    onSuccess: (category) => {
      setFeedbackMessage(`Catégorie ${category.name} créée.`);
      setErrorMessage(null);
      invalidateCategories();
      setCategoryModalState(null);
    },
    onError: handleMutationError,
  });

  const updateCategoryMutation = useMutation({
    mutationFn: ({ categoryId, payload }: { categoryId: string; payload: NafCategoryPayload }) =>
      nafApi.updateCategory(categoryId, payload),
    onSuccess: (category) => {
      setFeedbackMessage(`Catégorie ${category.name} mise à jour.`);
      setErrorMessage(null);
      invalidateCategories();
      setCategoryModalState(null);
    },
    onError: handleMutationError,
  });

  const deleteCategoryMutation = useMutation<void, unknown, { categoryId: string; categoryName: string }>({
    mutationFn: ({ categoryId }) => nafApi.deleteCategory(categoryId),
    onMutate: ({ categoryId }) => setDeletingCategoryId(categoryId),
    onSuccess: (_, { categoryName }) => {
      setFeedbackMessage(`Catégorie ${categoryName} supprimée.`);
      setErrorMessage(null);
      invalidateCategories();
    },
    onError: handleMutationError,
    onSettled: () => setDeletingCategoryId(null),
  });

  const createSubCategoryMutation = useMutation({
    mutationFn: (payload: NafSubCategoryCreatePayload) => nafApi.createSubCategory(payload),
    onSuccess: (subcategory) => {
      setFeedbackMessage(`Sous-catégorie ${subcategory.name} créée.`);
      setErrorMessage(null);
      invalidateCategories();
      setSubCategoryModalState(null);
    },
    onError: handleMutationError,
  });

  const updateSubCategoryMutation = useMutation({
    mutationFn: ({ subcategoryId, payload }: { subcategoryId: string; payload: NafSubCategoryUpdatePayload }) =>
      nafApi.updateSubCategory(subcategoryId, payload),
    onSuccess: (subcategory) => {
      setFeedbackMessage(`Sous-catégorie ${subcategory.name} mise à jour.`);
      setErrorMessage(null);
      invalidateCategories();
      setSubCategoryModalState(null);
    },
    onError: handleMutationError,
  });

  const deleteSubCategoryMutation = useMutation<
    void,
    unknown,
    { subcategoryId: string; subcategoryName: string }
  >({
    mutationFn: ({ subcategoryId }) => nafApi.deleteSubCategory(subcategoryId),
    onMutate: ({ subcategoryId }) => setDeletingSubCategoryId(subcategoryId),
    onSuccess: (_, { subcategoryName }) => {
      setFeedbackMessage(`Sous-catégorie ${subcategoryName} supprimée.`);
      setErrorMessage(null);
      invalidateCategories();
    },
    onError: handleMutationError,
    onSettled: () => setDeletingSubCategoryId(null),
  });

  const isCategoryModalProcessing = useMemo(
    () => createCategoryMutation.isPending || updateCategoryMutation.isPending,
    [createCategoryMutation.isPending, updateCategoryMutation.isPending],
  );

  const isSubCategoryModalProcessing = useMemo(
    () => createSubCategoryMutation.isPending || updateSubCategoryMutation.isPending,
    [createSubCategoryMutation.isPending, updateSubCategoryMutation.isPending],
  );

  const handleOpenCategoryModal = useCallback((mode: "create" | "edit", category: NafCategory | null = null) => {
    setFeedbackMessage(null);
    setErrorMessage(null);
    setCategoryModalState({ mode, category });
  }, []);

  const handleOpenSubCategoryModal = useCallback(
    (mode: "create" | "edit", options?: { subcategory?: NafSubCategory; categoryId?: string }) => {
      setFeedbackMessage(null);
      setErrorMessage(null);
      if (mode === "create") {
        setSubCategoryModalState({ mode, subcategory: null, initialCategoryId: options?.categoryId });
      } else if (options?.subcategory) {
        setSubCategoryModalState({ mode, subcategory: options.subcategory });
      }
    },
    [],
  );

  const handleSubmitCategory = useCallback(
    (payload: NafCategoryFormPayload) => {
      if (!ensureAuthenticated()) {
        return;
      }
      if (categoryModalState?.mode === "edit" && categoryModalState.category) {
        updateCategoryMutation.mutate({
          categoryId: categoryModalState.category.id,
          payload: { name: payload.name, description: payload.description, keywords: payload.keywords },
        });
      } else {
        createCategoryMutation.mutate({ name: payload.name, description: payload.description, keywords: payload.keywords });
      }
    },
    [ensureAuthenticated, categoryModalState, updateCategoryMutation, createCategoryMutation],
  );

  const handleSubmitSubCategory = useCallback(
    (payload: NafSubCategoryFormPayload) => {
      if (!ensureAuthenticated()) {
        return;
      }
      const basePayload: NafSubCategoryCreatePayload = {
        categoryId: payload.categoryId,
        name: payload.name,
        description: payload.description ?? null,
        nafCode: payload.nafCode,
        priceEur: payload.priceEur,
        isActive: payload.isActive,
      };
      if (basePayload.priceEur === undefined) {
        delete basePayload.priceEur;
      }
      if (subcategoryModalState?.mode === "edit" && subcategoryModalState.subcategory) {
        const updatePayload: NafSubCategoryUpdatePayload = {
          categoryId: basePayload.categoryId,
          name: basePayload.name,
          description: basePayload.description,
          nafCode: basePayload.nafCode,
          priceEur: basePayload.priceEur,
          isActive: basePayload.isActive,
        };
        updateSubCategoryMutation.mutate({ subcategoryId: subcategoryModalState.subcategory.id, payload: updatePayload });
      } else {
        createSubCategoryMutation.mutate(basePayload);
      }
    },
    [ensureAuthenticated, subcategoryModalState, updateSubCategoryMutation, createSubCategoryMutation],
  );

  const handleDeleteCategory = useCallback(
    (category: NafCategory) => {
      if (!ensureAuthenticated()) {
        return;
      }
      deleteCategoryMutation.mutate({ categoryId: category.id, categoryName: category.name });
    },
    [ensureAuthenticated, deleteCategoryMutation],
  );

  const handleDeleteSubCategory = useCallback(
    (subcategory: NafSubCategory) => {
      if (!ensureAuthenticated()) {
        return;
      }
      deleteSubCategoryMutation.mutate({
        subcategoryId: subcategory.id,
        subcategoryName: subcategory.name,
      });
    },
    [ensureAuthenticated, deleteSubCategoryMutation],
  );

  return (
    <>
      <section className="dashboard-section">
        <div className="section-header">
          <div>
            <h2>Config NAF</h2>
            <p className="muted">Pilotez les catégories surveillées et leurs souscriptions.</p>
          </div>
        </div>
        <div className="section-grid">
          <NafCategoriesSection
            categories={categories}
            isLoading={isLoading}
            isRefreshing={isRefreshing}
            error={error}
            feedbackMessage={feedbackMessage}
            errorMessage={errorMessage}
            onRefresh={onRefresh}
            regions={regions}
            onCreateCategory={() => handleOpenCategoryModal("create")}
            onEditCategory={(category) => handleOpenCategoryModal("edit", category)}
            onDeleteCategory={handleDeleteCategory}
            onCreateSubCategory={(categoryId) => handleOpenSubCategoryModal("create", { categoryId })}
            onEditSubCategory={(subcategory) => handleOpenSubCategoryModal("edit", { subcategory })}
            onDeleteSubCategory={handleDeleteSubCategory}
            deletingCategoryId={deletingCategoryId}
            deletingSubCategoryId={deletingSubCategoryId}
          />
        </div>
      </section>

      <NafCategoryModal
        isOpen={Boolean(categoryModalState)}
        mode={categoryModalState?.mode ?? "create"}
        category={categoryModalState?.category ?? null}
        onSubmit={handleSubmitCategory}
        onCancel={() => setCategoryModalState(null)}
        isProcessing={isCategoryModalProcessing}
      />

      <NafSubCategoryModal
        isOpen={Boolean(subcategoryModalState)}
        mode={subcategoryModalState?.mode ?? "create"}
        categories={categories ?? []}
        subcategory={
          subcategoryModalState && subcategoryModalState.mode === "edit"
            ? subcategoryModalState.subcategory
            : null
        }
        initialCategoryId={
          subcategoryModalState && subcategoryModalState.mode === "create"
            ? subcategoryModalState.initialCategoryId
            : undefined
        }
        onSubmit={handleSubmitSubCategory}
        onCancel={() => setSubCategoryModalState(null)}
        isProcessing={isSubCategoryModalProcessing}
      />
    </>
  );
};
