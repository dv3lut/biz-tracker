import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Check } from "lucide-react";

const Pricing = () => {
  const plans = [
    {
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

  const scrollToContact = () => {
    document.getElementById("contact")?.scrollIntoView({ behavior: "smooth" });
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
                onClick={scrollToContact}
              >
                {plan.cta}
              </Button>
            </Card>
          ))}
        </div>

        <div className="mt-12 text-center">
          <p className="text-muted-foreground">
            Toutes les offres incluent un essai gratuit de 14 jours
          </p>
        </div>
      </div>
    </section>
  );
};

export default Pricing;
