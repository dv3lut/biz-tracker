import { FormEvent, useEffect, useMemo, useState } from "react";

import type { NafCategory, NafSubCategory } from "../types";

export type NafSubCategoryFormPayload = {
  categoryId: string;
  name: string;
  description: string | null;
  nafCode: string;
  priceEur?: number;
  isActive: boolean;
};

type FormState = {
  categoryId: string;
  name: string;
  description: string;
  nafCode: string;
  priceEur: string;
  isActive: boolean;
};

type Props = {
  isOpen: boolean;
  mode: "create" | "edit";
  categories: NafCategory[];
  subcategory: NafSubCategory | null;
  initialCategoryId?: string;
  onSubmit: (payload: NafSubCategoryFormPayload) => void;
  onCancel: () => void;
  isProcessing: boolean;
};

type TextField = Exclude<keyof FormState, "isActive">;

const EMPTY_STATE: FormState = {
  categoryId: "",
  name: "",
  description: "",
  nafCode: "",
  priceEur: "",
  isActive: true,
};

export const NafSubCategoryModal = ({
  isOpen,
  mode,
  categories,
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
        categoryId: subcategory.categoryId,
        name: subcategory.name,
        description: subcategory.description ?? "",
        nafCode: subcategory.nafCode,
        priceEur: subcategory.priceEur.toString(),
        isActive: subcategory.isActive,
      });
    } else {
      const defaultCategoryId = initialCategoryId ?? categories[0]?.id ?? "";
      setFormState((current) => ({
        ...EMPTY_STATE,
        categoryId: defaultCategoryId || current.categoryId,
      }));
    }
  }, [isOpen, mode, subcategory, categories, initialCategoryId]);

  const isValid = useMemo(() => {
    return Boolean(formState.categoryId && formState.name.trim() && formState.nafCode.trim());
  }, [formState]);

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
      name: formState.name.trim(),
      description: formState.description.trim() ? formState.description.trim() : null,
      nafCode: formState.nafCode.trim(),
      priceEur: formState.priceEur.trim() ? Number(formState.priceEur) : undefined,
      isActive: formState.isActive,
    };
    onSubmit(payload);
  };

  if (!isOpen) {
    return null;
  }

  const hasCategories = categories.length > 0;

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
              <div className="form-field">
                <span className="input-label">Nom</span>
                <input
                  type="text"
                  value={formState.name}
                  onChange={handleChange("name")}
                  placeholder="Ex : Nouvelles ouvertures Paris"
                  required
                />
              </div>
              <div className="form-field">
                <span className="input-label">Description</span>
                <textarea
                  value={formState.description}
                  onChange={handleChange("description")}
                  placeholder="Note interne pour mieux identifier cette sous-catégorie"
                  rows={3}
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
                />
              </div>
              <label className="form-checkbox">
                <input
                  type="checkbox"
                  checked={formState.isActive}
                  onChange={(event) =>
                    setFormState((current) => ({ ...current, isActive: event.target.checked }))
                  }
                />
                <span>Activer la sous-catégorie</span>
              </label>
            </div>
          </section>

          <section className="card-actions">
            <button type="button" className="ghost" onClick={onCancel} disabled={isProcessing}>
              Annuler
            </button>
            <button type="submit" className="primary" disabled={!isValid || !hasCategories || isProcessing}>
              {isProcessing ? "Enregistrement…" : "Enregistrer"}
            </button>
          </section>
        </form>
      </div>
    </div>
  );
};
