import { Zap, Target, Clock, TrendingUp, Shield, Sparkles } from "lucide-react";
import { Card } from "@/components/ui/card";

const Benefits = () => {
  const benefits = [
    {
      icon: Zap,
      title: "Gain de temps considérable",
      description: "Fini les recherches manuelles fastidieuses. Recevez automatiquement tous les nouveaux prospects chaque semaine.",
    },
    {
      icon: Target,
      title: "Ciblage ultra-précis",
      description: "Filtrez par secteur d'activité, localisation géographique et critères spécifiques à votre business.",
    },
    {
      icon: Clock,
      title: "Réactivité maximale",
      description: "Contactez les nouvelles entreprises avant vos concurrents avec des données ultra-fraîches.",
    },
    {
      icon: TrendingUp,
      title: "ROI immédiat",
      description: "Convertissez plus facilement des entreprises en phase de création, au moment où elles cherchent leurs fournisseurs.",
    },
    {
      icon: Shield,
      title: "Données officielles et fiables",
      description: "Sources officielles vérifiées pour une qualité de données irréprochable.",
    },
    {
      icon: Sparkles,
      title: "Simplicité d'utilisation",
      description: "Aucune installation, aucune configuration. Recevez vos fichiers directement par email.",
    },
  ];

  return (
    <section className="py-20 bg-background">
      <div className="container mx-auto px-4">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            Les avantages de Business Tracking
          </h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Optimisez votre prospection et développez votre business plus rapidement
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8 max-w-6xl mx-auto">
          {benefits.map((benefit, index) => (
            <Card key={index} className="p-6 hover:shadow-md transition-all duration-300 hover:border-secondary/30">
              <div className="w-14 h-14 bg-gradient-secondary rounded-lg flex items-center justify-center mb-4">
                <benefit.icon className="w-7 h-7 text-secondary-foreground" />
              </div>
              <h3 className="text-xl font-semibold mb-3">
                {benefit.title}
              </h3>
              <p className="text-muted-foreground">
                {benefit.description}
              </p>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
};

export default Benefits;
