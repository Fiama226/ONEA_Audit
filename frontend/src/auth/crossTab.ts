/*
 * Signaux de session partagés entre les onglets du même navigateur (aucun secret) :
 * - « connexion » et « déconnexion » faites dans un onglet, propagées aux autres
 *   (BroadcastChannel, avec repli sur l'événement `storage`) ;
 * - déconnexion non confirmée par le serveur, à rejouer au prochain démarrage.
 */

export type AuthSignal = "login" | "logout";

const CHANNEL = "onea-auth";
const STORAGE_KEY = "onea-auth-signal";
const PENDING_LOGOUT_KEY = "onea-deconnexion-en-attente";

/** Identifie cet onglet : un onglet ignore ses propres signaux. */
const TAB_ID = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;

type Message = { type: AuthSignal; from: string };

function parse(value: unknown): Message | null {
  if (typeof value !== "object" || value === null) return null;
  const { type, from } = value as Record<string, unknown>;
  if ((type !== "login" && type !== "logout") || typeof from !== "string") return null;
  return { type, from };
}

function hasBroadcastChannel(): boolean {
  return typeof BroadcastChannel !== "undefined";
}

/** Annonce aux autres onglets une connexion ou une déconnexion faite dans celui-ci. */
export function announce(type: AuthSignal): void {
  const message: Message = { type, from: TAB_ID };
  if (hasBroadcastChannel()) {
    try {
      const channel = new BroadcastChannel(CHANNEL);
      channel.postMessage(message);
      channel.close();
      return;
    } catch {
      // repli sur le stockage local
    }
  }
  try {
    // Valeur toujours nouvelle (horodatage) : l'événement `storage` part à chaque annonce.
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...message, at: Date.now() }));
  } catch {
    // stockage indisponible (navigation privée stricte) : pas de propagation
  }
}

/** Écoute les annonces des autres onglets ; renvoie la fonction de désabonnement. */
export function listen(onSignal: (type: AuthSignal) => void): () => void {
  const receive = (value: unknown) => {
    const message = parse(value);
    if (message && message.from !== TAB_ID) onSignal(message.type);
  };
  if (hasBroadcastChannel()) {
    try {
      const channel = new BroadcastChannel(CHANNEL);
      channel.onmessage = (event: MessageEvent) => receive(event.data);
      return () => channel.close();
    } catch {
      // repli sur le stockage local
    }
  }
  const onStorage = (event: StorageEvent) => {
    if (event.key !== STORAGE_KEY || !event.newValue) return;
    try {
      receive(JSON.parse(event.newValue));
    } catch {
      // valeur illisible : ignorée
    }
  };
  window.addEventListener("storage", onStorage);
  return () => window.removeEventListener("storage", onStorage);
}

/*
 * Déconnexion en attente : marque (sans secret) posée tant que le serveur n'a pas confirmé la
 * fin de session. Stockage local plutôt que de session : un nouvel onglet ouvert sur le même
 * poste la voit aussi et rejoue la déconnexion avant de sonder la session.
 */

/** Pose la marque ; renvoie sa valeur, à passer à `clearPendingLogout`. */
export function markPendingLogout(): string {
  const mark = `${TAB_ID}-${Date.now().toString(36)}`;
  try {
    localStorage.setItem(PENDING_LOGOUT_KEY, mark);
  } catch {
    // stockage indisponible : seul le message à l'écran prévient l'agent
  }
  return mark;
}

export function hasPendingLogout(): boolean {
  try {
    return localStorage.getItem(PENDING_LOGOUT_KEY) !== null;
  } catch {
    return false;
  }
}

/**
 * Retire la marque ; avec `mark`, seulement si c'est encore celle-là (une confirmation tardive
 * n'efface pas la marque d'une déconnexion plus récente).
 */
export function clearPendingLogout(mark?: string): void {
  try {
    if (mark === undefined || localStorage.getItem(PENDING_LOGOUT_KEY) === mark) {
      localStorage.removeItem(PENDING_LOGOUT_KEY);
    }
  } catch {
    // stockage indisponible
  }
}
