import { SectionDefinition, SectionKey } from "../../constants/sections";

const SECTION_BADGES: Record<SectionKey, string> = {
  dashboard: "DB",
  sync: "SY",
  alerts: "AL",
  emails: "EM",
  establishments: "ET",
  clients: "CL",
  "naf-config": "NA",
};

type Props = {
  sections: ReadonlyArray<SectionDefinition>;
  activeSection: SectionKey;
  onSelect: (section: SectionKey) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
};

export const SidebarNav = ({ sections, activeSection, onSelect, collapsed, onToggleCollapse }: Props) => {
  const toggleLabel = collapsed ? "Agrandir le menu" : "Réduire le menu";
  const toggleIcon = collapsed ? "»" : "«";

  return (
    <aside className={`sidebar${collapsed ? " sidebar--collapsed" : ""}`}>
      <div className="sidebar-header">
        <div className="sidebar-brand">
          <span className="sidebar-title">Business tracker</span>
          <span className="sidebar-subtitle">Console Admin</span>
        </div>
        <button type="button" className="sidebar-toggle" onClick={onToggleCollapse} aria-label={toggleLabel}>
          <span className="sidebar-toggle-icon" aria-hidden="true">
            {toggleIcon}
          </span>
        </button>
      </div>
      <nav className="sidebar-nav">
        {sections.map((section) => {
          const isActive = section.key === activeSection;
          const badge = SECTION_BADGES[section.key];
          return (
            <button
              key={section.key}
              type="button"
              className={`sidebar-nav-item${isActive ? " active" : ""}`}
              onClick={() => onSelect(section.key)}
              aria-label={section.label}
              title={section.label}
            >
              <span className="sidebar-nav-badge" aria-hidden>
                {badge}
              </span>
              <div>
                <span className="sidebar-nav-label">{section.label}</span>
                {section.description ? <span className="sidebar-nav-description">{section.description}</span> : null}
              </div>
            </button>
          );
        })}
      </nav>
    </aside>
  );
};
