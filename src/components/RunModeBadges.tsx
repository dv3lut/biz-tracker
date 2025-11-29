import { SyncRun } from "../types";

type Props = {
  run: Pick<SyncRun, "mode" | "targetNafCodes" | "targetClientIds" | "notifyAdmins" | "dayReplayForceGoogle">;
  className?: string;
};

export const RunModeBadges = ({ run, className }: Props) => {
  const badges: Array<{ key: string; label: string; tone: "replay" | "naf" | "clients" | "admins"; title: string }> = [];

  if (run.mode === "day_replay") {
    badges.push({
      key: "replay",
      label: "Rejeu ciblé",
      tone: "replay",
      title: "Rejoue une journée précise avec options de ciblage",
    });
    if (run.dayReplayForceGoogle) {
      badges.push({
        key: "force-google",
        label: "Google forcé",
        tone: "replay",
        title: "Les appels Google ont été forcés pendant ce rejeu",
      });
    }
  }

  if (run.targetNafCodes && run.targetNafCodes.length > 0) {
    const count = run.targetNafCodes.length;
    const preview = run.targetNafCodes.slice(0, 5).join(", ");
    badges.push({
      key: "naf",
      label: count === 1 ? `NAF ${run.targetNafCodes[0]}` : `NAF ciblées (${count})`,
      tone: "naf",
      title:
        count === 1
          ? `Synchronisation ciblée sur ${run.targetNafCodes[0]}`
          : `Synchronisation ciblée sur ${preview}${count > 5 ? "…" : ""}`,
    });
  }

  if (run.targetClientIds && run.targetClientIds.length > 0) {
    const count = run.targetClientIds.length;
    const preview = run.targetClientIds.slice(0, 5).join(", ");
    badges.push({
      key: "clients",
      label: count === 1 ? "1 client ciblé" : `${count} clients ciblés`,
      tone: "clients",
      title: count > 5 ? `${preview}…` : preview || "Ciblage clients",
    });
  }

  if (run.notifyAdmins === false) {
    badges.push({
      key: "admins",
      label: "Admins désactivés",
      tone: "admins",
      title: "Les alertes administrateurs sont volontairement désactivées pour ce run.",
    });
  }

  if (badges.length === 0) {
    return null;
  }

  return (
    <div className={`run-mode-badges${className ? ` ${className}` : ""}`}>
      {badges.map((badge) => (
        <span key={badge.key} className={`badge badge-${badge.tone}`} title={badge.title}>
          {badge.label}
        </span>
      ))}
    </div>
  );
};
