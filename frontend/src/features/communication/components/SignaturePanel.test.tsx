import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { API_URL, server } from "@/test/msw";
import { aRapport, RAPPORT_ID, renderCommunication } from "../testUtils";
import { distributeBlocker } from "../zones/StepXVIIIZone";
import { SignaturePanel } from "./SignaturePanel";

const NON_SIGNEE = {
  signee: false,
  valide: false,
  signataire: "",
  emetteur: "",
  signe_par: "",
  signe_le: null,
  horodatage_tsa: false,
  empreinte_certificat: "",
  motif: "Le rapport n'est pas signé électroniquement.",
};

const SIGNEE = {
  ...NON_SIGNEE,
  signee: true,
  valide: true,
  signataire: "CN=ONEA Audit Interne",
  emetteur: "CN=ONEA Audit Interne",
  signe_par: "Awa Ouédraogo",
  signe_le: "2026-11-03T09:00:00Z",
  motif: "",
};

const URL = `${API_URL}/api/v1/reports/${RAPPORT_ID}/signature/`;
const requis = aRapport({
  statut: "VALIDE",
  signature_electronique_requise: true,
  actions_possibles: ["DIFFUSER"],
});

describe("SignaturePanel", () => {
  it("ne s'affiche pas si la signature électronique n'est pas exigée", () => {
    server.use(http.get(URL, () => HttpResponse.json(NON_SIGNEE)));
    renderCommunication(<SignaturePanel rapport={aRapport({ statut: "VALIDE" })} />, "RAI");
    expect(screen.queryByText("Signature électronique (PAdES)")).not.toBeInTheDocument();
  });

  it("propose au RAI de signer un rapport non signé et envoie la requête", async () => {
    let signe = false;
    server.use(
      http.get(URL, () => HttpResponse.json(signe ? SIGNEE : NON_SIGNEE)),
      http.post(`${API_URL}/api/v1/reports/${RAPPORT_ID}/sign/`, async ({ request }) => {
        expect(await request.json()).toEqual({ lieu: "Ouagadougou" });
        signe = true;
        return HttpResponse.json(SIGNEE, { status: 201 });
      }),
    );
    renderCommunication(<SignaturePanel rapport={requis} />, "RAI");
    expect(await screen.findByText(/pas encore signé électroniquement/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/Lieu de signature/), "Ouagadougou");
    await userEvent.click(screen.getByRole("button", { name: "Signer électroniquement" }));
    await userEvent.click(await screen.findByRole("checkbox"));
    await userEvent.click(screen.getByRole("button", { name: "Signer" }));
    expect(await screen.findByText("Signature valide")).toBeInTheDocument();
    expect(screen.getByText(/Signé par Awa Ouédraogo/)).toBeInTheDocument();
  });

  it("n'offre pas l'action de signature à un autre rôle", async () => {
    server.use(http.get(URL, () => HttpResponse.json(NON_SIGNEE)));
    renderCommunication(
      <SignaturePanel rapport={{ ...requis, actions_possibles: [] }} />,
      "AUDITEUR",
    );
    expect(await screen.findByText(/pas encore signé électroniquement/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Signer électroniquement" })).toBeNull();
  });

  it("signale une signature invalide avec son motif", async () => {
    server.use(
      http.get(URL, () =>
        HttpResponse.json({
          ...SIGNEE,
          valide: false,
          motif: "Le document a été modifié après sa signature.",
        }),
      ),
    );
    renderCommunication(<SignaturePanel rapport={requis} />, "RAI");
    expect(await screen.findByText(/Signature invalide/)).toBeInTheDocument();
    expect(screen.getByText(/modifié après sa signature/)).toBeInTheDocument();
  });
});

describe("distributeBlocker et signature", () => {
  const prete = {
    ...requis,
    version_finale: { statut: "PRETE", statut_pdf: "PRET" },
  } as unknown as Parameters<typeof distributeBlocker>[0];

  it("bloque la diffusion tant que le rapport n'est pas signé", () => {
    expect(distributeBlocker(prete, 1, false)).toMatch(/signature électronique/);
    expect(distributeBlocker(prete, 1, true)).toBeNull();
  });
});
