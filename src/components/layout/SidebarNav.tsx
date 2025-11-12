import { SectionDefinition, SectionKey } from "../../constants/sections";

const SECTION_BADGES: Record<SectionKey, string> = {
  dashboard: "DB",
  sync: "SY",
  alerts: "AL",
  emails: "EM",
  establishments: "ET",
  clients: "CL",
};

type Props = {
  sections: ReadonlyArray<SectionDefinition>;
  activeSection: SectionKey;
  onSelect: (section: SectionKey) => void;
};

export const SidebarNav = ({ sections, activeSection, onSelect }: Props) => {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="sidebar-title">Biz Tracker</span>
        <span className="sidebar-subtitle">Console Admin</span>
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
