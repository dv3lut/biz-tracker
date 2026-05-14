import { useEffect, useMemo, useRef, useState } from "react";
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
import { Calendar, Check, Sparkles, Target, Zap } from "lucide-react";

const CALENDLY_URL = "https://calendly.com/julien-businesstracker/30min";

type PlanKey = "starter" | "business";

type PublicNafCategory = {
  id: string;
  name: string;
  description: string | null;
  activeSubcategoryCount: number;
};

const PLAN_CATEGORY_LIMITS: Record<PlanKey, number> = {
  starter: 1,
  business: 5,
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
  const [isCategoryDropdownOpen, setIsCategoryDropdownOpen] = useState(false);
  const categoryDropdownRef = useRef<HTMLDivElement | null>(null);
  const [checkoutForm, setCheckoutForm] = useState({
    contactName: "",
    companyName: "",
    email: "",
    referrerName: "",
  });
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false);
  const [isCheckoutLoading, setIsCheckoutLoading] = useState(false);

  const [isPortalOpen, setIsPortalOpen] = useState(false);
  const [portalEmail, setPortalEmail] = useState("");
  const [portalError, setPortalError] = useState<string | null>(null);
  const [portalSuccess, setPortalSuccess] = useState<string | null>(null);
  const [isPortalLoading, setIsPortalLoading] = useState(false);

  const [isCalendlyOpen, setIsCalendlyOpen] = useState(false);


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
      cta: "Démarrer maintenant",
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
        "5 secteurs sélectionnés (sur le catalogue complet)",
        "Historique 2 mois (sur vos secteurs)",
      ],
      cta: "Démarrer maintenant",
      highlighted: true,
    },
    {
      key: null,
      name: "Prospection IA",
      price: "Sur mesure",
      period: "",
      description: "Votre pipeline en pilote automatique",
      features: [
        "Ciblage IA sur-mesure pour votre activité",
        "Prospection multi-canal entièrement automatisée",
        "Pipeline d'opportunités livré clé en main",
      ],
      cta: "Réserver un appel",
      highlighted: false,
      isCalendly: true,
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

  const requiredCategoryCount = useMemo(() => {
    if (!selectedPlan) return 0;
    return PLAN_CATEGORY_LIMITS[selectedPlan];
  }, [selectedPlan]);

  const selectedCategoryNames = useMemo(() => {
    if (!selectedCategoryIds.length) return [];
    const categoryMap = new Map(categories.map((category) => [category.id, category.name]));
    return selectedCategoryIds
      .map((id) => categoryMap.get(id))
      .filter((name): name is string => Boolean(name));
  }, [categories, selectedCategoryIds]);

  const scrollToContact = () => {
    document.getElementById("contact")?.scrollIntoView({ behavior: "smooth" });
  };

  const handleMissingCategories = () => {
    const message =
      "Bonjour, j'aimerais souscrire au service Business Tracker mais je ne trouve pas la/les catégorie(s) :";
    sessionStorage.setItem("bt_contact_prefill_message", message);
    window.dispatchEvent(
      new CustomEvent("bt:prefill-contact", {
        detail: { message },
      })
    );
    setIsCheckoutOpen(false);
    scrollToContact();
  };

  const handleOpenCheckout = (planKey: PlanKey) => {
    setSelectedPlan(planKey);
    setSelectedCategoryIds([]);
    setIsCategoryDropdownOpen(false);
    setCheckoutForm({ contactName: "", companyName: "", email: "", referrerName: "" });
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
      const next = [...current, categoryId];
      if (next.length >= requiredCategoryCount) {
        setIsCategoryDropdownOpen(false);
      }
      return next;
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
          referrer_name: checkoutForm.referrerName.trim() || null,
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
          {plans.map((plan, index) => {
            const isCalendly = "isCalendly" in plan && plan.isCalendly;
            return (
            <Card
              key={index}
              className={`relative p-8 flex flex-col ${
                plan.highlighted
                  ? "border-2 border-secondary shadow-lg scale-105"
                  : isCalendly
                  ? "border border-secondary/40"
                  : "border"
              }`}
            >
              {isCalendly && (
                <>
                  <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-lg">
                    <div className="absolute -top-16 -right-16 h-40 w-40 rounded-full bg-secondary/15 blur-3xl animate-pulse-glow" />
                    <div className="absolute -bottom-16 -left-16 h-40 w-40 rounded-full bg-primary/10 blur-3xl animate-pulse-glow [animation-delay:1.2s]" />
                  </div>
                  <div className="absolute -top-4 left-1/2 -translate-x-1/2 flex items-center gap-1.5 bg-gradient-to-r from-primary to-secondary text-primary-foreground px-4 py-1 rounded-full text-sm font-semibold shadow-md whitespace-nowrap">
                    <Sparkles className="w-3.5 h-3.5" />
                    Nouveau
                  </div>
                </>
              )}
              {plan.highlighted && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2 bg-secondary text-secondary-foreground px-4 py-1 rounded-full text-sm font-semibold">
                  Recommandé
                </div>
              )}

              <div className="relative text-center mb-6">
                <h3 className="text-2xl font-bold mb-2">{plan.name}</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  {plan.description}
                </p>
                <div className="flex items-end justify-center gap-2">
                  {!isCalendly && plan.originalPrice && (
                    <span className="text-xl text-muted-foreground line-through">
                      {plan.originalPrice}€
                    </span>
                  )}
                  {!isCalendly && (
                    <span className="text-4xl font-bold">{plan.price}€</span>
                  )}
                  {isCalendly && (
                    <span className="text-3xl font-bold bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
                      {plan.price}
                    </span>
                  )}
                  {plan.period && (
                    <span className="text-muted-foreground mb-1">
                      /{plan.period}
                    </span>
                  )}
                </div>
              </div>

              <ul className="relative space-y-3 mb-8 flex-grow">
                {plan.features.map((feature, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    {isCalendly ? (
                      <Target className="w-5 h-5 text-secondary flex-shrink-0 mt-0.5" />
                    ) : (
                      <Check className="w-5 h-5 text-secondary flex-shrink-0 mt-0.5" />
                    )}
                    <span className="text-sm">{feature}</span>
                  </li>
                ))}
              </ul>

              <Button
                variant={plan.highlighted || isCalendly ? "default" : "outline"}
                size="lg"
                className={`relative w-full ${
                  isCalendly
                    ? "bg-gradient-to-r from-primary to-secondary hover:opacity-90 transition-opacity"
                    : ""
                }`}
                onClick={() => {
                  if (isCalendly) {
                    setIsCalendlyOpen(true);
                  } else if (plan.key) {
                    handleOpenCheckout(plan.key);
                  } else {
                    scrollToContact();
                  }
                }}
              >
                {isCalendly && <Calendar className="w-4 h-4 mr-2" />}
                {plan.cta}
              </Button>
            </Card>
            );
          })}
        </div>

        <div className="mt-12 text-center">
          <p className="text-muted-foreground">
            Toutes les offres incluent {trialPeriodDays} jours d’essai (activation après souscription)
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <Button variant="outline" onClick={() => setIsPortalOpen(true)}>
              Portail client
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
                        : `Sélectionner ${requiredCategoryCount} catégorie(s)`}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {selectedCategoryIds.length}/{requiredCategoryCount}
                    </span>
                  </button>
                  {isCategoryDropdownOpen ? (
                    <div className="absolute z-20 mt-2 w-full rounded-md border bg-background shadow-lg">
                      <div className="max-h-64 space-y-2 overflow-y-auto p-2">
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
                  {selectedCategoryIds.length}/{requiredCategoryCount} sélectionnée(s)
                </p>
              </div>
            )}

            <button
              type="button"
              onClick={handleMissingCategories}
              className="text-sm text-secondary hover:text-secondary/80 underline underline-offset-4"
            >
              Je ne trouve pas la/les catégories que je veux
            </button>

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
              <div>
                <Label htmlFor="checkout-referrer">Parrain (optionnel)</Label>
                <Input
                  id="checkout-referrer"
                  placeholder="Nom / prénom de la personne qui vous a conseillé Business Tracker"
                  value={checkoutForm.referrerName}
                  onChange={(event) =>
                    setCheckoutForm((current) => ({
                      ...current,
                      referrerName: event.target.value,
                    }))
                  }
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
              {isCheckoutLoading ? "Redirection…" : "Continuer"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isCalendlyOpen} onOpenChange={setIsCalendlyOpen}>
        <DialogContent className="sm:max-w-md overflow-hidden">
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-secondary/10" />
          <DialogHeader className="relative">
            <DialogTitle className="text-center text-2xl">
              Laissez l'IA prospecter pour vous
            </DialogTitle>
            <DialogDescription className="text-center">
              Échangeons 30 minutes pour cadrer votre cible idéale et lancer votre prospection automatisée.
            </DialogDescription>
          </DialogHeader>

          <div className="relative flex flex-col items-center gap-6 py-6">
            <div className="relative flex h-28 w-28 items-center justify-center">
              <div className="absolute inset-0 rounded-full bg-secondary/30 blur-2xl animate-pulse-glow" />
              <div className="absolute inset-2 rounded-full bg-gradient-to-br from-primary to-secondary opacity-90" />
              <Calendar className="relative h-12 w-12 text-primary-foreground animate-float" strokeWidth={2.2} />
              <Sparkles className="absolute -top-1 -right-1 h-6 w-6 text-secondary animate-sparkle" />
              <Sparkles className="absolute -bottom-1 -left-2 h-5 w-5 text-primary animate-sparkle [animation-delay:0.8s]" />
            </div>

            <div className="flex flex-col gap-2.5 w-full text-sm">
              <div className="flex items-center gap-3 rounded-lg border border-secondary/20 bg-background/50 px-3 py-2.5">
                <Target className="w-5 h-5 text-secondary flex-shrink-0" />
                <span>Ciblage IA sur-mesure pour votre activité</span>
              </div>
              <div className="flex items-center gap-3 rounded-lg border border-secondary/20 bg-background/50 px-3 py-2.5">
                <Zap className="w-5 h-5 text-secondary flex-shrink-0" />
                <span>Prospection multi-canal 100 % automatisée</span>
              </div>
              <div className="flex items-center gap-3 rounded-lg border border-secondary/20 bg-background/50 px-3 py-2.5">
                <Calendar className="w-5 h-5 text-secondary flex-shrink-0" />
                <span>30 minutes pour tout configurer ensemble</span>
              </div>
            </div>
          </div>

          <DialogFooter className="relative sm:justify-center gap-2">
            <Button variant="outline" onClick={() => setIsCalendlyOpen(false)}>
              Annuler
            </Button>
            <Button
              asChild
              className="bg-gradient-to-r from-primary to-secondary hover:opacity-90 transition-opacity"
            >
              <a
                href={CALENDLY_URL}
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => setIsCalendlyOpen(false)}
              >
                <Calendar className="w-4 h-4 mr-2" />
                Ouvrir Calendly
              </a>
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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

    </section>
  );
};

export default Pricing;
