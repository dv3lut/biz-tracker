import { useMemo, useState, useEffect, useRef } from "react";

import type { Region } from "../types";

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);

const buildAllDepartmentCodes = (regions: Region[] | undefined): string[] => {
  if (!regions) {
    return [];
  }
  const codes: string[] = [];
  regions.forEach((region) => {
    region.departments.forEach((department) => {
      codes.push(department.code);
    });
  });
  return codes;
};

type RegionDepartmentPanelProps = {
  regions: Region[] | undefined;
  isLoading: boolean;
  selectedDepartmentCodes: string[];
  onSelectionChange: (codes: string[]) => void;
  helperText?: string;
  compact?: boolean;
};

type RegionRowProps = {
  region: Region;
  selectedCodes: Set<string>;
  onToggleRegion: (region: Region) => void;
  onToggleDepartment: (code: string) => void;
  isLoading: boolean;
};

const RegionRow = ({ region, selectedCodes, onToggleRegion, onToggleDepartment, isLoading }: RegionRowProps) => {
  const checkboxRef = useRef<HTMLInputElement | null>(null);
  const departmentCodes = region.departments.map((department) => department.code);
  const selectedCount = departmentCodes.filter((code) => selectedCodes.has(code)).length;
  const isAllSelected = departmentCodes.length > 0 && selectedCount === departmentCodes.length;
  const isIndeterminate = selectedCount > 0 && !isAllSelected;

  useEffect(() => {
    if (!checkboxRef.current) {
      return;
    }
    checkboxRef.current.indeterminate = isIndeterminate;
  }, [isIndeterminate]);

  return (
    <details className="region-accordion">
      <summary>
        <label className="region-accordion-summary" onClick={(event) => event.preventDefault()}>
          <input
            ref={checkboxRef}
            type="checkbox"
            checked={isAllSelected}
            onChange={() => onToggleRegion(region)}
            disabled={isLoading}
          />
          <span>{region.name}</span>
        </label>
        <span className="muted small">
          {selectedCount}/{departmentCodes.length}
        </span>
      </summary>
      <div className="region-accordion-panel">
        <div className="region-department-grid">
          {region.departments.map((department) => {
            const checked = selectedCodes.has(department.code);
            return (
              <label key={department.id} className="region-department-option">
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => onToggleDepartment(department.code)}
                  disabled={isLoading}
                />
                <span>
                  {department.code} · {department.name}
                </span>
              </label>
            );
          })}
        </div>
      </div>
    </details>
  );
};

export const RegionDepartmentPanel = ({
  regions,
  isLoading,
  selectedDepartmentCodes,
  onSelectionChange,
  helperText,
  compact = false,
}: RegionDepartmentPanelProps) => {
  const [zoom, setZoom] = useState(1);
  const allDepartmentCodes = useMemo(() => buildAllDepartmentCodes(regions), [regions]);
  const selectedCodes = useMemo(() => new Set(selectedDepartmentCodes), [selectedDepartmentCodes]);
  const hasAll = allDepartmentCodes.length > 0 && allDepartmentCodes.every((code) => selectedCodes.has(code));

  const handleToggleAll = () => {
    if (hasAll) {
      onSelectionChange([]);
      return;
    }
    onSelectionChange(allDepartmentCodes);
  };

  const handleToggleDepartment = (code: string) => {
    const next = new Set(selectedCodes);
    if (next.has(code)) {
      next.delete(code);
    } else {
      next.add(code);
    }
    onSelectionChange(Array.from(next));
  };

  const handleToggleRegion = (region: Region) => {
    const departmentCodes = region.departments.map((department) => department.code);
    if (departmentCodes.length === 0) {
      return;
    }
    const next = new Set(selectedCodes);
    const hasAllRegion = departmentCodes.every((code) => next.has(code));
    if (hasAllRegion) {
      departmentCodes.forEach((code) => next.delete(code));
    } else {
      departmentCodes.forEach((code) => next.add(code));
    }
    onSelectionChange(Array.from(next));
  };

  const handleZoomChange = (value: number) => {
    setZoom(clamp(value, 1, 2.6));
  };

  return (
    <div className={`region-picker ${compact ? "region-picker--compact" : ""}`}>
      <div className="region-picker-header">
        <div>
          <strong>Départements</strong>
          <p className="muted small">
            {helperText ?? "Sélectionnez une région pour inclure tous ses départements, ou choisissez au détail."}
          </p>
        </div>
        <div className="region-picker-actions">
          <button type="button" className="ghost" onClick={handleToggleAll} disabled={isLoading}>
            {hasAll ? "Tout désélectionner" : "Tout sélectionner"}
          </button>
        </div>
      </div>

      <div className="region-picker-body">
        <div className="region-map-card">
          <div className="region-map-toolbar">
            <span className="muted small">Carte des régions</span>
            <div className="region-map-zoom">
              <button type="button" className="ghost" onClick={() => handleZoomChange(zoom - 0.1)}>
                −
              </button>
              <input
                type="range"
                min={1}
                max={2.6}
                step={0.1}
                value={zoom}
                onChange={(event) => handleZoomChange(Number(event.target.value))}
                aria-label="Zoom carte"
              />
              <button type="button" className="ghost" onClick={() => handleZoomChange(zoom + 0.1)}>
                +
              </button>
            </div>
          </div>
          <div className="region-map-frame">
            <img
              src="/carte-des-regions-de-france-metropolitaine-et-outre-mer.jpg"
              alt="Carte des régions de France métropolitaine et outre-mer"
              style={{ transform: `scale(${zoom})` }}
            />
          </div>
        </div>

        <div className="region-picker-list">
          {isLoading && <p>Chargement des régions…</p>}
          {!isLoading && (!regions || regions.length === 0) && (
            <p className="muted small">Aucune région disponible.</p>
          )}
          {regions?.map((region) => (
            <RegionRow
              key={region.id}
              region={region}
              selectedCodes={selectedCodes}
              onToggleRegion={handleToggleRegion}
              onToggleDepartment={handleToggleDepartment}
              isLoading={isLoading}
            />
          ))}
        </div>
      </div>
    </div>
  );
};

export default RegionDepartmentPanel;
