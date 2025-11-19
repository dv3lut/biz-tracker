import { CheckCircle2 } from "lucide-react";
import { Card } from "@/components/ui/card";

const WhatYouGet = () => {
  const dataFields = [
    "Raison sociale complète",
    "Forme juridique (SARL, SAS, EURL...)",
    "Adresse complète de l'établissement",
    "Code NAF et secteur d'activité détaillé",
    "Date de création exacte",
    "Capital social",
    "Numéro SIREN/SIRET",
    "Nom du dirigeant (si disponible)",
    "Coordonnées de contact (téléphone, email si disponibles)",
    "Site web (si disponible)",
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
              Un fichier Excel ou CSV complet et structuré avec toutes les données essentielles
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
                Formats disponibles
              </h3>
              <p className="text-muted-foreground mb-3">
                Recevez vos données dans le format de votre choix :
              </p>
              <div className="flex flex-wrap gap-3">
                <span className="px-4 py-2 bg-background rounded-md text-sm font-medium border">
                  📊 Excel (.xlsx)
                </span>
                <span className="px-4 py-2 bg-background rounded-md text-sm font-medium border">
                  📄 CSV
                </span>
                <span className="px-4 py-2 bg-background rounded-md text-sm font-medium border">
                  🔗 API (sur demande)
                </span>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </section>
  );
};

export default WhatYouGet;
