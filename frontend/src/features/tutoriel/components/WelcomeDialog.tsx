import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { Role } from "@/auth/types";
import { fr } from "@/i18n/fr";

const T = fr.tutoriel;

type Props = { role: Role; onStart: () => void; onLater: () => void };

/** Fenêtre de bienvenue : Échap équivaut à « Plus tard ». */
export function WelcomeDialog({ role, onStart, onLater }: Props) {
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onLater();
      }}
    >
      <DialogContent
        showCloseButton={false}
        onInteractOutside={(e) => e.preventDefault()}
        className="sm:max-w-md"
      >
        <DialogHeader>
          <DialogTitle>{T.welcomeTitle}</DialogTitle>
          <DialogDescription>{T.welcomeText}</DialogDescription>
        </DialogHeader>
        <p className="text-sm text-text-muted">{T.welcomeRole.replace("{role}", fr.roles[role])}</p>
        <DialogFooter className="gap-2 sm:gap-2">
          <Button type="button" variant="outline" onClick={onLater}>
            {T.later}
          </Button>
          <Button type="button" onClick={onStart}>
            {T.start}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
