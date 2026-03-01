import { CheckCircle2 } from "lucide-react";
import { Card } from "@/components/ui/card";

const WhatYouGet = () => {
  const dataFields = [
    "Nom d’entreprise",
    "Adresse",
    "Secteur(s) d’activité",
    "Type d’alerte (création récente ou mise à jour administrative récente)",
    "Lien vers la fiche Google",
    "Contacts présents sur la fiche Google (téléphone, site web…)",
  ];

  return (
    <section className="py-20 bg-muted/50">
      <div className="container mx-auto px-4">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              Ce que vous recevez
            </h2>
            <p className="text-lg text-muted-foreground">
              Un email quotidien avec des alertes sur vos secteurs (créations et mises à jour administratives)
            </p>
          </div>

          <Card className="p-8 md:p-12">
            <div className="grid md:grid-cols-2 gap-4">
              {dataFields.map((field, index) => (
                <div key={index} className="flex items-start gap-3">
                  <CheckCircle2 className="w-5 h-5 text-secondary flex-shrink-0 mt-0.5" />
                  <span className="text-foreground">{field}</span>
                </div>
              ))}
            </div>

            <div className="mt-10 p-6 bg-secondary/10 rounded-lg border border-secondary/20">
              <h3 className="font-semibold text-lg mb-3 flex items-center gap-2">
                <span className="text-secondary">✓</span>
                À savoir
              </h3>
              <p className="text-muted-foreground">
                Les alertes couvrent les créations récentes et certains changements administratifs récents.
                La fiche Google peut concerner un établissement plus ancien.
              </p>
            </div>
          </Card>
        </div>
      </div>
    </section>
  );
};

export default WhatYouGet;
