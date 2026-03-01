import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import { AppHeader } from "../../components/layout/AppHeader";
import { SidebarNav } from "../../components/layout/SidebarNav";
import { NAV_SECTIONS, type SectionKey } from "../../constants/sections";
import styles from "./AppFrame.module.css";

type Props = {
  activeSection: SectionKey;
  onSectionChange: (section: SectionKey) => void;
  onResetToken: () => void;
  children: ReactNode;
};

export const AppFrame = ({
  activeSection,
  onSectionChange,
  onResetToken,
  children,
}: Props) => {
  const [isNavOpen, setIsNavOpen] = useState(false);

  useEffect(() => {
    if (!isNavOpen) {
      return;
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsNavOpen(false);
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [isNavOpen]);

  useEffect(() => {
    if (!isNavOpen) {
      return;
    }

    // Évite le scroll de fond quand le drawer est ouvert.
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [isNavOpen]);

  const drawerClassName = useMemo(() => {
    return isNavOpen ? `${styles.drawer} ${styles.drawerOpen}` : styles.drawer;
  }, [isNavOpen]);

  const backdropClassName = useMemo(() => {
    return isNavOpen ? `${styles.backdrop} ${styles.backdropOpen}` : styles.backdrop;
  }, [isNavOpen]);

  return (
    <div className={styles.frame}>
      <div
        className={backdropClassName}
        onClick={() => setIsNavOpen(false)}
        aria-hidden={!isNavOpen}
      />

      <div className={drawerClassName} role="dialog" aria-modal="true" aria-label="Menu" aria-hidden={!isNavOpen}>
        <SidebarNav
          sections={NAV_SECTIONS}
          activeSection={activeSection}
          onSelect={(section) => {
            onSectionChange(section);
            setIsNavOpen(false);
          }}
          onClose={() => setIsNavOpen(false)}
        />
      </div>

      <div className={styles.content}>
        <AppHeader onTokenReset={onResetToken} onOpenMenu={() => setIsNavOpen(true)} />
        <main className={styles.main}>{children}</main>
      </div>
    </div>
  );
};
