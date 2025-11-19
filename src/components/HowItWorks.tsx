import { Database, FileSpreadsheet, Send } from "lucide-react";
import { Card } from "@/components/ui/card";

const HowItWorks = () => {
  const steps = [
    {
      icon: Database,
      title: "Détection automatique",
      description: "Notre système analyse quotidiennement les registres officiels (INPI, INSEE) pour identifier toutes les nouvelles créations d'entreprises et d'établissements en France.",
    },
    {
      icon: FileSpreadsheet,
      title: "Enrichissement des données",
      description: "Nous collectons et structurons toutes les informations essentielles : raison sociale, adresse, contact, secteur d'activité, et bien plus encore.",
    },
    {
      icon: Send,
      title: "Livraison par email",
      description: "Recevez automatiquement votre fichier Excel ou CSV chaque semaine ou chaque mois, prêt à être importé dans votre CRM ou vos outils de prospection.",
    },
  ];

  return (
    <section className="py-20 bg-muted/50">
      <div className="container mx-auto px-4">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            Comment ça marche ?
          </h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Un processus simple et entièrement automatisé pour vous fournir les meilleurs prospects
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto">
          {steps.map((step, index) => (
            <Card key={index} className="relative p-8 hover:shadow-lg transition-shadow duration-300">
              <div className="absolute -top-4 left-8 w-12 h-12 bg-gradient-hero rounded-full flex items-center justify-center text-primary-foreground font-bold text-lg">
                {index + 1}
              </div>
              
              <div className="mt-4 mb-6">
                <div className="w-16 h-16 bg-secondary/10 rounded-lg flex items-center justify-center">
                  <step.icon className="w-8 h-8 text-secondary" />
                </div>
              </div>

              <h3 className="text-xl font-semibold mb-3">
                {step.title}
              </h3>
              <p className="text-muted-foreground">
                {step.description}
              </p>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
};

export default HowItWorks;
