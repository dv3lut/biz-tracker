import { MouseEvent, useMemo } from "react";

import { buildAnnuaireEtablissementUrl } from "../utils/urls";

type Props = {
  value: string;
  className?: string;
  stopPropagation?: boolean;
};

export const SiretLink = ({ value, className, stopPropagation = true }: Props) => {
  const normalized = useMemo(() => value.replace(/\s+/g, ""), [value]);
  const href = useMemo(() => buildAnnuaireEtablissementUrl(normalized), [normalized]);

  const handleClick = (event: MouseEvent<HTMLAnchorElement>) => {
    if (stopPropagation) {
      event.stopPropagation();
    }
  };

  return (
    <a className={className} href={href} target="_blank" rel="noreferrer" onClick={handleClick}>
      {normalized}
    </a>
  );
};
