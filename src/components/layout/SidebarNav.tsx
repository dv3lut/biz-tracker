import { SectionDefinition, SectionKey } from "../../constants/sections";

const SECTION_BADGES: Record<SectionKey, string> = {
  dashboard: "DB",
  sync: "SY",
  alerts: "AL",
  emails: "EM",
  billing: "FA",
  establishments: "ET",
  clients: "CL",
  "naf-config": "NA",
};

type Props = {
  sections: ReadonlyArray<SectionDefinition>;
  activeSection: SectionKey;
  onSelect: (section: SectionKey) => void;
  onClose?: () => void;
};

export const SidebarNav = ({ sections, activeSection, onSelect, onClose }: Props) => {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-brand">
          <span className="sidebar-title">Business tracker</span>
          <span className="sidebar-subtitle">Console Admin</span>
        </div>
        {onClose ? (
          <button type="button" className="sidebar-close" onClick={onClose} aria-label="Fermer le menu">
            <span className="sidebar-close-icon" aria-hidden="true">
              ×
            </span>
          </button>
        ) : null}
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
