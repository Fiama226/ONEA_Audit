import { useParams } from "react-router-dom";
import { fr } from "@/i18n/fr";
import { useMeetings, useMission } from "../api";
import { MeetingCard } from "../components/MeetingCard";
import type { TypeReunion } from "../types";

const TYPES: readonly TypeReunion[] = ["OUVERTURE", "LANCEMENT", "CLOTURE"];

/** Réunions de la mission : ouverture, lancement et clôture. */
export function MeetingsPage() {
  const { id } = useParams();
  const mission = useMission(id);
  const meetings = useMeetings(id);

  if (meetings.isError) {
    return (
      <p role="alert" className="text-sm text-destructive">
        {fr.missionTravaux.loadError}
      </p>
    );
  }
  if (!mission.data || !meetings.data) {
    return (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  }
  const data = mission.data;

  return (
    <section aria-labelledby="meetings-title" className="grid gap-4">
      <h2 id="meetings-title" className="text-lg font-semibold">
        {fr.missionTravaux.meetingsTitle}
      </h2>
      {TYPES.map((type) => (
        <MeetingCard
          key={type}
          mission={data}
          type={type}
          meeting={meetings.data.results.find((m) => m.type === type)}
        />
      ))}
    </section>
  );
}
