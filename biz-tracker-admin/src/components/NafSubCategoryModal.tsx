import { FormEvent, useEffect, useMemo, useState } from "react";

import type { NafCategory, NafSubCategory } from "../types";

export type NafSubCategoryFormPayload = {
  categoryId: string;
  mode: "create" | "attach";
  existingSubcategoryId?: string;
  name: string;
  description: string | null;
  nafCode: string;
  priceEur?: number;
  isActive: boolean;
  autoEmailEnabled: boolean;
  autoEmailSubject: string | null;
  autoEmailBody: string | null;
};

type FormState = {
  categoryId: string;
  mode: "create" | "attach";
  existingSubcategoryId: string;
  name: string;
  description: string;
  nafCode: string;
  priceEur: string;
  isActive: boolean;
  autoEmailEnabled: boolean;
  autoEmailSubject: string;
  autoEmailBody: string;
};

type Props = {
  isOpen: boolean;
  mode: "create" | "edit";
  categories: NafCategory[];
  existingSubcategories: NafSubCategory[];
  subcategory: NafSubCategory | null;
  initialCategoryId?: string;
  onSubmit: (payload: NafSubCategoryFormPayload) => void;
  onCancel: () => void;
  isProcessing: boolean;
};

type TextField = Exclude<keyof FormState, "isActive" | "autoEmailEnabled">;

const DEFAULT_AUTO_EMAIL_SUBJECT = "Félicitations pour la création de {name}";
const DEFAULT_AUTO_EMAIL_BODY = [
  "Bonjour,",
  "",
  "Nous avons remarqué la récente création de votre entreprise {name} (SIRET {siret})",
  "à {commune} {code_postal}.",
  "",
  "[Personnalisez ce message ici.]",
  "",
  "Cordialement,",
  "L'équipe Business tracker",
].join("\n");

const EMPTY_STATE: FormState = {
  categoryId: "",
  mode: "create",
  existingSubcategoryId: "",
  name: "",
  description: "",
  nafCode: "",
  priceEur: "",
  isActive: true,
  autoEmailEnabled: false,
  autoEmailSubject: "",
  autoEmailBody: "",
};

