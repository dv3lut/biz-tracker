import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

const FAQ = () => {
  const faqs = [
    {
      question: "D'où viennent les données ?",
      answer: "Nos données proviennent des registres officiels français (INPI, INSEE). Nous analysons quotidiennement ces sources pour détecter toutes les nouvelles créations d'entreprises et d'établissements en France.",
    },
    {
      question: "À quelle fréquence les données sont-elles mises à jour ?",
      answer: "Les données sont collectées quotidiennement. Selon votre formule, vous recevez votre fichier chaque semaine, chaque mois, ou même quotidiennement pour l'offre Enterprise. Vous avez ainsi accès aux créations les plus récentes.",
    },
    {
      question: "Puis-je filtrer par secteur d'activité ou zone géographique ?",
      answer: "Oui, absolument. Vous pouvez choisir les départements qui vous intéressent et filtrer par codes NAF (secteurs d'activité). Pour des filtres encore plus avancés, notre équipe peut configurer des critères sur mesure avec l'offre Enterprise.",
    },
    {
      question: "Les données incluent-elles les coordonnées de contact ?",
      answer: "Oui, nous fournissons toutes les informations publiques disponibles : numéro SIREN/SIRET, adresse, raison sociale, dirigeant, et lorsque disponible, téléphone, email et site web. Ces informations permettent de contacter directement les prospects.",
    },
    {
      question: "Puis-je annuler mon abonnement à tout moment ?",
      answer: "Oui, aucun engagement. Vous pouvez suspendre ou annuler votre abonnement à tout moment. De plus, nous offrons 7 jours d'essai gratuit pour toutes nos formules afin que vous puissiez tester le service sans risque.",
    },
    {
      question: "Comment puis-je utiliser les fichiers dans mon CRM ?",
      answer: "Nos fichiers Excel et CSV sont prêts à l'importation dans tous les CRM du marché (Salesforce, HubSpot, Pipedrive, etc.). Pour l'offre Enterprise, nous proposons également une intégration API directe pour automatiser complètement le processus.",
    },
  ];

  return (
    <section className="py-20 bg-background">
      <div className="container mx-auto px-4">
        <div className="max-w-3xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              Questions fréquentes
            </h2>
            <p className="text-lg text-muted-foreground">
              Tout ce que vous devez savoir sur Business Tracking
            </p>
          </div>

          <Accordion type="single" collapsible className="w-full">
            {faqs.map((faq, index) => (
              <AccordionItem key={index} value={`item-${index}`}>
                <AccordionTrigger className="text-left text-lg font-semibold">
                  {faq.question}
                </AccordionTrigger>
                <AccordionContent className="text-muted-foreground">
                  {faq.answer}
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </div>
      </div>
    </section>
  );
};

export default FAQ;
