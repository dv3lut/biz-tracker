import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, clientsApi, nafApi, regionsApi, type ClientCreatePayload, type ClientUpdatePayload } from "../../api";
import type { Client, NafCategory, Region } from "../../types";
import { ClientsView } from "../../components/views/ClientsView";
import { ClientModal, type ClientFormSubmitPayload } from "../../components/ClientModal";
import { useRefreshIndicator } from "../../hooks/useRefreshIndicator";

const buildErrorMessage = (error: unknown): string => {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "Une erreur est survenue.";
};

type ClientModalState = { mode: "create" | "edit"; client: Client | null } | null;

type Props = {
  onUnauthorized: () => void;
};

export const ClientsSection = ({ onUnauthorized }: Props) => {
  const queryClient = useQueryClient();
  const [modalState, setModalState] = useState<ClientModalState>(null);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const clientsQuery = useQuery<Client[]>({
    queryKey: ["clients"],
    queryFn: () => clientsApi.list(),
  });

  const nafCategoriesQuery = useQuery<NafCategory[]>({
    queryKey: ["naf-categories"],
    queryFn: () => nafApi.listCategories(),
  });

  const regionsQuery = useQuery<Region[]>({
    queryKey: ["regions"],
    queryFn: () => regionsApi.list(),
  });

  const clientsIsRefreshing = useRefreshIndicator(
    clientsQuery.isFetching && !clientsQuery.isLoading,
    { delay: 300, minVisible: 250 },
  );

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

  const showError = useCallback(
    (error: unknown) => {
      if (error instanceof ApiError && error.status === 403) {
        onUnauthorized();
        return;
      }
      setErrorMessage(buildErrorMessage(error));
      setFeedbackMessage(null);
    },
    [onUnauthorized],
  );

  const invalidateClients = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["clients"] });
  }, [queryClient]);

  const createClientMutation = useMutation({
    mutationFn: (payload: ClientCreatePayload) => clientsApi.create(payload),
    onSuccess: (client) => {
      setFeedbackMessage(`Client ${client.name} créé.`);
      setErrorMessage(null);
      invalidateClients();
      setModalState(null);
    },
    onError: showError,
  });

  const updateClientMutation = useMutation({
    mutationFn: ({ clientId, payload }: { clientId: string; payload: ClientUpdatePayload }) =>
      clientsApi.update(clientId, payload),
    onSuccess: (client) => {
      setFeedbackMessage(`Client ${client.name} mis à jour.`);
      setErrorMessage(null);
      invalidateClients();
      setModalState(null);
    },
    onError: showError,
  });

  const deleteClientMutation = useMutation<void, unknown, { clientId: string; clientName: string }>({
    mutationFn: ({ clientId }) => clientsApi.delete(clientId),
    onSuccess: (_, variables) => {
      setFeedbackMessage(`Client ${variables.clientName} supprimé.`);
      setErrorMessage(null);
      invalidateClients();
    },
    onError: showError,
  });

  const deletingClientId = useMemo(() => {
    if (!deleteClientMutation.isPending) {
      return null;
    }
    return deleteClientMutation.variables?.clientId ?? null;
  }, [deleteClientMutation.isPending, deleteClientMutation.variables]);

  const openCreateModal = useCallback(() => {
    setFeedbackMessage(null);
    setErrorMessage(null);
    setModalState({ mode: "create", client: null });
  }, []);

  const openEditModal = useCallback((client: Client) => {
    setFeedbackMessage(null);
    setErrorMessage(null);
    setModalState({ mode: "edit", client });
  }, []);

  const closeModal = useCallback(() => {
    setModalState(null);
  }, []);

  const handleSubmitModal = useCallback(
    (formPayload: ClientFormSubmitPayload) => {
      if (!modalState) {
        return;
      }
      const payload: ClientCreatePayload = {
        name: formPayload.name,
        startDate: formPayload.startDate,
        endDate: formPayload.endDate,
        listingStatuses: formPayload.listingStatuses,
        recipients: formPayload.recipients,
        subscriptionIds: formPayload.subscriptionIds,
        regionIds: formPayload.regionIds,
      };
      if (modalState.mode === "edit" && modalState.client) {
        updateClientMutation.mutate({ clientId: modalState.client.id, payload });
      } else {
        createClientMutation.mutate(payload);
      }
    },
    [modalState, createClientMutation, updateClientMutation],
  );

  const handleDeleteClient = useCallback(
    (client: Client) => {
      deleteClientMutation.mutate({ clientId: client.id, clientName: client.name });
    },
    [deleteClientMutation],
  );

  const isModalProcessing = createClientMutation.isPending || updateClientMutation.isPending;
  const clientsError = clientsQuery.error instanceof Error ? clientsQuery.error : null;

  return (
    <>
      <ClientsView
        clients={clientsQuery.data}
        nafCategories={nafCategoriesQuery.data}
        isLoading={clientsQuery.isLoading}
        isRefreshing={clientsIsRefreshing}
        error={clientsError}
        feedbackMessage={feedbackMessage}
        errorMessage={errorMessage}
        onRefresh={() => clientsQuery.refetch()}
        onCreateClient={openCreateModal}
        onEditClient={openEditModal}
        onDeleteClient={handleDeleteClient}
        deletingClientId={deletingClientId}
      />

      <ClientModal
        isOpen={Boolean(modalState)}
        mode={modalState?.mode ?? "create"}
        client={modalState?.client ?? null}
        nafCategories={nafCategoriesQuery.data}
        isLoadingNafCategories={nafCategoriesQuery.isLoading}
        regions={regionsQuery.data}
        isLoadingRegions={regionsQuery.isLoading}
        onSubmit={handleSubmitModal}
        onCancel={closeModal}
        isProcessing={isModalProcessing}
      />
    </>
  );
};
