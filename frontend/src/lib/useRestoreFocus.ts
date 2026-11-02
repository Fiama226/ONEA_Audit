import * as React from "react";

/**
 * Retour du focus à la fermeture d'une boîte de dialogue pilotée sans `Trigger` (état `open`
 * contrôlé) : Radix ne sait alors pas où rendre le focus et il retombe sur `<body>` (WCAG 2.4.3).
 * L'élément actif est mémorisé au rendu qui ouvre la boîte, avant que le focus ne bascule.
 */
export function useRestoreFocus(open: boolean | undefined) {
  const [saved, setSaved] = React.useState<HTMLElement | null>(null);
  const [wasOpen, setWasOpen] = React.useState(false);
  const isOpen = !!open;
  if (isOpen !== wasOpen) {
    setWasOpen(isOpen);
    if (isOpen) {
      setSaved(document.activeElement instanceof HTMLElement ? document.activeElement : null);
    }
  }

  return React.useCallback(
    (event: Event) => {
      if (!event.defaultPrevented && saved && saved.isConnected && saved !== document.body) {
        event.preventDefault();
        saved.focus();
      }
    },
    [saved],
  );
}

export const RestoreFocusContext = React.createContext<((event: Event) => void) | null>(null);
