export type SectionKey =
  | "dashboard"
  | "sync"
  | "alerts"
  | "clients"
  | "naf-config"
  | "emails"
  | "tools"
  | "billing"
  | "establishments"
  | "analytics";

export interface SectionDefinition {
  key: SectionKey;
  label: string;
  description?: string;
  icon?: string;
}

export const NAV_SECTIONS: ReadonlyArray<SectionDefinition> = [
  { key: "dashboard", label: "Tableau de bord", description: "Vue synthétique" },
  { key: "analytics", label: "Statistiques", description: "Analytics par NAF" },
  { key: "sync", label: "Synchronisations", description: "Historique & états" },
  { key: "alerts", label: "Alertes", description: "Suivi des notifications" },
  { key: "clients", label: "Clients", description: "Destinataires par client" },
  { key: "naf-config", label: "Config NAF", description: "Catégories et souscriptions" },
  { key: "emails", label: "E-mails", description: "Configuration & tests" },
  { key: "tools", label: "Outils", description: "Utilitaires de développement" },
  { key: "billing", label: "Facturation", description: "Essai Stripe" },
  { key: "establishments", label: "Etablissements", description: "Recherche & actions" },
];
