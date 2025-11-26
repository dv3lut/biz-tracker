import type { ReactNode } from "react";

import { AppHeader } from "../../components/layout/AppHeader";
import { SidebarNav } from "../../components/layout/SidebarNav";
import { NAV_SECTIONS, type SectionKey } from "../../constants/sections";
import styles from "./AppFrame.module.css";

const buildFrameClassName = (collapsed: boolean) => {
  if (!collapsed) {
    return styles.frame;
  }
  return `${styles.frame} ${styles.sidebarCollapsed}`;
};

type Props = {
  activeSection: SectionKey;
  onSectionChange: (section: SectionKey) => void;
  isSidebarCollapsed: boolean;
  onToggleSidebar: () => void;
  onResetToken: () => void;
  children: ReactNode;
};

export const AppFrame = ({
  activeSection,
  onSectionChange,
  isSidebarCollapsed,
  onToggleSidebar,
  onResetToken,
  children,
}: Props) => {
  return (
    <div className={buildFrameClassName(isSidebarCollapsed)}>
      <SidebarNav
        sections={NAV_SECTIONS}
        activeSection={activeSection}
        onSelect={onSectionChange}
        collapsed={isSidebarCollapsed}
        onToggleCollapse={onToggleSidebar}
      />
      <div className={styles.content}>
        <AppHeader onTokenReset={onResetToken} />
        <main className={styles.main}>{children}</main>
      </div>
    </div>
  );
};
