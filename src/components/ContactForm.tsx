import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Mail, Phone, MapPin } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

const ContactForm = () => {
  const { toast } = useToast();
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    linkedin: "",
    phone: "",
    message: "",
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [cooldownUntilMs, setCooldownUntilMs] = useState<number | null>(null);
  const [nowMs, setNowMs] = useState(() => Date.now());
  const [isSuccessDialogOpen, setIsSuccessDialogOpen] = useState(false);

  const cooldownRemainingSeconds = useMemo(() => {
    if (!cooldownUntilMs) return 0;
    const remainingMs = cooldownUntilMs - nowMs;
    return remainingMs > 0 ? Math.ceil(remainingMs / 1000) : 0;
  }, [cooldownUntilMs, nowMs]);

  const isInCooldown = cooldownRemainingSeconds > 0;

  const isProfessionalEmail = (email: string) => {
    const normalized = email.trim().toLowerCase();
    const atIndex = normalized.lastIndexOf("@");
    if (atIndex <= 0 || atIndex === normalized.length - 1) return false;
    const domain = normalized.slice(atIndex + 1);

    const personalDomains = new Set([
      "gmail.com",
      "googlemail.com",
      "yahoo.com",
      "yahoo.fr",
      "ymail.com",
      "outlook.com",
      "hotmail.com",
      "live.com",
      "msn.com",
      "aol.com",
      "icloud.com",
      "me.com",
      "mac.com",
      "proton.me",
      "protonmail.com",
      "gmx.com",
      "gmx.fr",
      "mail.com",
      "yandex.com",
      "yandex.ru",
      "orange.fr",
      "wanadoo.fr",
      "sfr.fr",
      "neuf.fr",
      "free.fr",
      "laposte.net",
      "bbox.fr",
      "aliceadsl.fr",
    ]);

    return !personalDomains.has(domain);
  };

  const apiBaseUrl = (import.meta.env.VITE_APP_API_BASE_URL ?? "").replace(/\/$/, "");

  useEffect(() => {
    if (!cooldownUntilMs) return;
    if (Date.now() >= cooldownUntilMs) return;

    const interval = window.setInterval(() => {
      setNowMs(Date.now());
    }, 250);

    return () => window.clearInterval(interval);
  }, [cooldownUntilMs]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting || isInCooldown) return;

    if (!isProfessionalEmail(formData.email)) {
      toast({
        title: "Email professionnel requis",
        description: "Merci d'utiliser une adresse email d'entreprise (pas Gmail/Yahoo/Outlook…).",
        variant: "destructive",
      });
      return;
    }

    // Anti-spam: évite plusieurs soumissions successives (ex: double-clic).
    setCooldownUntilMs(Date.now() + 8000);
    setNowMs(Date.now());
    setIsSubmitting(true);

    try {
      const response = await fetch(`${apiBaseUrl}/public/contact`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: formData.name,
          email: formData.email,
          company: formData.linkedin,
          phone: formData.phone,
          message: formData.message || null,
          website: null,
        }),
      });

      if (!response.ok) {
        let detail = "Impossible d'envoyer le message.";
        try {
          const errorPayload = await response.json();
          if (typeof errorPayload?.detail === "string") {
            detail = errorPayload.detail;
          }
        } catch {
          // ignore JSON parse errors
        }

        toast({
          title: "Erreur d'envoi",
          description: detail,
          variant: "destructive",
        });
        return;
      }

      setFormData({
        name: "",
        email: "",
        linkedin: "",
        phone: "",
        message: "",
      });
      setIsSuccessDialogOpen(true);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  return (
    <section id="contact" className="py-20 bg-muted/50">
      <div className="container mx-auto px-4">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              Essai gratuit 14 jours
            </h2>
            <p className="text-lg text-muted-foreground">
              Découvrez la qualité de nos données gratuitement
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            <div className="md:col-span-2">
              <Card className="p-8">
                <form onSubmit={handleSubmit} className="space-y-6">
                  <div className="grid md:grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="name">Nom complet *</Label>
                      <Input
                        id="name"
                        name="name"
                        value={formData.name}
                        onChange={handleChange}
                        required
                        placeholder="Jean Dupont"
                      />
                    </div>
                    <div>
                      <Label htmlFor="email">Email professionnel *</Label>
                      <Input
                        id="email"
                        name="email"
                        type="email"
                        value={formData.email}
                        onChange={handleChange}
                        required
                        placeholder="jean@entreprise.fr"
                      />
                    </div>
                  </div>

                  <div className="grid md:grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="linkedin">LinkedIn *</Label>
                      <Input
                        id="linkedin"
                        name="linkedin"
                        value={formData.linkedin}
                        onChange={handleChange}
                        required
                        placeholder="https://www.linkedin.com/company/votre-entreprise"
                      />
                    </div>
                    <div>
                      <Label htmlFor="phone">Téléphone *</Label>
                      <Input
                        id="phone"
                        name="phone"
                        type="tel"
                        value={formData.phone}
                        onChange={handleChange}
                        required
                        placeholder="+33 6 12 34 56 78"
                      />
                    </div>
                  </div>

                  <div>
                    <Label htmlFor="message">
                      Parlez-nous de vos besoins (optionnel)
                    </Label>
                    <Textarea
                      id="message"
                      name="message"
                      value={formData.message}
                      onChange={handleChange}
                      rows={4}
                      placeholder="Secteurs d'activité à surveiller, questions..."
                    />
                  </div>

                  <Button
                    type="submit"
                    size="lg"
                    className="w-full"
                    disabled={isSubmitting || isInCooldown}
                  >
                    {isSubmitting ? (
                      <>
                        <span
                          className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
                          aria-hidden="true"
                        />
                        <span className="sr-only">Envoi en cours...</span>
                      </>
                    ) : (
                      "Envoyer ma demande d'essai gratuit"
                    )}
                  </Button>

                  <p className="text-xs text-muted-foreground text-center">
                    Vos données sont protégées et ne seront jamais partagées
                  </p>
                </form>
              </Card>
            </div>

            <div className="space-y-6">
              <Card className="p-6">
                <div className="flex items-start gap-4">
                  <div className="w-10 h-10 bg-secondary/10 rounded-lg flex items-center justify-center flex-shrink-0">
                    <Mail className="w-5 h-5 text-secondary" />
                  </div>
                  <div>
                    <h3 className="font-semibold mb-1">Email</h3>
                    <a
                      href="mailto:contact@business-tracker.fr"
                      className="text-sm text-muted-foreground hover:text-secondary transition-colors"
                    >
                      contact@business-tracker.fr
                    </a>
                  </div>
                </div>
              </Card>

              <Card className="p-6">
                <div className="flex items-start gap-4">
                  <div className="w-10 h-10 bg-secondary/10 rounded-lg flex items-center justify-center flex-shrink-0">
                    <Phone className="w-5 h-5 text-secondary" />
                  </div>
                  <div>
                    <h3 className="font-semibold mb-1">WhatsApp</h3>
                    <a
                      href="https://wa.me/33699042706"
                      className="text-sm text-muted-foreground hover:text-secondary transition-colors"
                    >
                      +33 6 99 04 27 06
                    </a>
                  </div>
                </div>
              </Card>

              <Card className="p-6">
                <div className="flex items-start gap-4">
                  <div className="w-10 h-10 bg-secondary/10 rounded-lg flex items-center justify-center flex-shrink-0">
                    <MapPin className="w-5 h-5 text-secondary" />
                  </div>
                  <div>
                    <h3 className="font-semibold mb-1">Siège social</h3>
                    <p className="text-sm text-muted-foreground">
                      Paris, France
                    </p>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        </div>
      </div>
      <Dialog open={isSuccessDialogOpen} onOpenChange={setIsSuccessDialogOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Message envoyé</DialogTitle>
            <DialogDescription>
              Merci ! Votre demande a bien été envoyée. Nous revenons vers vous très vite.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" onClick={() => setIsSuccessDialogOpen(false)}>
              Fermer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
};

export default ContactForm;
