import { FormEvent, useEffect, useMemo, useState } from "react";

import type { NafCategory } from "../types";

export type NafCategoryFormPayload = {
  name: string;
  description: string | null;
  keywords: string[];
};

type Props = {
  isOpen: boolean;
  mode: "create" | "edit";
  category: NafCategory | null;
  onSubmit: (payload: NafCategoryFormPayload) => void;
  onCancel: () => void;
  isProcessing: boolean;
};

type FormState = {
  name: string;
  description: string;
  keywordsText: string;
};

const EMPTY_STATE: FormState = {
  name: "",
  description: "",
  keywordsText: "",
};

const splitKeywords = (value: string): string[] => {
  return Array.from(
    new Set(
      value
        .split(/[\n,;]/)
        .map((entry) => entry.trim())
        .filter((entry) => entry.length > 0),
    ),
  );
};

export const NafCategoryModal = ({ isOpen, mode, category, onSubmit, onCancel, isProcessing }: Props) => {
  const [formState, setFormState] = useState<FormState>(EMPTY_STATE);

  useEffect(() => {
    if (!isOpen) {
      setFormState(EMPTY_STATE);
      return;
    }
    if (mode === "edit" && category) {
      setFormState({
        name: category.name,
        description: category.description ?? "",
        keywordsText: (category.keywords ?? []).join("\n"),
      });
    } else {
      setFormState(EMPTY_STATE);
    }
  }, [isOpen, mode, category]);

  const isValid = useMemo(() => Boolean(formState.name.trim()), [formState.name]);

  const handleChange = (field: keyof FormState) => (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setFormState((current) => ({ ...current, [field]: event.target.value }));
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!isValid) {
      return;
    }
    const payload: NafCategoryFormPayload = {
      name: formState.name.trim(),
      description: formState.description.trim() ? formState.description.trim() : null,
      keywords: splitKeywords(formState.keywordsText),
    };
    onSubmit(payload);
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true">
      <div className="modal">
        <header className="modal-header">
          <h2>{mode === "create" ? "Nouvelle catégorie NAF" : `Modifier ${category?.name ?? "la catégorie"}`}</h2>
          <button type="button" className="ghost" onClick={onCancel} disabled={isProcessing}>
            Fermer
          </button>
        </header>
        <form className="modal-content" onSubmit={handleSubmit}>
          <section>
            <h3>Informations</h3>
            <div className="form-grid">
              <div className="form-field">
                <span className="input-label">Nom</span>
                <input
                  type="text"
                  value={formState.name}
                  onChange={handleChange("name")}
                  placeholder="Ex : Franchise premium"
                  required
                />
              </div>
            </div>
            <div className="form-field">
              <span className="input-label">Description</span>
              <textarea
                rows={4}
                value={formState.description}
                onChange={handleChange("description")}
                placeholder="Notes internes visibles dans l'UI."
              />
            </div>
            <div className="form-field">
              <span className="input-label">Mots-clés additionnels</span>
              <textarea
                rows={4}
                value={formState.keywordsText}
                onChange={handleChange("keywordsText")}
                placeholder="Un mot ou une expression par ligne"
              />
              <p className="small muted">
                Ces mots-clés complètent le nom/description afin d'améliorer le rapprochement avec les catégories Google.
              </p>
            </div>
          </section>

          <section className="card-actions">
            <button type="button" className="ghost" onClick={onCancel} disabled={isProcessing}>
              Annuler
            </button>
            <button type="submit" className="primary" disabled={!isValid || isProcessing}>
              {isProcessing ? "Enregistrement…" : "Enregistrer"}
            </button>
          </section>
        </form>
      </div>
    </div>
  );
};
