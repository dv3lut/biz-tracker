import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";


type PlanKey = "starter" | "business";

type PublicNafCategory = {
  id: string;
  name: string;
  description: string | null;
  activeSubcategoryCount: number;
};

type SubscriptionInfo = {
  planKey: string | null;
  status: string | null;
  currentPeriodEnd: string | null;
  cancelAt: string | null;
  contactName: string | null;
  contactEmail: string | null;
  categoryIds: string[];
  categories: { id: string; name: string }[];
};

const PLAN_CATEGORY_LIMITS: Record<PlanKey, number> = {
  starter: 1,
  business: 3,
};

const Upgrade = () => {
  const apiBaseUrl = (import.meta.env.VITE_APP_API_BASE_URL ?? "").replace(/\/$/, "");
  const accessToken = useMemo(() => {
    const token = new URLSearchParams(window.location.search).get("token");
    return token?.trim() ?? "";
  }, []);
  const [categories, setCategories] = useState<PublicNafCategory[]>([]);
  const [isLoadingCategories, setIsLoadingCategories] = useState(false);
  const [categoriesError, setCategoriesError] = useState<string | null>(null);

  const [subscriptionInfo, setSubscriptionInfo] = useState<SubscriptionInfo | null>(null);
  const [subscriptionError, setSubscriptionError] = useState<string | null>(null);

  const [plan, setPlan] = useState<PlanKey>("starter");
  const [categoryIds, setCategoryIds] = useState<string[]>([]);
  const [isCategoryDropdownOpen, setIsCategoryDropdownOpen] = useState(false);
  const categoryDropdownRef = useRef<HTMLDivElement | null>(null);
  const [updateError, setUpdateError] = useState<string | null>(null);
  const [updateSuccess, setUpdateSuccess] = useState<string | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [updateAction, setUpdateAction] = useState<"upgrade" | "downgrade" | "update" | null>(null);
  const [updateEffectiveAt, setUpdateEffectiveAt] = useState<string | null>(null);
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const [previewAmount, setPreviewAmount] = useState<number | null>(null);
  const [previewCurrency, setPreviewCurrency] = useState<string | null>(null);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [isPreviewTrial, setIsPreviewTrial] = useState(false);
  const [hasPaymentMethod, setHasPaymentMethod] = useState(true);

  const [portalError, setPortalError] = useState<string | null>(null);
  const [isPortalLoading, setIsPortalLoading] = useState(false);
  const [hasInitializedCategories, setHasInitializedCategories] = useState(false);
  const [hasInitializedPlan, setHasInitializedPlan] = useState(false);

  useEffect(() => {
    if (!accessToken) return undefined;
    let isMounted = true;
    const fetchCategories = async () => {
      setIsLoadingCategories(true);
      setCategoriesError(null);
      try {
        const response = await fetch(`${apiBaseUrl}/public/naf-categories`);
        if (!response.ok) {
          throw new Error("Impossible de charger les catégories.");
        }
        const data = (await response.json()) as Array<{
          id: string;
          name: string;
          description: string | null;
          active_subcategory_count: number;
        }>;
        if (!isMounted) return;
        setCategories(
          data.map((entry) => ({
            id: entry.id,
            name: entry.name,
            description: entry.description,
            activeSubcategoryCount: entry.active_subcategory_count,
          }))
        );
      } catch (error) {
        if (!isMounted) return;
        setCategoriesError(error instanceof Error ? error.message : "Erreur inattendue.");
      } finally {
        if (isMounted) setIsLoadingCategories(false);
      }
    };

    fetchCategories();
    return () => {
      isMounted = false;
    };
  }, [accessToken, apiBaseUrl]);

  const fetchSubscriptionInfo = useCallback(async () => {
    if (!accessToken) return;
    setSubscriptionError(null);
    const response = await fetch(`${apiBaseUrl}/public/stripe/subscription-info`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ access_token: accessToken }),
    });
    if (!response.ok) {
      throw new Error("Impossible de récupérer votre abonnement.");
    }
    const payload = (await response.json()) as {
      plan_key?: string | null;
      status?: string | null;
      current_period_end?: string | null;
      cancel_at?: string | null;
      contact_name?: string | null;
      contact_email?: string | null;
      categories?: Array<{ id: string; name: string }>;
    };
    const categoriesPayload = payload.categories ?? [];
    setSubscriptionInfo({
      planKey: payload.plan_key ?? null,
      status: payload.status ?? null,
      currentPeriodEnd: payload.current_period_end ?? null,
      cancelAt: payload.cancel_at ?? null,
      contactName: payload.contact_name ?? null,
      contactEmail: payload.contact_email ?? null,
      categoryIds: categoriesPayload.map((category) => category.id),
      categories: categoriesPayload,
    });
    if (!hasInitializedPlan && payload.plan_key) {
      setPlan(payload.plan_key as PlanKey);
      setHasInitializedPlan(true);
    }
    if (!hasInitializedCategories && categoriesPayload.length) {
      setCategoryIds(categoriesPayload.map((category) => category.id));
      setHasInitializedCategories(true);
    }
  }, [accessToken, apiBaseUrl, hasInitializedCategories, hasInitializedPlan]);

  useEffect(() => {
    if (!accessToken) return undefined;
    let isMounted = true;
    const runFetch = async () => {
      try {
        await fetchSubscriptionInfo();
      } catch (error) {
        if (!isMounted) return;
        setSubscriptionError(error instanceof Error ? error.message : "Erreur inattendue.");
      }
    };
    runFetch();
    return () => {
      isMounted = false;
    };
  }, [accessToken, fetchSubscriptionInfo]);

  useEffect(() => {
    if (!isCategoryDropdownOpen) return;
    const handleClickOutside = (event: MouseEvent) => {
      if (!categoryDropdownRef.current) return;
      if (!categoryDropdownRef.current.contains(event.target as Node)) {
        setIsCategoryDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isCategoryDropdownOpen]);

  const requiredCount = useMemo(() => PLAN_CATEGORY_LIMITS[plan], [plan]);

  const selectedCategoryNames = useMemo(() => {
    if (!categoryIds.length) return [];
    const categoryMap = new Map(categories.map((category) => [category.id, category.name]));
    return categoryIds
      .map((id) => categoryMap.get(id))
      .filter((name): name is string => Boolean(name));
  }, [categories, categoryIds]);

  const formatAmount = useCallback((amount: number | null, currency: string | null) => {
    if (amount === null) return null;
    try {
      return new Intl.NumberFormat("fr-FR", {
        style: "currency",
        currency: (currency ?? "EUR").toUpperCase(),
      }).format(amount / 100);
    } catch {
      return `${(amount / 100).toFixed(2)} €`;
    }
  }, []);

  const handleToggleCategory = (categoryId: string) => {
    setCategoryIds((current) => {
      if (current.includes(categoryId)) {
        return current.filter((id) => id !== categoryId);
      }
      if (current.length >= requiredCount) {
        return current;
      }
      const next = [...current, categoryId];
      if (next.length >= requiredCount) {
        setIsCategoryDropdownOpen(false);
      }
      return next;
    });
  };

  const handlePortalSubmit = async () => {
    if (!accessToken) {
      setPortalError("Lien sécurisé manquant ou invalide.");
      return;
    }

    setPortalError(null);
    setIsPortalLoading(true);

    try {
      const response = await fetch(`${apiBaseUrl}/public/stripe/portal-session`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ access_token: accessToken }),
      });

      if (!response.ok) {
        let detail = "Impossible d'ouvrir le portail Stripe.";
        try {
          const payload = await response.json();
          if (typeof payload?.detail === "string") {
            detail = payload.detail;
          }
        } catch {
          // ignore
        }
        setPortalError(detail);
        return;
      }

      const payload = (await response.json()) as { url?: string };
      if (payload.url) {
        window.location.href = payload.url;
      } else {
        setPortalError("Lien Stripe non disponible.");
      }
    } finally {
      setIsPortalLoading(false);
    }
  };

  const runUpdate = async () => {
    setUpdateError(null);
    setUpdateSuccess(null);
    setUpdateAction(null);
    setUpdateEffectiveAt(null);
    setIsUpdating(true);

    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 30000);

    try {
      const response = await fetch(`${apiBaseUrl}/public/stripe/subscription-update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          plan_key: plan,
          category_ids: categoryIds,
          access_token: accessToken,
        }),
      });

      if (!response.ok) {
        let detail = "Impossible de mettre à jour l'abonnement.";
        try {
          const payload = await response.json();
          if (typeof payload?.detail === "string") {
            detail = payload.detail;
          }
        } catch {
          // ignore
        }
        setUpdateError(detail);
        return;
      }

      const payload = (await response.json()) as {
        payment_url: string | null;
        action: "upgrade" | "downgrade" | "update";
        effective_at: string | null;
      };
      setUpdateAction(payload.action);
      setUpdateEffectiveAt(payload.effective_at);
      // Si payment_url est présent, rediriger vers Stripe pour payer
      if (payload.payment_url) {
        window.location.href = payload.payment_url;
        return;
      }
      if (payload.action === "downgrade") {
        const formattedDate = payload.effective_at
          ? new Date(payload.effective_at).toLocaleDateString("fr-FR")
          : "la prochaine période";
        setUpdateSuccess(
          `Votre downgrade prendra effet le ${formattedDate}. Vous conservez votre plan actuel jusqu'à cette date.`
        );
      } else if (payload.action === "upgrade") {
        const isTrialing = subscriptionInfo?.status === "trialing";
        setUpdateSuccess(
          isTrialing
            ? "Votre upgrade est effectif immédiatement."
            : "Votre upgrade est effectif immédiatement. La différence de prix a été débitée au prorata du mois en cours."
        );
      } else {
        setUpdateSuccess("Vos catégories ont été mises à jour.");
      }
      setHasInitializedCategories(false);
      setHasInitializedPlan(false);
      try {
        await fetchSubscriptionInfo();
      } catch (error) {
        setSubscriptionError(error instanceof Error ? error.message : "Erreur inattendue.");
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        setUpdateError("La demande prend trop de temps. Merci de réessayer.");
      } else {
        setUpdateError("Impossible de contacter l'API. Merci de réessayer.");
      }
    } finally {
      window.clearTimeout(timeoutId);
      setIsUpdating(false);
    }
  };

  const handleUpdateSubmit = async () => {
    if (categoryIds.length !== requiredCount) {
      setUpdateError(`Sélectionnez exactement ${requiredCount} catégorie(s).`);
      return;
    }
    if (!accessToken) {
      setUpdateError("Lien sécurisé manquant ou invalide.");
      return;
    }

    if (isUpgrade && !isSamePlan) {
      setIsPreviewLoading(true);
      setUpdateError(null);
      try {
        const response = await fetch(`${apiBaseUrl}/public/stripe/subscription-update-preview`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            plan_key: plan,
            category_ids: categoryIds,
            access_token: accessToken,
          }),
        });
        if (!response.ok) {
          let detail = "Impossible de prévisualiser l'upgrade.";
          try {
            const payload = await response.json();
            if (typeof payload?.detail === "string") {
              detail = payload.detail;
            }
          } catch {
            // ignore
          }
          setUpdateError(detail);
          return;
        }
        const payload = (await response.json()) as {
          amount_due: number | null;
          currency: string | null;
          is_upgrade: boolean;
          is_trial: boolean;
          has_payment_method: boolean;
        };
        setPreviewAmount(payload.amount_due ?? null);
        setPreviewCurrency(payload.currency ?? null);
        setIsPreviewTrial(payload.is_trial);
        setHasPaymentMethod(payload.has_payment_method);
        setIsConfirmOpen(true);
      } catch (error) {
        setUpdateError(error instanceof Error ? error.message : "Erreur inattendue.");
      } finally {
        setIsPreviewLoading(false);
      }
      return;
    }

    await runUpdate();
  };

  const handleConfirmUpgrade = async () => {
    setIsConfirmOpen(false);
    await runUpdate();
  };

  const currentPlanKey = subscriptionInfo?.planKey ?? null;
  const isSamePlan = currentPlanKey === plan;
  const planRank: Record<PlanKey, number> = { starter: 0, business: 1 };
  const isUpgrade = currentPlanKey ? planRank[plan] > planRank[currentPlanKey as PlanKey] : true;
  const selectedCategoryLabel = requiredCount > 1 ? "mes nouvelles catégories" : "ma nouvelle catégorie";
  const updateLabel = isSamePlan
    ? `Mettre à jour ${selectedCategoryLabel}`
    : isUpgrade
      ? "Upgrader mon plan"
      : "Downgrader mon plan";
  const planLabel = currentPlanKey ? currentPlanKey.charAt(0).toUpperCase() + currentPlanKey.slice(1) : "-";
  const statusLabel = (() => {
    const status = subscriptionInfo?.status ?? "-";
    const mapping: Record<string, string> = {
      active: "Actif",
      trialing: "Période d'essai gratuite",
      past_due: "Paiement en retard",
      canceled: "Résilié",
      incomplete: "Incomplet",
      incomplete_expired: "Incomplet expiré",
      unpaid: "Impayé",
      paused: "En pause",
    };
    if (status === "-") return status;
    return mapping[status] ?? status.charAt(0).toUpperCase() + status.slice(1);
  })();

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-indigo-50 text-foreground">
      <header className="border-b bg-white/70 backdrop-blur">
        <div className="container mx-auto px-4 py-6 flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">Business Tracker</p>
            <h1 className="text-2xl font-bold">Gestion de votre abonnement</h1>
          </div>
          <Button variant="outline" asChild>
            <Link to="/">Retour à l'accueil</Link>
          </Button>
        </div>
      </header>

      <main className="container mx-auto px-4 py-12">
        {accessToken ? (
          <div className="grid gap-6 lg:grid-cols-2">
            <Card className="p-6 bg-white/95 shadow-lg border border-sky-100">
              <div className="space-y-2">
                <h2 className="text-lg font-semibold text-sky-900">Votre abonnement actuel</h2>
                {subscriptionError ? (
                  <p className="text-sm text-destructive">{subscriptionError}</p>
                ) : subscriptionInfo ? (
                  <div className="grid gap-2 text-sm text-muted-foreground">
                    {subscriptionInfo.contactName ? (
                      <p className="text-base font-semibold text-foreground">
                        Bonjour {subscriptionInfo.contactName}
                      </p>
                    ) : null}
                    {subscriptionInfo.contactEmail ? (
                      <p>
                        <span className="font-medium text-foreground">Email :</span>{" "}
                        {subscriptionInfo.contactEmail}
                      </p>
                    ) : null}
                    <p>
                      <span className="font-medium text-foreground">Plan :</span>{" "}
                      <span className="text-sky-700 font-semibold">{planLabel}</span>
                    </p>
                    <p>
                      <span className="font-medium text-foreground">Statut :</span>{" "}
                      <span className="text-emerald-700 font-semibold">{statusLabel}</span>
                    </p>
                    <p>
                      <span className="font-medium text-foreground">Catégories :</span>{" "}
                      {subscriptionInfo.categories.length
                        ? subscriptionInfo.categories.map((category) => category.name).join(", ")
                        : "-"}
                    </p>
                    <p>
                      <span className="font-medium text-foreground">Prochaine échéance :</span>{" "}
                      {subscriptionInfo.currentPeriodEnd
                        ? new Date(subscriptionInfo.currentPeriodEnd).toLocaleDateString("fr-FR")
                        : "-"}
                    </p>
                    <p>
                      <span className="font-medium text-foreground">Résiliation prévue :</span>{" "}
                      {subscriptionInfo.cancelAt
                        ? new Date(subscriptionInfo.cancelAt).toLocaleDateString("fr-FR")
                        : "-"}
                    </p>
                    <div className="pt-2 text-xs text-muted-foreground">
                      Le portail Stripe permet de consulter vos factures, gérer vos moyens de paiement et résilier
                      l'abonnement.
                      <div className="mt-1">La résiliation doit être réalisée depuis le portail Stripe.</div>
                    </div>
                    <div className="pt-3">
                      <Button variant="default" onClick={handlePortalSubmit} disabled={isPortalLoading}>
                        {isPortalLoading ? "Ouverture…" : "Accéder au portail Stripe"}
                      </Button>
                      {portalError ? (
                        <p className="text-sm text-destructive mt-2">{portalError}</p>
                      ) : null}
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">Chargement de l'abonnement…</p>
                )}
              </div>
            </Card>

            <section id="upgrade">
              <Card className="p-8 space-y-6 bg-white/95 shadow-lg border border-indigo-100">
                <div>
                  <h2 className="text-xl font-semibold text-indigo-900">Changer de plan</h2>
                  <p className="text-sm text-muted-foreground">
                    Vous pouvez changer de plan (upgrade/downgrade) ou ajuster vos catégories.
                    En cas d'upgrade, la différence vous sera facturée au prorata du mois en cours.
                  </p>
                  <p className="text-xs text-muted-foreground mt-2">
                    Pour résilier l'abonnement, utilisez le portail Stripe.
                  </p>
                </div>

                <div className="grid gap-6">
                  <div className="max-w-sm">
                    <Label htmlFor="plan">Plan</Label>
                    <select
                      id="plan"
                      className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                      value={plan}
                      onChange={(event) => {
                        const value = event.target.value as PlanKey;
                        setPlan(value);
                        setCategoryIds([]);
                        setIsCategoryDropdownOpen(false);
                      }}
                    >
                      <option value="starter">Starter (1 catégorie)</option>
                      <option value="business">Business (3 catégories)</option>
                    </select>
                  </div>

                  {isLoadingCategories ? (
                    <p className="text-sm text-muted-foreground">Chargement des catégories…</p>
                  ) : categoriesError ? (
                    <p className="text-sm text-destructive">{categoriesError}</p>
                  ) : (
                    <div className="grid gap-2">
                      <Label>Catégories</Label>
                      <div className="relative" ref={categoryDropdownRef}>
                        <button
                          type="button"
                          className="flex w-full items-center justify-between gap-3 rounded-md border px-3 py-2 text-left text-sm"
                          onClick={() => setIsCategoryDropdownOpen((current) => !current)}
                        >
                          <span className="flex-1 truncate">
                            {selectedCategoryNames.length
                              ? selectedCategoryNames.join(", ")
                              : `Sélectionner ${requiredCount} catégorie(s)`}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {categoryIds.length}/{requiredCount}
                          </span>
                        </button>
                        {isCategoryDropdownOpen ? (
                          <div className="absolute z-20 mt-2 w-full rounded-md border bg-background shadow-lg">
                            <div className="max-h-64 space-y-2 overflow-y-auto p-2">
                              {categories.map((category) => {
                                const isSelected = categoryIds.includes(category.id);
                                const isDisabled =
                                  !isSelected && categoryIds.length >= requiredCount;
                                return (
                                  <label
                                    key={category.id}
                                    className={`flex items-start gap-3 rounded-md border p-3 ${
                                      isDisabled ? "opacity-60" : "cursor-pointer"
                                    }`}
                                  >
                                    <input
                                      type="checkbox"
                                      className="mt-1"
                                      checked={isSelected}
                                      disabled={isDisabled}
                                      onChange={() => handleToggleCategory(category.id)}
                                    />
                                    <div>
                                      <p className="font-medium">{category.name}</p>
                                      {category.description ? (
                                        <p className="text-sm text-muted-foreground">
                                          {category.description}
                                        </p>
                                      ) : null}
                                    </div>
                                  </label>
                                );
                              })}
                            </div>
                          </div>
                        ) : null}
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {categoryIds.length}/{requiredCount} sélectionnée(s)
                      </p>
                    </div>
                  )}

                  {updateError ? <p className="text-sm text-destructive">{updateError}</p> : null}
                  {updateSuccess ? <p className="text-sm text-emerald-600">{updateSuccess}</p> : null}

                  <Button onClick={handleUpdateSubmit} disabled={isUpdating || isPreviewLoading}>
                    {isUpdating
                      ? "Mise à jour…"
                      : isPreviewLoading
                        ? "Calcul du prorata…"
                        : updateLabel}
                  </Button>
                </div>
              </Card>
            </section>
          </div>
        ) : (
          <section id="upgrade">
            <Card className="p-8 space-y-6 bg-white/95 shadow-lg border border-indigo-100">
              <div className="space-y-3">
                <h2 className="text-xl font-semibold text-indigo-900">Accès sécurisé requis</h2>
                <p className="text-sm text-muted-foreground">
                  Pour modifier votre plan, utilisez le lien sécurisé reçu par email après votre premier paiement.
                </p>
                <Button variant="outline" asChild>
                  <Link to="/">Retour à l'accueil</Link>
                </Button>
              </div>
            </Card>
          </section>
        )}
      </main>

      {isConfirmOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-slate-900/60"
            onClick={() => setIsConfirmOpen(false)}
          />
          <Card className="relative z-10 w-full max-w-lg p-6 shadow-xl">
            <div className="space-y-3">
              <h3 className="text-lg font-semibold text-foreground">Confirmer l'upgrade</h3>
              {hasPaymentMethod ? (
                <>
                  <p className="text-sm text-muted-foreground">
                    Vous allez être débité du prorata correspondant à la différence du mois en cours.
                  </p>
                  {isPreviewTrial ? (
                    <p className="text-sm text-emerald-600">
                      Aucun débit pendant la période d'essai.
                    </p>
                  ) : (
                    <p className="text-sm text-foreground">
                      Montant à débiter :{" "}
                      <span className="font-semibold">
                        {formatAmount(previewAmount, previewCurrency) ?? "Estimation indisponible"}
                      </span>
                    </p>
                  )}
                </>
              ) : (
                <>
                  <p className="text-sm text-muted-foreground">
                    Vous n'avez pas encore de moyen de paiement enregistré.
                  </p>
                  <p className="text-sm text-foreground">
                    Montant à payer :{" "}
                    <span className="font-semibold">
                      {formatAmount(previewAmount, previewCurrency) ?? "Estimation indisponible"}
                    </span>
                  </p>
                  <p className="text-sm text-amber-600">
                    Vous allez être redirigé vers Stripe pour effectuer le paiement.
                  </p>
                </>
              )}
            </div>
            <div className="mt-6 flex justify-end gap-3">
              <Button variant="outline" onClick={() => setIsConfirmOpen(false)} disabled={isUpdating}>
                Annuler
              </Button>
              <Button onClick={handleConfirmUpgrade} disabled={isUpdating}>
                {isUpdating 
                  ? "Traitement en cours…" 
                  : hasPaymentMethod 
                    ? "Confirmer l'upgrade" 
                    : "Payer maintenant"}
              </Button>
            </div>
          </Card>
        </div>
      ) : null}

    </div>
  );
};

export default Upgrade;
