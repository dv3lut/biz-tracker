-- ============================================================
-- Insertion des catégories NAF et sous-catégories
-- Date : 2026-04-13
-- Règles : is_active = true, price_cents = 0, keywords = ["establishments"]
-- ============================================================

-- 1. Catégories
INSERT INTO naf_categories (id, name, description, keywords, created_at, updated_at)
VALUES
  (gen_random_uuid(), '🏠 Immobilier',                          'Activités liées à la transaction, la gestion, l''administration et la valorisation de biens immobiliers résidentiels ou professionnels.', '["establishments"]', NOW(), NOW()),
  (gen_random_uuid(), '🏗️ BTP / Construction',                  'Entreprises intervenant dans la construction, le gros œuvre et les travaux principaux sur les bâtiments et ouvrages.',                  '["establishments"]', NOW(), NOW()),
  (gen_random_uuid(), '⚡ Électricité',                         'Professionnels réalisant l''installation, la mise en conformité et la maintenance des équipements électriques dans les bâtiments et infrastructures.', '["establishments"]', NOW(), NOW()),
  (gen_random_uuid(), '🚿 Plomberie / Chauffage / Climatisation','Acteurs spécialisés dans les réseaux d''eau, de gaz, le chauffage, la ventilation et les équipements de climatisation.',               '["establishments"]', NOW(), NOW()),
  (gen_random_uuid(), '🪚 Menuiserie',                          'Entreprises réalisant la fabrication, la pose ou l''aménagement d''éléments en bois, métal ou matériaux associés pour l''habitat et les locaux professionnels.', '["establishments"]', NOW(), NOW()),
  (gen_random_uuid(), '🏢 Architecture',                        'Professionnels de la conception de bâtiments, de l''aménagement des espaces et du conseil architectural.',                                '["establishments"]', NOW(), NOW()),
  (gen_random_uuid(), '🧪 Ingénierie / Bureau d''études',       'Structures techniques accompagnant les projets par l''étude, la conception, l''analyse et l''expertise sur des sujets industriels, techniques ou réglementaires.', '["establishments"]', NOW(), NOW()),
  (gen_random_uuid(), '🎨 Design / Création',                   'Activités centrées sur la création visuelle, l''identité graphique, le design d''espaces, de produits ou de supports de communication.',  '["establishments"]', NOW(), NOW()),
  (gen_random_uuid(), '📞 Communication / Conseil',             'Cabinets et agences accompagnant les entreprises sur leur stratégie, leur organisation, leur image et leur communication.',               '["establishments"]', NOW(), NOW()),
  (gen_random_uuid(), '🧑‍💼 Recrutement / RH',                   'Acteurs spécialisés dans le recrutement, l''intérim, la mise à disposition de personnel et l''accompagnement en ressources humaines.',  '["establishments"]', NOW(), NOW()),
  (gen_random_uuid(), '🚚 Transport / Logistique',              'Entreprises dédiées au transport de marchandises, à l''acheminement, à l''organisation logistique et aux services de livraison.',         '["establishments"]', NOW(), NOW()),
  (gen_random_uuid(), '🚖 Taxi / VTC',                         'Professionnels du transport de personnes, avec ou sans réservation, pour des trajets ponctuels ou réguliers.',                            '["establishments"]', NOW(), NOW()),
  (gen_random_uuid(), '🏨 Hôtellerie / Hébergement',           'Établissements proposant des solutions d''accueil et d''hébergement de courte ou moyenne durée pour particuliers et voyageurs.',           '["establishments"]', NOW(), NOW()),
  (gen_random_uuid(), '✈️ Voyage / Tourisme',                   'Acteurs de l''organisation de séjours, de réservations, de distribution d''offres touristiques et d''accompagnement au voyage.',          '["establishments"]', NOW(), NOW()),
  (gen_random_uuid(), '💇 Coiffure / Beauté',                   'Professionnels des services esthétiques, du soin, de la coiffure et du bien-être destinés aux particuliers.',                             '["establishments"]', NOW(), NOW()),
  (gen_random_uuid(), '🏋️ Sport / Fitness',                     'Structures proposant des activités physiques, sportives ou de loisirs, en club, en salle ou dans un cadre encadré.',                     '["establishments"]', NOW(), NOW()),
  (gen_random_uuid(), '🩺 Santé',                               'Professionnels et établissements intervenant dans les soins, le suivi médical, la rééducation et les prestations de santé.',               '["establishments"]', NOW(), NOW()),
  (gen_random_uuid(), '💊 Pharmacie',                           'Commerces spécialisés dans la délivrance de produits pharmaceutiques et de solutions liées à la santé du quotidien.',                    '["establishments"]', NOW(), NOW()),
  (gen_random_uuid(), '🐶 Vétérinaire',                         'Professionnels assurant les soins, le suivi médical et l''accompagnement de santé des animaux.',                                         '["establishments"]', NOW(), NOW()),
  (gen_random_uuid(), '🧹 Nettoyage / Services aux bâtiments',  'Entreprises intervenant dans l''entretien, le nettoyage, la maintenance courante et certains services liés aux bâtiments et espaces extérieurs.', '["establishments"]', NOW(), NOW()),
  (gen_random_uuid(), '🛒 Commerce alimentaire spécialisé',     'Commerces de détail spécialisés dans la vente de produits alimentaires ciblés, frais ou préparés, hors grande distribution généraliste.',  '["establishments"]', NOW(), NOW()),
  (gen_random_uuid(), '👗 Mode / Habillement',                  'Enseignes et commerces dédiés à la vente de vêtements, chaussures, accessoires et articles de mode.',                                    '["establishments"]', NOW(), NOW()),
  (gen_random_uuid(), '🪑 Ameublement / Décoration',            'Acteurs proposant du mobilier, des équipements de la maison et des solutions d''aménagement ou de décoration intérieure.',                '["establishments"]', NOW(), NOW()),
  (gen_random_uuid(), '🔧 Réparation automobile / Garage',      'Professionnels de l''entretien, de la réparation, du diagnostic et du contrôle de véhicules automobiles.',                               '["establishments"]', NOW(), NOW())
