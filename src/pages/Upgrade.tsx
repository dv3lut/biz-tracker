import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";


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

  const [portalEmail, setPortalEmail] = useState("");
  const [portalError, setPortalError] = useState<string | null>(null);
  const [isPortalLoading, setIsPortalLoading] = useState(false);

  const [plan, setPlan] = useState<PlanKey>("starter");
  const [categoryIds, setCategoryIds] = useState<string[]>([]);
  const [email, setEmail] = useState("");
  const [updateError, setUpdateError] = useState<string | null>(null);
  const [updateSuccess, setUpdateSuccess] = useState<string | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);

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

  const requiredCount = useMemo(() => PLAN_CATEGORY_LIMITS[plan], [plan]);

  const handleToggleCategory = (categoryId: string) => {
    setCategoryIds((current) => {
      if (current.includes(categoryId)) {
        return current.filter((id) => id !== categoryId);
      }
      if (current.length >= requiredCount) {
        return current;
      }
      return [...current, categoryId];
    });
  };

  const handlePortalSubmit = async () => {
    if (!portalEmail.trim()) {
      setPortalError("Merci de renseigner votre email.");
      return;
    }

    setPortalError(null);
    setIsPortalLoading(true);

    try {
      const response = await fetch(`${apiBaseUrl}/public/stripe/portal`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: portalEmail.trim() }),
      });

      if (!response.ok) {
        let detail = "Impossible d'ouvrir le portail.";
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

      const payload = (await response.json()) as { url: string };
      if (payload.url) {
        window.location.href = payload.url;
      } else {
        setPortalError("URL Stripe invalide.");
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

      const payload = (await response.json()) as { payment_url: string | null };
      if (payload.payment_url) {
        window.location.href = payload.payment_url;
      } else {
        setUpdateSuccess("Abonnement mis à jour. Vous recevrez la facture Stripe si nécessaire.");
      }
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
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
        <section id="portal">
          <Card className="p-8 space-y-4">
            <div>
              <h2 className="text-xl font-semibold">Accéder au portail Stripe</h2>
              <p className="text-sm text-muted-foreground">
                Gérez votre abonnement (résiliation en fin de période, factures, moyens de paiement).
              </p>
            </div>
            <div className="grid gap-3 max-w-md">
              <Label htmlFor="portalEmail">Email professionnel</Label>
              <Input
                id="portalEmail"
                type="email"
                value={portalEmail}
                onChange={(event) => setPortalEmail(event.target.value)}
                placeholder="vous@entreprise.fr"
              />
              {portalError ? <p className="text-sm text-destructive">{portalError}</p> : null}
              <Button onClick={handlePortalSubmit} disabled={isPortalLoading}>
                {isPortalLoading ? "Ouverture…" : "Ouvrir le portail"}
              </Button>
            </div>
          </Card>
        </section>

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
                <div className="grid gap-3 md:grid-cols-2">
                  {categories.map((category) => {
                    const isSelected = categoryIds.includes(category.id);
                    const isDisabled = !isSelected && categoryIds.length >= requiredCount;
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
                            <p className="text-sm text-muted-foreground">{category.description}</p>
                          ) : null}
                        </div>
                      </label>
                    );
                  })}
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
    </div>
  );
};

export default Upgrade;
