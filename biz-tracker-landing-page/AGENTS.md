# Agents — Business tracker Landing Page

Ce dossier contient la landing page marketing (Vite + React) de Business tracker.

## Architecture

- `src/pages/Index.tsx` : page d'accueil (assemble Hero, Pricing, FAQ, etc.).
- `src/components/ContactForm.tsx` : formulaire de contact (lead capture).
- `src/components/ui/*` : composants UI (shadcn).
- `vite.config.ts` : configuration Vite (dev server, alias `@`).

## Variables d'environnement

- `VITE_APP_API_BASE_URL` : base URL du backend (ex: `http://localhost:8080` en local, `https://api.business-tracker.fr` en prod).

> Note: si la variable n'est pas définie, le formulaire utilisera une URL relative et appellera le port de la landing (ex: `localhost:8082`).

## Flux email (formulaire landing)

1. L'utilisateur valide le formulaire dans `ContactForm.tsx`.
2. La landing envoie une requête HTTP : `POST {VITE_APP_API_BASE_URL}/public/contact`.
3. Le backend (route publique) construit un corps d'email avec les champs du formulaire.
4. Le backend envoie **un seul email** vers l'inbox configurée `contact@business-tracker.fr`.
   - L'adresse de destination est contrôlée par `PUBLIC_CONTACT__INBOX_ADDRESS`.
   - Le header `Reply-To` est positionné sur l'email saisi dans le formulaire.
5. Côté OVH, des redirections peuvent être mises en place pour distribuer `contact@...` vers les admins.

### Pourquoi le reply marche "comme contact@" ?

- Tu lis le message reçu à `contact@business-tracker.fr`.
- Quand tu cliques **Répondre**, ton client mail répond au `Reply-To` (le prospect).
- Si tu configures ton client pour envoyer "From: contact@business-tracker.fr" (alias Gmail ou SMTP OVH), le prospect verra `contact@business-tracker.fr` comme expéditeur.

## OVH: redirections et "répondre en tant que contact@"

Objectif: recevoir les leads sur ton adresse admin (via redirection OVH) mais pouvoir répondre en affichant `contact@business-tracker.fr`.

### 1) Mettre en place la réception (OVH)

- Dans OVH Manager → Emails (selon ton offre: MX Plan / Email Pro / Exchange) → Redirections.
- Crée une redirection: `contact@business-tracker.fr` → `ton-admin@...`.

Après ça, tout mail envoyé à `contact@...` arrive dans ta boîte admin.

### 2) Répondre en affichant `contact@business-tracker.fr` (cas Gmail recommandé)

Pré-requis: il faut un serveur SMTP autorisé à envoyer pour `business-tracker.fr`.

Option la plus simple: créer une vraie boîte OVH `contact@business-tracker.fr` (même si tu ne l'utilises pas pour lire) et utiliser ses identifiants SMTP.

Étapes (Gmail):

1. Ouvre Gmail avec ton compte admin.
2. ⚙️ Paramètres → "Voir tous les paramètres".
3. Onglet "Comptes et importation".
4. Section "Envoyer des e-mails en tant que" → "Ajouter une autre adresse e-mail".
5. Adresse: `contact@business-tracker.fr`.
6. Choisir "Envoyer via un serveur SMTP".
7. Renseigner les paramètres SMTP OVH (donnés par OVH dans la fiche de la boîte `contact@`):
   - Serveur SMTP (ex: `ssl0.ovh.net` / `smtp.ovh.net` selon offre)
   - Port 587 (STARTTLS) ou 465 (SSL)
   - Identifiant: `contact@business-tracker.fr`
   - Mot de passe: celui de la boîte `contact@...`
8. Gmail envoie un email de validation à `contact@...`.
   - Comme tu as une redirection OVH, tu reçois le code dans ta boîte admin.
   - Copie/colle le code pour valider l'adresse.
9. Optionnel: coche "Répondre à partir de la même adresse à laquelle le message a été envoyé".

Résultat:
- Tu lis les leads dans ta boîte admin.
- Tu réponds en choisissant "De: contact@business-tracker.fr".
- Le prospect voit `contact@business-tracker.fr` comme expéditeur.

### Notes importantes

- Le backend positionne `Reply-To` sur l'email du prospect: le bouton "Répondre" vise bien le lead.
- Sans configuration SMTP (ou si Gmail n'est pas autorisé), tu risques un "via gmail.com" ou un expéditeur non conforme.

## Développement local

- Lancer le backend: `cd biz-tracker-back && python -m app serve` (ou via launch VS Code).
- Lancer la landing: `cd biz-tracker-landing-page && npm run dev`.

Par défaut le dev server Vite est configuré sur le port `8082`.

## Dépannage

- Si la landing appelle `localhost:8082` au lieu du backend: vérifier que `VITE_APP_API_BASE_URL` est bien défini et que le serveur Vite a été redémarré.
- Si l'API renvoie `503`: vérifier la config SMTP du backend (`EMAIL__*`) et `PUBLIC_CONTACT__INBOX_ADDRESS`.
