import { useCallback, useEffect, useState } from "react";

import { AppFrame } from "./app/components/AppFrame";
import { useAdminSession } from "./app/hooks/useAdminSession";
import { useEstablishmentDetailModal } from "./app/hooks/useEstablishmentDetailModal";
import { AlertsSection } from "./app/sections/AlertsSection";
import { ClientsSection } from "./app/sections/ClientsSection";
import { DashboardSection } from "./app/sections/DashboardSection";
import { EmailsSection } from "./app/sections/EmailsSection";
import { EstablishmentsSection } from "./app/sections/EstablishmentsSection";
import { NafConfigSection } from "./app/sections/NafConfigSection";
import { SyncSection } from "./app/sections/SyncSection";
import type { SectionKey } from "./constants/sections";
import { AdminTokenPrompt } from "./components/AdminTokenPrompt";
import { EstablishmentDetailModal } from "./components/EstablishmentDetailModal";

const DEFAULT_SECTION: SectionKey = "dashboard";

const App = () => {
  const {
    adminToken,
    tokenError,
    handleTokenSubmit,
    handleTokenReset: resetSession,
    requestAdminToken,
    handleUnauthorized,
  } = useAdminSession();

  const [activeSection, setActiveSection] = useState<SectionKey>(DEFAULT_SECTION);
  const [isSidebarCollapsed, setSidebarCollapsed] = useState(false);

  const isAuthenticated = Boolean(adminToken);
  const { modalProps, openDetail } = useEstablishmentDetailModal(isAuthenticated, handleUnauthorized);

  const handleSectionChange = useCallback((section: SectionKey) => {
    setActiveSection(section);
  }, []);

  const handleToggleSidebar = useCallback(() => {
    setSidebarCollapsed((value) => !value);
  }, []);

  const handleResetToken = useCallback(() => {
    resetSession();
    setActiveSection(DEFAULT_SECTION);
    setSidebarCollapsed(false);
  }, [resetSession]);

  useEffect(() => {
    if (!adminToken) {
      setActiveSection(DEFAULT_SECTION);
      setSidebarCollapsed(false);
    }
  }, [adminToken]);

  const renderSection = () => {
    switch (activeSection) {
      case "dashboard":
        return <DashboardSection onUnauthorized={handleUnauthorized} />;
      case "sync":
        return <SyncSection onUnauthorized={handleUnauthorized} />;
      case "alerts":
        return (
          <AlertsSection onUnauthorized={handleUnauthorized} onOpenEstablishmentDetail={openDetail} />
        );
      case "clients":
        return <ClientsSection onUnauthorized={handleUnauthorized} />;
      case "naf-config":
        return (
          <NafConfigSection
            isAuthenticated={isAuthenticated}
            onRequireToken={requestAdminToken}
            onUnauthorized={handleUnauthorized}
          />
        );
      case "emails":
        return <EmailsSection onUnauthorized={handleUnauthorized} />;
      case "establishments":
        return (
          <EstablishmentsSection
            onUnauthorized={handleUnauthorized}
            onOpenEstablishmentDetail={openDetail}
          />
        );
      default:
        return null;
    }
  };

  if (!adminToken) {
    return <AdminTokenPrompt onSubmit={handleTokenSubmit} errorMessage={tokenError} />;
  }

  return (
    <>
      <AppFrame
        activeSection={activeSection}
        onSectionChange={handleSectionChange}
        isSidebarCollapsed={isSidebarCollapsed}
        onToggleSidebar={handleToggleSidebar}
        onResetToken={handleResetToken}
      >
        {renderSection()}
      </AppFrame>

      <EstablishmentDetailModal {...modalProps} />
    </>
  );
};

export default App;