export const NafSubCategoryModal = ({
  isOpen,
  mode,
  categories,
  existingSubcategories,
  subcategory,
  initialCategoryId,
  onSubmit,
  onCancel,
  isProcessing,
}: Props) => {
  const [formState, setFormState] = useState<FormState>(EMPTY_STATE);

  useEffect(() => {
    if (!isOpen) {
      setFormState(EMPTY_STATE);
      return;
    }
    if (mode === "edit" && subcategory) {
      setFormState({
        categoryId: "",
        mode: "create",
        existingSubcategoryId: "",
        name: subcategory.name,
        description: subcategory.description ?? "",
        nafCode: subcategory.nafCode,
        priceEur: subcategory.priceEur.toString(),
        isActive: subcategory.isActive,
        autoEmailEnabled: subcategory.autoEmailEnabled,
        autoEmailSubject: subcategory.autoEmailSubject ?? "",
        autoEmailBody: subcategory.autoEmailBody ?? "",
      });
    } else {
      const defaultCategoryId = initialCategoryId ?? categories[0]?.id ?? "";
      setFormState((current) => ({
        ...EMPTY_STATE,
        categoryId: defaultCategoryId || current.categoryId,
      }));
    }
  }, [isOpen, mode, subcategory, categories, initialCategoryId]);

  useEffect(() => {
    if (mode !== "create" || formState.mode !== "attach") {
      return;
    }
    const selected = existingSubcategories.find((item) => item.id === formState.existingSubcategoryId);
    if (!selected) {
      return;
    }
    setFormState((current) => ({
      ...current,
      name: selected.name,
      description: selected.description ?? "",
      nafCode: selected.nafCode,
      priceEur: selected.priceEur.toString(),
      isActive: selected.isActive,
      autoEmailEnabled: selected.autoEmailEnabled,
      autoEmailSubject: selected.autoEmailSubject ?? "",
      autoEmailBody: selected.autoEmailBody ?? "",
    }));
  }, [mode, formState.mode, formState.existingSubcategoryId, existingSubcategories]);

  const isValid = useMemo(() => {
    const baseValid =
      mode === "edit"
        ? Boolean(formState.name.trim() && formState.nafCode.trim())
        : formState.mode === "attach"
          ? Boolean(formState.categoryId && formState.existingSubcategoryId)
          : Boolean(formState.categoryId && formState.name.trim() && formState.nafCode.trim());
    if (!baseValid) {
      return false;
    }
    if (formState.autoEmailEnabled) {
      if (!formState.autoEmailSubject.trim() || !formState.autoEmailBody.trim()) {
        return false;
      }
    }
    return true;
  }, [formState, mode]);

  const handleChange = (field: TextField) =>
    (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
      setFormState((current) => ({ ...current, [field]: event.target.value }));
    };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!isValid) {
      return;
    }
    const payload: NafSubCategoryFormPayload = {
      categoryId: formState.categoryId,
      mode: formState.mode,
      existingSubcategoryId: formState.existingSubcategoryId || undefined,
      name: formState.name.trim(),
      description: formState.description.trim() ? formState.description.trim() : null,
      nafCode: formState.nafCode.trim(),
      priceEur: formState.priceEur.trim() ? Number(formState.priceEur) : undefined,
      isActive: formState.isActive,
      autoEmailEnabled: formState.autoEmailEnabled,
      autoEmailSubject: formState.autoEmailSubject.trim() ? formState.autoEmailSubject : null,
      autoEmailBody: formState.autoEmailBody.trim() ? formState.autoEmailBody : null,
    };
    onSubmit(payload);
  };

  const hasCategories = categories.length > 0;
  const attachedSubcategoryIds = useMemo(() => {
    if (mode !== "create") {
      return new Set<string>();
    }
    const selected = categories.find((category) => category.id === formState.categoryId);
    return new Set((selected?.subcategories ?? []).map((item) => item.id));
  }, [categories, formState.categoryId, mode]);
  const selectableExisting = useMemo(
    () => existingSubcategories.filter((item) => !attachedSubcategoryIds.has(item.id)),
    [existingSubcategories, attachedSubcategoryIds],
  );

  if (!isOpen) {
    return null;
  }

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true">
      <div className="modal">
        <header className="modal-header">
          <h2>
            {mode === "create"
              ? "Nouvelle sous-catégorie NAF"
              : `Modifier ${subcategory?.name ?? "la sous-catégorie"}`}
          </h2>
          <button type="button" className="ghost" onClick={onCancel} disabled={isProcessing}>
            Fermer
          </button>
        </header>
        <form className="modal-content" onSubmit={handleSubmit}>
          <section>
            <h3>Informations principales</h3>
            <div className="form-grid">
              {mode === "create" ? (
                <div className="form-field">
                  <span className="input-label">Catégorie</span>
                  <select value={formState.categoryId} onChange={handleChange("categoryId")} disabled={!hasCategories}>
                    <option value="" disabled>
                      Sélectionner une catégorie
                    </option>
                    {categories.map((category) => (
                      <option key={category.id} value={category.id}>
                        {category.name}
                      </option>
                    ))}
                  </select>
                </div>
              ) : null}
              {mode === "create" ? (
                <div className="form-field">
                  <span className="input-label">Mode</span>
                  <select value={formState.mode} onChange={handleChange("mode")}>
                    <option value="create">Créer une nouvelle sous-catégorie</option>
                    <option value="attach">Associer une sous-catégorie existante</option>
                  </select>
                </div>
              ) : null}
              {mode === "create" && formState.mode === "attach" ? (
                <div className="form-field">
                  <span className="input-label">Sous-catégorie existante</span>
                  <select
                    value={formState.existingSubcategoryId}
                    onChange={handleChange("existingSubcategoryId")}
                    disabled={!selectableExisting.length}
                  >
                    <option value="" disabled>
                      Sélectionner une sous-catégorie
                    </option>
                    {selectableExisting.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name} · {item.nafCode}
                      </option>
                    ))}
                  </select>
                </div>
              ) : null}
              <div className="form-field">
                <span className="input-label">Nom</span>
                <input
                  type="text"
                  value={formState.name}
                  onChange={handleChange("name")}
                  placeholder="Ex : Nouvelles ouvertures Paris"
                  required
                  disabled={mode === "create" && formState.mode === "attach"}
                />
              </div>
              <div className="form-field">
                <span className="input-label">Description</span>
                <textarea
                  value={formState.description}
                  onChange={handleChange("description")}
                  placeholder="Note interne pour mieux identifier cette sous-catégorie"
                  rows={3}
                  disabled={mode === "create" && formState.mode === "attach"}
                />
              </div>
              <div className="form-field">
                <span className="input-label">Code NAF</span>
                <input
                  type="text"
                  value={formState.nafCode}
                  onChange={handleChange("nafCode")}
                  placeholder="56.10A"
                  required
                  disabled={mode === "create" && formState.mode === "attach"}
                />
              </div>
            </div>
          </section>

          <section>
            <h3>Tarification & affichage</h3>
            <div className="form-grid">
              <div className="form-field">
                <span className="input-label">Prix (euros)</span>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={formState.priceEur}
                  onChange={handleChange("priceEur")}
                  placeholder="Optionnel"
                  disabled={mode === "create" && formState.mode === "attach"}
                />
              </div>
              <label className="form-checkbox">
                <input
                  type="checkbox"
                  checked={formState.isActive}
                  onChange={(event) =>
                    setFormState((current) => ({ ...current, isActive: event.target.checked }))
                  }
                  disabled={mode === "create" && formState.mode === "attach"}
                />
                <span>Activer la sous-catégorie</span>
              </label>
            </div>
          </section>

          <section>
            <h3>Email automatique en fin de synchronisation</h3>
            <p className="muted small">
              Lorsqu'une synchronisation détecte un nouvel établissement avec une adresse email,
              un message ciblé peut lui être envoyé automatiquement. Le Reply-To est positionné sur
              l'adresse expéditrice pour récupérer les réponses.
            </p>
            <label className="form-checkbox">
              <input
                type="checkbox"
                checked={formState.autoEmailEnabled}
                onChange={(event) => {
                  const enabled = event.target.checked;
                  setFormState((current) => ({
                    ...current,
                    autoEmailEnabled: enabled,
                    autoEmailSubject:
                      enabled && !current.autoEmailSubject.trim()
                        ? DEFAULT_AUTO_EMAIL_SUBJECT
                        : current.autoEmailSubject,
                    autoEmailBody:
                      enabled && !current.autoEmailBody.trim()
                        ? DEFAULT_AUTO_EMAIL_BODY
                        : current.autoEmailBody,
                  }));
                }}
                disabled={mode === "create" && formState.mode === "attach"}
              />
              <span>Envoyer un email automatique aux nouveaux établissements de ce NAF</span>
            </label>
            <div className="form-grid">
              <div className="form-field">
                <span className="input-label">Sujet du mail</span>
                <input
                  type="text"
                  value={formState.autoEmailSubject}
                  onChange={handleChange("autoEmailSubject")}
                  placeholder="Ex : Félicitations pour la création de {name}"
                  disabled={!formState.autoEmailEnabled || (mode === "create" && formState.mode === "attach")}
                />
              </div>
              <div className="form-field">
                <span className="input-label">Corps du mail</span>
                <textarea
                  value={formState.autoEmailBody}
                  onChange={handleChange("autoEmailBody")}
                  rows={10}
                  placeholder="Bonjour, ..."
                  disabled={!formState.autoEmailEnabled || (mode === "create" && formState.mode === "attach")}
                />
              </div>
            </div>
            <p className="muted small">
              Variables disponibles : {"{name}"}, {"{siret}"}, {"{naf_code}"}, {"{commune}"},
              {" "}{"{code_postal}"}, {"{email}"}, {"{leader_name}"}, {"{google_place_url}"},
              {" "}{"{legal_unit_name}"}.
            </p>
          </section>

          <section className="card-actions">
            <button type="button" className="ghost" onClick={onCancel} disabled={isProcessing}>
              Annuler
            </button>
            <button
              type="submit"
              className="primary"
              disabled={!isValid || (mode === "create" && !hasCategories) || isProcessing}
            >
              {isProcessing ? "Enregistrement…" : "Enregistrer"}
            </button>
          </section>
        </form>
      </div>
    </div>
  );
};
