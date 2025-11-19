import { Store, Utensils, Package, Smartphone, TrendingUp, Users } from "lucide-react";
import { Card } from "@/components/ui/card";

const TargetAudience = () => {
  const audiences = [
    {
      icon: Utensils,
      title: "Solutions pour la restauration",
      examples: "Zenchef, TheFork, Guestonline, L'Addition...",
    },
    {
      icon: Store,
      title: "Solutions pour les commerces",
      examples: "Lightspeed, Shopify, Square, Sumup...",
    },
    {
      icon: Package,
      title: "Livraison et logistique",
      examples: "Deliverect, Stuart, Glovo, Uber Eats...",
    },
    {
      icon: Smartphone,
      title: "Marketing & Communication",
      examples: "Mailchimp, Sendinblue, Partoo, Trustpilot...",
    },
    {
      icon: Users,
      title: "RH & Gestion d'équipe",
      examples: "Skello, PayFit, Lucca, Factorial...",
    },
    {
      icon: TrendingUp,
      title: "Finance & Comptabilité",
      examples: "Qonto, Shine, Pennylane, Indy...",
    },
  ];

  return (
    <section className="py-20 bg-background">
      <div className="container mx-auto px-4">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            À qui s'adresse Business Tracking ?
          </h2>
          <p className="text-lg text-muted-foreground max-w-3xl mx-auto">
            Toutes les entreprises qui doivent identifier rapidement les nouvelles ouvertures de restaurants, 
            commerces et établissements pour développer leur activité.
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-6xl mx-auto">
          {audiences.map((audience, index) => (
            <Card key={index} className="p-6 hover:shadow-md transition-all duration-300 hover:border-secondary/50">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 bg-secondary/10 rounded-lg flex items-center justify-center flex-shrink-0">
                  <audience.icon className="w-6 h-6 text-secondary" />
                </div>
                <div>
                  <h3 className="font-semibold mb-2">
                    {audience.title}
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    {audience.examples}
                  </p>
                </div>
              </div>
            </Card>
          ))}
        </div>

        <div className="mt-12 text-center">
          <p className="text-lg font-medium text-foreground">
            Et bien d'autres secteurs qui cherchent à conquérir de nouveaux clients B2B
          </p>
        </div>
      </div>
    </section>
  );
};

export default TargetAudience;
