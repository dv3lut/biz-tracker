# Stripe — scénarios de tests (end‑to‑end)

Ce document décrit **comment tester de bout en bout** l’essai gratuit, le passage au payant, la résiliation et l’upgrade (avec proratisation), **en mode test Stripe**.

## Pré‑requis

- Backend lancé (http://localhost:8080).
- Landing lancée (http://localhost:8082).
- Variables d’env renseignées (mode test) :
  - `STRIPE__SECRET_KEY=sk_test_...`
  - `STRIPE__WEBHOOK_SECRET=whsec_...`
  - `STRIPE__PRICE_IDS={"starter":"price_...","business":"price_..."}`
  - `STRIPE__UPGRADE_URL=https://business-tracker.fr/upgrade` (ou URL locale si besoin)
  - `STRIPE__PORTAL_RETURN_URL=.../upgrade`

## 1) Créer les produits (mode test)

1. Dashboard Stripe → **Test mode** activé.
2. **Products** → **Add product**.
3. Créer “Starter” :
   - Prix : 56€
   - Récurrence : Monthly
4. Copier l’ID `price_...`.
5. Créer “Business” :
   - Prix : 128€
   - Récurrence : Monthly
6. Copier l’ID `price_...`.
7. Mettre à jour `STRIPE__PRICE_IDS`.

> L’essai gratuit de 14 jours est défini côté code (`trial_period_days=14`).

## 2) Configurer le webhook (mode test)

1. **Developers → Webhooks → Add endpoint**.
2. URL : `https://<ton-backend>/public/stripe/webhook`.
3. Events :
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
4. Copier le **Signing secret** `whsec_...` dans `STRIPE__WEBHOOK_SECRET`.

## 3) Scénario A — Essai gratuit (checkout)

1. Landing → Section “Tarifs”.
2. Choisir “Starter” ou “Business”.
3. Sélectionner 1 ou 3 catégories.
4. Remplir email + nom + entreprise.
5. Checkout Stripe → utiliser une carte de test (ex: 4242 4242 4242 4242).

**Vérifications**
- Stripe Dashboard → Subscription : status **trialing**.
- Backend : un client est créé en base avec destinataire email.
- Page /upgrade accessible.

## 4) Scénario B — Fin d’essai → passage au payant

### Option 1 (simple, sans avance de temps)
- Attendre la fin de l’essai (ou modifier manuellement la date dans Stripe si besoin).

### Option 2 (avancée, Test Clock — recommandé)

> Pour simuler le temps qui passe, Stripe impose d’utiliser un **Test Clock**.

**Étapes (avec Stripe CLI)**
1. Créer un Test Clock :
   ```bash
   stripe test_helpers test_clocks create --frozen_time=$(date +%s)
   ```
2. Créer un customer rattaché au clock :
   ```bash
   stripe customers create \
     --email="test@entreprise.fr" \
     --test-clock=TEST_CLOCK_ID
   ```
3. Créer une subscription rattachée au customer :
   ```bash
   stripe subscriptions create \
     --customer=CUSTOMER_ID \
     --items[0][price]=price_starter \
     --trial_period_days=14 \
     --metadata[plan_key]=starter \
     --metadata[category_ids]='["<UUID_CAT>"]'
   ```
4. Avancer le temps de 15 jours :
   ```bash
   stripe test_helpers test_clocks advance \
     --test-clock=TEST_CLOCK_ID \
     --frozen_time=$(date -v+15d +%s)
   ```

**Vérifications**
- Stripe : la subscription passe à **active**, facture générée.
- Backend : webhook `customer.subscription.updated` reçu.

## 5) Scénario C — Résiliation (fin de période)

1. Page /upgrade → ouvrir le portail Stripe.
2. Annuler l’abonnement “à la fin de période”.

**Vérifications**
- Stripe : `cancel_at_period_end=true`.
- Backend : `end_date` renseignée à la fin de période.

## 6) Scénario D — Upgrade / Downgrade + proratisation

1. Page /upgrade → choisir nouveau plan + catégories.
2. Valider.

**Vérifications**
- Stripe : facture de proratisation générée.
- Backend :
  - `stripe_plan_key` mis à jour,
  - nouvelles catégories appliquées.

> Si Stripe renvoie une facture, l’utilisateur est redirigé vers l’URL de paiement.

## 7) Scénario E — Accès portail client

1. Page /upgrade → entrer email → “Ouvrir le portail”.
2. Vérifier : factures, moyens de paiement, résiliation.

---

## Conseils pratiques

- Pour simuler “temps qui passe”, privilégier **Test Clocks**.
- Pour tester les webhooks sans attendre :
  ```bash
  stripe trigger checkout.session.completed
  stripe trigger customer.subscription.updated
  stripe trigger customer.subscription.deleted
  ```
- Si tu utilises Stripe CLI, vérifie que `stripe login` est fait dans le compte Business Tracker (mode test).

---

## Passage en production

1. Refaire la création produits/prix en **Live mode**.
2. Créer un webhook live.
3. Mettre à jour `.env` avec `sk_live_...`, `whsec_...`, `price_...` live.
4. Déployer backend + landing.
