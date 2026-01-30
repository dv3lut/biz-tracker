import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";


type PlanKey = "starter" | "business";

type PublicNafCategory = {
  id: string;
  name: string;
  description: string | null;
  activeSubcategoryCount: number;
};

const PLAN_CATEGORY_LIMITS: Record<PlanKey, number> = {
  starter: 1,
  business: 3,
};

const Upgrade = () => {
  const apiBaseUrl = (import.meta.env.VITE_APP_API_BASE_URL ?? "").replace(/\/$/, "");
  const [categories, setCategories] = useState<PublicNafCategory[]>([]);
  const [isLoadingCategories, setIsLoadingCategories] = useState(false);
  const [categoriesError, setCategoriesError] = useState<string | null>(null);

  const [plan, setPlan] = useState<PlanKey>("starter");
  const [categoryIds, setCategoryIds] = useState<string[]>([]);
  const [isCategoryDropdownOpen, setIsCategoryDropdownOpen] = useState(false);
  const categoryDropdownRef = useRef<HTMLDivElement | null>(null);
  const [email, setEmail] = useState("");
  const [updateError, setUpdateError] = useState<string | null>(null);
  const [updateSuccess, setUpdateSuccess] = useState<string | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [updateAction, setUpdateAction] = useState<"upgrade" | "downgrade" | null>(null);
  const [updateEffectiveAt, setUpdateEffectiveAt] = useState<string | null>(null);

  const [isPortalOpen, setIsPortalOpen] = useState(false);
  const [portalEmail, setPortalEmail] = useState("");
  const [portalError, setPortalError] = useState<string | null>(null);
  const [portalSuccess, setPortalSuccess] = useState<string | null>(null);
  const [isPortalLoading, setIsPortalLoading] = useState(false);

  useEffect(() => {
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
  }, [apiBaseUrl]);

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
    if (!portalEmail.trim()) {
      setPortalError("Merci de renseigner votre email.");
      return;
    }

    setPortalError(null);
    setPortalSuccess(null);
    setIsPortalLoading(true);

    try {
      const response = await fetch(`${apiBaseUrl}/public/stripe/portal`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email: portalEmail.trim() }),
      });

      if (!response.ok) {
        let detail = "Impossible d'envoyer le lien.";
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

      const payload = (await response.json()) as { sent?: boolean };
      if (payload.sent) {
        setPortalSuccess("Si l'adresse est reconnue, un email vient d'être envoyé.");
      } else {
        setPortalError("Envoi non confirmé.");
      }
    } finally {
      setIsPortalLoading(false);
    }
  };

  const handleUpdateSubmit = async () => {
    if (categoryIds.length !== requiredCount) {
      setUpdateError(`Sélectionnez exactement ${requiredCount} catégorie(s).`);
      return;
    }
    if (!email.trim()) {
      setUpdateError("Merci de renseigner votre email.");
      return;
    }

    setUpdateError(null);
    setUpdateSuccess(null);
    setUpdateAction(null);
    setUpdateEffectiveAt(null);
    setIsUpdating(true);

    try {
      const response = await fetch(`${apiBaseUrl}/public/stripe/subscription-update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plan_key: plan,
          category_ids: categoryIds,
          email: email.trim(),
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
        action: "upgrade" | "downgrade";
        effective_at: string | null;
      };
      if (payload.payment_url) {
        window.location.href = payload.payment_url;
      } else {
        setUpdateAction(payload.action);
        setUpdateEffectiveAt(payload.effective_at);
        if (payload.action === "downgrade") {
          const formattedDate = payload.effective_at
            ? new Date(payload.effective_at).toLocaleDateString("fr-FR")
            : "la prochaine période";
          setUpdateSuccess(
            `Votre downgrade prendra effet le ${formattedDate}. Vous conservez votre plan actuel jusqu'à cette date.`
          );
        } else {
          setUpdateSuccess(
            "Votre upgrade est effectif immédiatement. La différence de prix sera facturée au prorata du mois en cours."
          );
        }
      }
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <div className="min-h-screen bg-muted/50 text-foreground">
      <header className="border-b bg-background/80 backdrop-blur">
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

      <main className="container mx-auto px-4 py-12 space-y-10">
        <Card className="p-6 text-sm text-muted-foreground">
          Le portail Stripe est accessible uniquement via le lien sécurisé envoyé par email.
          <div className="mt-4">
            <Button variant="outline" onClick={() => setIsPortalOpen(true)}>
              Portail client
            </Button>
          </div>
        </Card>

        <section id="upgrade">
          <Card className="p-8 space-y-6">
            <div>
              <h2 className="text-xl font-semibold">Changer de plan</h2>
              <p className="text-sm text-muted-foreground">
                Vous pouvez mettre à jour votre plan immédiatement. Stripe facturera la proratisation du mois en cours.
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

              <div className="max-w-md">
                <Label htmlFor="email">Email professionnel</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="vous@entreprise.fr"
                />
              </div>

              {updateError ? <p className="text-sm text-destructive">{updateError}</p> : null}
              {updateSuccess ? <p className="text-sm text-emerald-600">{updateSuccess}</p> : null}

              <Button onClick={handleUpdateSubmit} disabled={isUpdating}>
                {isUpdating ? "Mise à jour…" : "Mettre à jour mon plan"}
              </Button>
            </div>
          </Card>
        </section>
      </main>

      <Dialog open={isPortalOpen} onOpenChange={setIsPortalOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Accéder au portail client</DialogTitle>
            <DialogDescription>
              Nous envoyons un lien sécurisé par email pour gérer votre abonnement.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-3">
            <div>
              <Label htmlFor="portalEmail">Email professionnel</Label>
              <Input
                id="portalEmail"
                type="email"
                value={portalEmail}
                onChange={(event) => setPortalEmail(event.target.value)}
                placeholder="vous@entreprise.fr"
              />
            </div>
            {portalError ? <p className="text-sm text-destructive">{portalError}</p> : null}
            {portalSuccess ? <p className="text-sm text-emerald-600">{portalSuccess}</p> : null}
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setIsPortalOpen(false)}>
              Fermer
            </Button>
            <Button onClick={handlePortalSubmit} disabled={isPortalLoading}>
              {isPortalLoading ? "Envoi…" : "Envoyer le lien"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Upgrade;
