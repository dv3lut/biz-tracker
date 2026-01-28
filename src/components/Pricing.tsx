import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Link } from "react-router-dom";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Check } from "lucide-react";

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

type Props = {
  trialPeriodDays?: number;
};

const Pricing = ({ trialPeriodDays = 14 }: Props) => {
  const apiBaseUrl = (import.meta.env.VITE_APP_API_BASE_URL ?? "").replace(/\/$/, "");
  const [categories, setCategories] = useState<PublicNafCategory[]>([]);
  const [isLoadingCategories, setIsLoadingCategories] = useState(false);
  const [categoriesError, setCategoriesError] = useState<string | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<PlanKey | null>(null);
  const [selectedCategoryIds, setSelectedCategoryIds] = useState<string[]>([]);
  const [checkoutForm, setCheckoutForm] = useState({
    contactName: "",
    companyName: "",
    email: "",
  });
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false);
  const [isCheckoutLoading, setIsCheckoutLoading] = useState(false);

  const [isPortalOpen, setIsPortalOpen] = useState(false);
  const [portalEmail, setPortalEmail] = useState("");
  const [portalError, setPortalError] = useState<string | null>(null);
  const [isPortalLoading, setIsPortalLoading] = useState(false);

  const plans = [
    {
      key: "starter" as PlanKey,
      name: "Starter",
      price: "56",
      originalPrice: "69",
      period: "mois",
      description: "Pour démarrer simplement",
      features: [
        "Alertes quotidiennes par email",
        "1 secteur sélectionné (sur le catalogue complet)",
        "Nouvelles entreprises détectées en France",
      ],
      cta: "Commencer",
      highlighted: false,
    },
    {
      key: "business" as PlanKey,
      name: "Business",
      price: "128",
      originalPrice: "159",
      period: "mois",
      description: "Le plus populaire",
      features: [
        "Alertes quotidiennes par email",
        "3 secteurs sélectionnés (sur le catalogue complet)",
        "Historique 2 mois (sur vos secteurs)",
      ],
      cta: "Démarrer maintenant",
      highlighted: true,
    },
    {
      key: null,
      name: "Enterprise",
      price: "Sur devis",
      period: "",
      description: "Pour couvrir tous les secteurs",
      features: [
        "Alertes quotidiennes par email",
        "Secteurs illimités",
        "Historique 4 mois (sur vos secteurs)",
      ],
      cta: "Nous contacter",
      highlighted: false,
    },
  ];

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

  const requiredCategoryCount = useMemo(() => {
    if (!selectedPlan) return 0;
    return PLAN_CATEGORY_LIMITS[selectedPlan];
  }, [selectedPlan]);

  const scrollToContact = () => {
    document.getElementById("contact")?.scrollIntoView({ behavior: "smooth" });
  };

  const handleOpenCheckout = (planKey: PlanKey) => {
    setSelectedPlan(planKey);
    setSelectedCategoryIds([]);
    setCheckoutForm({ contactName: "", companyName: "", email: "" });
    setCheckoutError(null);
    setIsCheckoutOpen(true);
  };

  const handleToggleCategory = (categoryId: string) => {
    setSelectedCategoryIds((current) => {
      if (current.includes(categoryId)) {
        return current.filter((id) => id !== categoryId);
      }
      if (current.length >= requiredCategoryCount) {
        return current;
      }
      return [...current, categoryId];
    });
  };

  const handleCheckoutSubmit = async () => {
    if (!selectedPlan) return;
    if (selectedCategoryIds.length !== requiredCategoryCount) {
      setCheckoutError(`Sélectionnez exactement ${requiredCategoryCount} catégorie(s).`);
      return;
    }
    if (!checkoutForm.contactName.trim() || !checkoutForm.companyName.trim() || !checkoutForm.email.trim()) {
      setCheckoutError("Merci de renseigner vos coordonnées.");
      return;
    }

    setCheckoutError(null);
    setIsCheckoutLoading(true);

    try {
      const response = await fetch(`${apiBaseUrl}/public/stripe/checkout`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          plan_key: selectedPlan,
          category_ids: selectedCategoryIds,
          contact_name: checkoutForm.contactName,
          company_name: checkoutForm.companyName,
          email: checkoutForm.email,
        }),
      });

      if (!response.ok) {
        let detail = "Impossible de démarrer le paiement.";
        try {
          const payload = await response.json();
          if (typeof payload?.detail === "string") {
            detail = payload.detail;
          }
        } catch {
          // ignore
        }
        setCheckoutError(detail);
        return;
      }

      const payload = (await response.json()) as { url: string };
      if (payload.url) {
        window.location.href = payload.url;
      } else {
        setCheckoutError("URL Stripe invalide.");
      }
    } finally {
      setIsCheckoutLoading(false);
    }
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
        headers: {
          "Content-Type": "application/json",
        },
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


  return (
    <section id="pricing" className="py-20 bg-muted/50">
      <div className="container mx-auto px-4">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            Tarifs transparents
          </h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Choisissez la formule adaptée au nombre de secteurs à surveiller
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto">
          {plans.map((plan, index) => (
            <Card
              key={index}
              className={`relative p-8 flex flex-col ${
                plan.highlighted
                  ? "border-2 border-secondary shadow-lg scale-105"
                  : "border"
              }`}
            >
              {plan.highlighted && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2 bg-secondary text-secondary-foreground px-4 py-1 rounded-full text-sm font-semibold">
                  Recommandé
                </div>
              )}

              <div className="text-center mb-6">
                <h3 className="text-2xl font-bold mb-2">{plan.name}</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  {plan.description}
                </p>
                <div className="flex items-end justify-center gap-2">
                  {plan.price !== "Sur devis" && plan.originalPrice && (
                    <span className="text-xl text-muted-foreground line-through">
                      {plan.originalPrice}€
                    </span>
                  )}
                  {plan.price !== "Sur devis" && (
                    <span className="text-4xl font-bold">{plan.price}€</span>
                  )}
                  {plan.price === "Sur devis" && (
                    <span className="text-3xl font-bold">{plan.price}</span>
                  )}
                  {plan.period && (
                    <span className="text-muted-foreground mb-1">
                      /{plan.period}
                    </span>
                  )}
                </div>
              </div>

              <ul className="space-y-3 mb-8 flex-grow">
                {plan.features.map((feature, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <Check className="w-5 h-5 text-secondary flex-shrink-0 mt-0.5" />
                    <span className="text-sm">{feature}</span>
                  </li>
                ))}
              </ul>

              <Button
                variant={plan.highlighted ? "default" : "outline"}
                size="lg"
                className="w-full"
                onClick={() => {
                  if (plan.key) {
                    handleOpenCheckout(plan.key);
                  } else {
                    scrollToContact();
                  }
                }}
              >
                {plan.cta}
              </Button>
            </Card>
          ))}
        </div>

        <div className="mt-12 text-center">
          <p className="text-muted-foreground">
            Toutes les offres incluent un essai gratuit de {trialPeriodDays} jours
          </p>
          <p className="text-sm text-muted-foreground mt-2">
            Résiliation possible à la fin de chaque mois. Changement de plan avec proratisation immédiate.
          </p>
          <div className="mt-6">
            <Button variant="outline" onClick={() => setIsPortalOpen(true)}>
              Gérer mon abonnement
            </Button>
            <Button variant="outline" className="ml-3" asChild>
              <Link to="/upgrade">Changer de plan</Link>
            </Button>
          </div>
        </div>
      </div>

      <Dialog open={isCheckoutOpen} onOpenChange={setIsCheckoutOpen}>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>Choisissez vos catégories</DialogTitle>
            <DialogDescription>
              Sélectionnez exactement {requiredCategoryCount} catégorie(s) pour votre plan.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {isLoadingCategories ? (
              <p className="text-sm text-muted-foreground">Chargement des catégories…</p>
            ) : categoriesError ? (
              <p className="text-sm text-destructive">{categoriesError}</p>
            ) : (
              <div className="grid gap-3">
                {categories.map((category) => {
                  const isSelected = selectedCategoryIds.includes(category.id);
                  const isDisabled =
                    !isSelected && selectedCategoryIds.length >= requiredCategoryCount;
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

            <div className="grid gap-3">
              <div>
                <Label htmlFor="contactName">Nom complet</Label>
                <Input
                  id="contactName"
                  value={checkoutForm.contactName}
                  onChange={(event) =>
                    setCheckoutForm((current) => ({ ...current, contactName: event.target.value }))
                  }
                  placeholder="Jean Dupont"
                />
              </div>
              <div>
                <Label htmlFor="companyName">Entreprise</Label>
                <Input
                  id="companyName"
                  value={checkoutForm.companyName}
                  onChange={(event) =>
                    setCheckoutForm((current) => ({ ...current, companyName: event.target.value }))
                  }
                  placeholder="Business Tracker"
                />
              </div>
              <div>
                <Label htmlFor="checkoutEmail">Email professionnel</Label>
                <Input
                  id="checkoutEmail"
                  type="email"
                  value={checkoutForm.email}
                  onChange={(event) =>
                    setCheckoutForm((current) => ({ ...current, email: event.target.value }))
                  }
                  placeholder="vous@entreprise.fr"
                />
              </div>
            </div>

            {checkoutError ? <p className="text-sm text-destructive">{checkoutError}</p> : null}
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setIsCheckoutOpen(false)}>
              Annuler
            </Button>
            <Button onClick={handleCheckoutSubmit} disabled={isCheckoutLoading}>
              {isCheckoutLoading ? "Redirection…" : "Payer sur Stripe"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isPortalOpen} onOpenChange={setIsPortalOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Accéder au portail client</DialogTitle>
            <DialogDescription>
              Renseignez votre email pour gérer votre abonnement Stripe.
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
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setIsPortalOpen(false)}>
              Fermer
            </Button>
            <Button onClick={handlePortalSubmit} disabled={isPortalLoading}>
              {isPortalLoading ? "Ouverture…" : "Ouvrir le portail"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

    </section>
  );
};

export default Pricing;
