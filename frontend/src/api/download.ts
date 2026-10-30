import { fr } from "@/i18n/fr";
import { downloadBlob } from "@/lib/download";
import { apiDownload } from "./client";
import { ApiError, isApiError } from "./errors";

/**
 * Télécharge une pièce justificative : `fetch` authentifié, puis `Blob` et lien temporaire.
 * Aucun lien direct vers un fichier. 409 = empreinte SHA-256 non conforme (intégrité).
 */
export async function downloadEvidence(id: string, filename: string): Promise<void> {
  let blob: Blob;
  try {
    ({ blob } = await apiDownload(`/api/v1/evidence/${id}/download/`));
  } catch (error) {
    if (isApiError(error) && error.status === 409) {
      throw new ApiError(409, fr.errors.evidenceIntegrity);
    }
    throw error;
  }
  downloadBlob(blob, filename);
}
