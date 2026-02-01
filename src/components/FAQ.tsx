import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

type Props = {
  trialPeriodDays?: number;
};

const FAQ = ({ trialPeriodDays = 14 }: Props) => {
  const faqs = [
    {
      question: "D'où viennent les données ?",
      answer: "Nous analysons quotidiennement des bases officielles disponibles en France pour détecter des créations récentes et certaines mises à jour administratives récentes.",
    },
    {
      question: "À quelle fréquence les données sont-elles mises à jour ?",
      answer: "Les alertes sont envoyées chaque jour par email, quelle que soit la formule.",
    },
    {
      question: "Puis-je choisir les secteurs à surveiller ?",
      answer: "Oui. Vous sélectionnez un ou plusieurs secteurs d’activité (parmi des centaines de catégories) et vous recevez les alertes correspondant à vos choix. L’offre Enterprise permet un nombre de secteurs illimité.",
    },
    {
      question: "Les données incluent-elles les coordonnées de contact ?",
      answer: "Oui. Chaque alerte est associée à une fiche Google : nous affichons le lien vers la fiche et les contacts présents (ex: téléphone, site web).",
    },
    {
      question: "Puis-je annuler mon abonnement à tout moment ?",
      answer: `Oui, sans engagement. Vous pouvez suspendre ou annuler votre abonnement à tout moment depuis le portail. L’essai de ${trialPeriodDays} jours démarre après la souscription (paiement requis) et vous pouvez annuler avant la première facturation.`,
    },
    {
      question: "Que contient une alerte ?",
      answer: "Chaque alerte contient au minimum le nom de l’entreprise, son adresse, son secteur, et un indicateur indiquant si l’alerte concerne une création récente ou une mise à jour administrative récente. Il y a également le lien vers la fiche Google associée, contenant les coordonnées de contact si disponibles.",
    },
    {
      question: "Y a-t-il un portail / dashboard ?",
      answer: "Pour l’instant, la livraison se fait par email. Nous travaillons sur un portail avec dashboard pour gérer les secteurs, l’historique et le suivi de vos alertes depuis une interface dédiée.",
    },    {
      question: "Couvrez-vous d'autres pays que la France ?",
      answer: "Pour l'instant, le service est disponible uniquement pour la France. Nous travaillons activement sur l'expansion à d'autres pays européens. Contactez-nous si vous êtes intéressé par une future couverture.",
    },  ];

  return (
    <section className="py-20 bg-background">
      <div className="container mx-auto px-4">
        <div className="max-w-3xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              Questions fréquentes
            </h2>
            <p className="text-lg text-muted-foreground">
              Tout ce que vous devez savoir sur Business Tracker
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
