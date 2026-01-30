import { useEffect, useState } from "react";

import Hero from "@/components/Hero";
import HowItWorks from "@/components/HowItWorks";
import TargetAudience from "@/components/TargetAudience";
import WhatYouGet from "@/components/WhatYouGet";
import Benefits from "@/components/Benefits";
import Pricing from "@/components/Pricing";
import FAQ from "@/components/FAQ";
import ContactForm from "@/components/ContactForm";
import Footer from "@/components/Footer";

const DEFAULT_TRIAL_PERIOD_DAYS = 14;

const Index = () => {
  const apiBaseUrl = (import.meta.env.VITE_APP_API_BASE_URL ?? "").replace(/\/$/, "");
  const [trialPeriodDays, setTrialPeriodDays] = useState(DEFAULT_TRIAL_PERIOD_DAYS);

  useEffect(() => {
    const controller = new AbortController();

    const loadStripeSettings = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/public/stripe/settings`, {
          signal: controller.signal,
        });
        if (!response.ok) {
          return;
        }
        const payload = (await response.json()) as { trial_period_days?: number };
        if (typeof payload.trial_period_days === "number") {
          setTrialPeriodDays(payload.trial_period_days);
        }
      } catch {
        // Ignore les erreurs réseau pour conserver la valeur par défaut.
      }
    };

    loadStripeSettings();
    return () => controller.abort();
  }, [apiBaseUrl]);

  return (
    <div className="min-h-screen">
      <Hero />
      <HowItWorks />
      <TargetAudience />
      <WhatYouGet />
      <Benefits />
      <Pricing trialPeriodDays={trialPeriodDays} />
      <FAQ trialPeriodDays={trialPeriodDays} />
      <ContactForm />
      <Footer />
    </div>
  );
};

export default Index;
