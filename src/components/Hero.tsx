import { Button } from "@/components/ui/button";
import { ArrowRight, Sparkles } from "lucide-react";
import heroBg from "@/assets/hero-bg.jpg";

const Hero = () => {
  const scrollToContact = () => {
    document.getElementById("contact")?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <section 
      className="relative min-h-[90vh] flex items-center justify-center overflow-hidden"
      style={{
        backgroundImage: `linear-gradient(rgba(7, 48, 87, 0.95), rgba(7, 48, 87, 0.85)), url(${heroBg})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}
    >
      <div className="container mx-auto px-4 py-20 relative z-10">
        <div className="max-w-4xl mx-auto text-center">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 bg-background/10 backdrop-blur-sm border border-background/20 rounded-full px-4 py-2 mb-8">
            <Sparkles className="w-4 h-4 text-secondary" />
            <span className="text-sm font-medium text-primary-foreground">
              Alertes quotidiennes • Des centaines de secteurs
            </span>
          </div>

          {/* Main Heading */}
          <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-primary-foreground mb-6 leading-tight">
            Recevez chaque jour les nouveaux business détectés en France
          </h1>

          {/* Subheading */}
          <p className="text-xl md:text-2xl text-primary-foreground/90 mb-4">
            Triés par secteur d’activité
          </p>

          <p className="text-lg text-primary-foreground/80 mb-10 max-w-2xl mx-auto">
            Business Tracker envoie des alertes quotidiennes par email sur des créations récentes et des mises à jour
            administratives récentes d’entreprises en France, selon les secteurs que vous avez sélectionnés.
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
            <Button 
              size="lg" 
              variant="hero"
              onClick={scrollToContact}
              className="text-lg px-8 py-6 h-auto"
            >
              Essai gratuit 14 jours
              <ArrowRight className="ml-2 w-5 h-5" />
            </Button>
            <Button 
              size="lg" 
              variant="outline-light"
              onClick={() => document.getElementById("pricing")?.scrollIntoView({ behavior: "smooth" })}
              className="text-lg px-8 py-6 h-auto"
            >
              Voir les tarifs
            </Button>
          </div>

          {/* Trust Indicators */}
          <div className="mt-16 flex flex-wrap justify-center gap-8 text-primary-foreground/70 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-secondary rounded-full" />
              <span>Données officielles vérifiées</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-secondary rounded-full" />
              <span>Envoi par email chaque jour</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-secondary rounded-full" />
              <span>Secteurs au choix (1, 3 ou illimité)</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Hero;