ON CONFLICT (name) DO NOTHING;


-- 2. Sous-catégories (codes NAF uniques)
-- 74.10Z est partagé entre "🎨 Design / Création" et "🪑 Ameublement / Décoration" → inséré une seule fois
INSERT INTO naf_subcategories (id, name, naf_code, price_cents, is_active, created_at, updated_at)
VALUES
  -- Immobilier
  (gen_random_uuid(), 'Agences immobilières',                                                                                 '68.31Z', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Administration d''immeubles et autres biens immobiliers',                                              '68.32A', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Supports juridiques de gestion de patrimoine immobilier',                                              '68.32B', 0, true, NOW(), NOW()),
  -- BTP / Construction
  (gen_random_uuid(), 'Construction de maisons individuelles',                                                                '41.20A', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Construction d''autres bâtiments',                                                                    '41.20B', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Travaux de maçonnerie générale et gros œuvre de bâtiment',                                            '43.99C', 0, true, NOW(), NOW()),
  -- Électricité
  (gen_random_uuid(), 'Travaux d''installation électrique dans tous locaux',                                                  '43.21A', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Travaux d''installation électrique sur la voie publique',                                              '43.21B', 0, true, NOW(), NOW()),
  -- Plomberie / Chauffage / Climatisation
  (gen_random_uuid(), 'Travaux d''installation d''eau et de gaz en tous locaux',                                              '43.22A', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Travaux d''installation d''équipements thermiques et de climatisation',                                '43.22B', 0, true, NOW(), NOW()),
  -- Menuiserie
  (gen_random_uuid(), 'Travaux de menuiserie bois et PVC',                                                                   '43.32A', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Travaux de menuiserie métallique et serrurerie',                                                      '43.32B', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Agencement de lieux de vente',                                                                        '43.32C', 0, true, NOW(), NOW()),
  -- Architecture
  (gen_random_uuid(), 'Activités d''architecture',                                                                           '71.11Z', 0, true, NOW(), NOW()),
  -- Ingénierie / Bureau d'études
  (gen_random_uuid(), 'Activité des géomètres',                                                                              '71.12A', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Ingénierie, études techniques',                                                                       '71.12B', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Analyses, essais et inspections techniques',                                                          '71.20B', 0, true, NOW(), NOW()),
  -- Design / Création (74.10Z partagé avec Ameublement)
  (gen_random_uuid(), 'Activités spécialisées de design',                                                                    '74.10Z', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Activités photographiques',                                                                           '74.20Z', 0, true, NOW(), NOW()),
  -- Communication / Conseil
  (gen_random_uuid(), 'Conseil en relations publiques et communication',                                                     '70.21Z', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Conseil pour les affaires et autres conseils de gestion',                                             '70.22Z', 0, true, NOW(), NOW()),
  -- Recrutement / RH
  (gen_random_uuid(), 'Activités des agences de placement de main-d''œuvre',                                                 '78.10Z', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Activités des agences de travail temporaire',                                                         '78.20Z', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Autre mise à disposition de ressources humaines',                                                     '78.30Z', 0, true, NOW(), NOW()),
  -- Transport / Logistique
  (gen_random_uuid(), 'Transports routiers de fret interurbains',                                                            '49.41A', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Transports routiers de fret de proximité',                                                            '49.41B', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Messagerie, fret express',                                                                            '52.29A', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Affrètement et organisation des transports',                                                          '52.29B', 0, true, NOW(), NOW()),
  -- Taxi / VTC
  (gen_random_uuid(), 'Transports de voyageurs par taxis',                                                                   '49.32Z', 0, true, NOW(), NOW()),
  -- Hôtellerie / Hébergement
  (gen_random_uuid(), 'Hôtels et hébergement similaire',                                                                     '55.10Z', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Hébergement touristique et autre hébergement de courte durée',                                        '55.20Z', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Terrains de camping et parcs pour caravanes ou véhicules de loisirs',                                 '55.30Z', 0, true, NOW(), NOW()),
  -- Voyage / Tourisme
  (gen_random_uuid(), 'Activités des agences de voyage',                                                                     '79.11Z', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Activités des voyagistes',                                                                            '79.12Z', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Autres services de réservation et activités connexes',                                                '79.90Z', 0, true, NOW(), NOW()),
  -- Coiffure / Beauté
  (gen_random_uuid(), 'Coiffure',                                                                                            '96.02A', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Soins de beauté',                                                                                     '96.02B', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Entretien corporel',                                                                                  '96.04Z', 0, true, NOW(), NOW()),
  -- Sport / Fitness
  (gen_random_uuid(), 'Activités des centres de culture physique',                                                           '93.13Z', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Activités de clubs de sports',                                                                        '93.12Z', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Autres activités récréatives et de loisirs',                                                          '93.29Z', 0, true, NOW(), NOW()),
  -- Santé
  (gen_random_uuid(), 'Activité des médecins généralistes',                                                                  '86.21Z', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Activités de radiodiagnostic et de radiothérapie',                                                    '86.22A', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Pratique dentaire',                                                                                   '86.23Z', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Activités des professionnels de la rééducation, de l''appareillage et des pédicures-podologues',      '86.90E', 0, true, NOW(), NOW()),
  -- Pharmacie
  (gen_random_uuid(), 'Commerce de détail de produits pharmaceutiques en magasin spécialisé',                                '47.73Z', 0, true, NOW(), NOW()),
  -- Vétérinaire
  (gen_random_uuid(), 'Activités vétérinaires',                                                                              '75.00Z', 0, true, NOW(), NOW()),
  -- Nettoyage / Services aux bâtiments
  (gen_random_uuid(), 'Activités combinées de soutien lié aux bâtiments',                                                   '81.10Z', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Nettoyage courant des bâtiments',                                                                     '81.21Z', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Autres activités de nettoyage des bâtiments et nettoyage industriel',                                 '81.22Z', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Services d''aménagement paysager',                                                                    '81.30Z', 0, true, NOW(), NOW()),
  -- Commerce alimentaire spécialisé
  (gen_random_uuid(), 'Commerce de détail de poissons, crustacés et mollusques en magasin spécialisé',                       '47.23Z', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Commerce de détail de pain, pâtisserie et confiserie en magasin spécialisé',                          '47.24Z', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Autres commerces de détail alimentaires en magasin spécialisé',                                       '47.29Z', 0, true, NOW(), NOW()),
  -- Mode / Habillement
  (gen_random_uuid(), 'Commerce de détail d''habillement en magasin spécialisé',                                             '47.71Z', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Commerce de détail de la chaussure',                                                                  '47.72A', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Commerce de détail de maroquinerie et d''articles de voyage',                                         '47.72B', 0, true, NOW(), NOW()),
  -- Ameublement / Décoration
  (gen_random_uuid(), 'Commerce de détail de meubles',                                                                      '47.59A', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Commerce de détail d''autres équipements du foyer',                                                   '47.59B', 0, true, NOW(), NOW()),
  -- Réparation automobile / Garage
  (gen_random_uuid(), 'Entretien et réparation de véhicules automobiles légers',                                             '45.20A', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Entretien et réparation d''autres véhicules automobiles',                                             '45.20B', 0, true, NOW(), NOW()),
  (gen_random_uuid(), 'Contrôle technique automobile',                                                                       '71.20A', 0, true, NOW(), NOW())
ON CONFLICT (naf_code) DO NOTHING;


-- 3. Liaisons catégorie ↔ sous-catégorie
-- Note : 74.10Z est lié à la fois à "🎨 Design / Création" et "🪑 Ameublement / Décoration"
INSERT INTO naf_category_subcategories (category_id, subcategory_id, created_at)
SELECT c.id, s.id, NOW()
FROM (VALUES
  -- Immobilier
  ('🏠 Immobilier',                          '68.31Z'),
  ('🏠 Immobilier',                          '68.32A'),
  ('🏠 Immobilier',                          '68.32B'),
  -- BTP / Construction
  ('🏗️ BTP / Construction',                  '41.20A'),
  ('🏗️ BTP / Construction',                  '41.20B'),
  ('🏗️ BTP / Construction',                  '43.99C'),
  -- Électricité
  ('⚡ Électricité',                         '43.21A'),
  ('⚡ Électricité',                         '43.21B'),
  -- Plomberie / Chauffage / Climatisation
  ('🚿 Plomberie / Chauffage / Climatisation','43.22A'),
  ('🚿 Plomberie / Chauffage / Climatisation','43.22B'),
  -- Menuiserie
  ('🪚 Menuiserie',                          '43.32A'),
  ('🪚 Menuiserie',                          '43.32B'),
  ('🪚 Menuiserie',                          '43.32C'),
  -- Architecture
  ('🏢 Architecture',                        '71.11Z'),
  -- Ingénierie / Bureau d'études
  ('🧪 Ingénierie / Bureau d''études',       '71.12A'),
  ('🧪 Ingénierie / Bureau d''études',       '71.12B'),
  ('🧪 Ingénierie / Bureau d''études',       '71.20B'),
  -- Design / Création
  ('🎨 Design / Création',                   '74.10Z'),
  ('🎨 Design / Création',                   '74.20Z'),
  -- Communication / Conseil
  ('📞 Communication / Conseil',             '70.21Z'),
  ('📞 Communication / Conseil',             '70.22Z'),
  -- Recrutement / RH
  ('🧑‍💼 Recrutement / RH',                   '78.10Z'),
  ('🧑‍💼 Recrutement / RH',                   '78.20Z'),
  ('🧑‍💼 Recrutement / RH',                   '78.30Z'),
  -- Transport / Logistique
  ('🚚 Transport / Logistique',              '49.41A'),
  ('🚚 Transport / Logistique',              '49.41B'),
  ('🚚 Transport / Logistique',              '52.29A'),
  ('🚚 Transport / Logistique',              '52.29B'),
  -- Taxi / VTC
  ('🚖 Taxi / VTC',                         '49.32Z'),
  -- Hôtellerie / Hébergement
  ('🏨 Hôtellerie / Hébergement',           '55.10Z'),
  ('🏨 Hôtellerie / Hébergement',           '55.20Z'),
  ('🏨 Hôtellerie / Hébergement',           '55.30Z'),
  -- Voyage / Tourisme
  ('✈️ Voyage / Tourisme',                   '79.11Z'),
  ('✈️ Voyage / Tourisme',                   '79.12Z'),
  ('✈️ Voyage / Tourisme',                   '79.90Z'),
  -- Coiffure / Beauté
  ('💇 Coiffure / Beauté',                   '96.02A'),
  ('💇 Coiffure / Beauté',                   '96.02B'),
  ('💇 Coiffure / Beauté',                   '96.04Z'),
  -- Sport / Fitness
  ('🏋️ Sport / Fitness',                     '93.13Z'),
  ('🏋️ Sport / Fitness',                     '93.12Z'),
  ('🏋️ Sport / Fitness',                     '93.29Z'),
  -- Santé
  ('🩺 Santé',                               '86.21Z'),
  ('🩺 Santé',                               '86.22A'),
  ('🩺 Santé',                               '86.23Z'),
  ('🩺 Santé',                               '86.90E'),
  -- Pharmacie
  ('💊 Pharmacie',                           '47.73Z'),
  -- Vétérinaire
  ('🐶 Vétérinaire',                         '75.00Z'),
  -- Nettoyage / Services aux bâtiments
  ('🧹 Nettoyage / Services aux bâtiments',  '81.10Z'),
  ('🧹 Nettoyage / Services aux bâtiments',  '81.21Z'),
  ('🧹 Nettoyage / Services aux bâtiments',  '81.22Z'),
  ('🧹 Nettoyage / Services aux bâtiments',  '81.30Z'),
  -- Commerce alimentaire spécialisé
  ('🛒 Commerce alimentaire spécialisé',     '47.23Z'),
  ('🛒 Commerce alimentaire spécialisé',     '47.24Z'),
  ('🛒 Commerce alimentaire spécialisé',     '47.29Z'),
  -- Mode / Habillement
  ('👗 Mode / Habillement',                  '47.71Z'),
  ('👗 Mode / Habillement',                  '47.72A'),
  ('👗 Mode / Habillement',                  '47.72B'),
  -- Ameublement / Décoration (74.10Z partagé)
  ('🪑 Ameublement / Décoration',            '47.59A'),
  ('🪑 Ameublement / Décoration',            '47.59B'),
  ('🪑 Ameublement / Décoration',            '74.10Z'),
  -- Réparation automobile / Garage
  ('🔧 Réparation automobile / Garage',      '45.20A'),
  ('🔧 Réparation automobile / Garage',      '45.20B'),
  ('🔧 Réparation automobile / Garage',      '71.20A')
) AS mapping(cat_name, naf_code)
JOIN naf_categories c ON c.name = mapping.cat_name
JOIN naf_subcategories s ON s.naf_code = mapping.naf_code
ON CONFLICT (category_id, subcategory_id) DO NOTHING;


-- 4. Mise à jour des descriptions des catégories existantes
UPDATE naf_categories SET description = 'Professionnels du droit, du conseil juridique et de l''accompagnement sur les sujets contractuels, réglementaires ou contentieux.',                                                  updated_at = NOW() WHERE name = '⚖️ Juridique';
UPDATE naf_categories SET description = 'Commerces spécialisés dans la vente de fruits et légumes frais, en magasin, sur marché ou en circuit de distribution dédié.',                                                       updated_at = NOW() WHERE name = '🍎 Primeur';
UPDATE naf_categories SET description = 'Acteurs proposant la préparation et la fourniture de repas, buffets ou prestations culinaires pour événements, entreprises ou particuliers.',                                        updated_at = NOW() WHERE name = '🍱 Traiteur';
UPDATE naf_categories SET description = 'Établissements proposant des repas ou des boissons sur place, à emporter ou en service rapide, du restaurant au café.',                                                              updated_at = NOW() WHERE name = '🍽️ Restauration';
UPDATE naf_categories SET description = 'Entreprises spécialisées dans le développement logiciel, les services numériques, la maintenance informatique et le conseil en systèmes d''information.',                           updated_at = NOW() WHERE name = '💻 Informatique';
UPDATE naf_categories SET description = 'Structures accompagnant les entreprises dans la tenue comptable, la gestion financière, les obligations fiscales et le suivi administratif.',                                        updated_at = NOW() WHERE name = '📊 Comptabilité';
UPDATE naf_categories SET description = 'Agences et prestataires intervenant sur la communication, la promotion de marque, la diffusion publicitaire et les études de marché.',                                               updated_at = NOW() WHERE name = '📣 Publicité';
UPDATE naf_categories SET description = 'Acteurs de l''assurance, du courtage et des services associés, intervenant dans la protection des biens, des personnes et des activités professionnelles.',                         updated_at = NOW() WHERE name = '🛡️ Assurance';
UPDATE naf_categories SET description = 'Professionnels de la fabrication et de la vente de pain, viennoiseries, pâtisseries et produits boulangers.',                                                                       updated_at = NOW() WHERE name = '🥖 Boulangerie';
UPDATE naf_categories SET description = 'Commerces et activités spécialisées dans la préparation, la transformation et la vente de viandes, charcuteries et produits associés.',                                             updated_at = NOW() WHERE name = '🥩 Boucherie';
