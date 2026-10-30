import { ZoneSkeleton } from "@/features/accomplissement/zones/ZoneSkeleton";
import { fr } from "@/i18n/fr";

/** Squelette T12 : liste des notifications, à implémenter par T14. */
export function NotificationsPage() {
  return (
    <>
      <h1 className="mb-6 text-2xl font-semibold tracking-[-0.012em]">
        {fr.suivi.notificationsTitle}
      </h1>
      <ZoneSkeleton id="notifications-list" title={fr.suivi.skeletonNotifications} />
    </>
  );
}
