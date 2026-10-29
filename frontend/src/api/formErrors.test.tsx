import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useForm } from "react-hook-form";
import { describe, expect, it } from "vitest";
import { ApiError } from "@/api/errors";
import { fr } from "@/i18n/fr";
import { applyApiErrors } from "./formErrors";

type Values = { a: string; b: string };
const FIELDS = ["a", "b"] as const;

function Harness({ error, onResult }: { error: unknown; onResult: (m: string | null) => void }) {
  const { register, setError } = useForm<Values>();
  return (
    <form>
      <input aria-label="A" {...register("a")} />
      <input aria-label="B" {...register("b")} />
      <button type="button" onClick={() => onResult(applyApiErrors(error, setError, FIELDS))}>
        go
      </button>
    </form>
  );
}

async function run(error: unknown) {
  cleanup();
  let result: string | null | undefined;
  render(<Harness error={error} onResult={(m) => (result = m)} />);
  await userEvent.click(screen.getByRole("button", { name: "go" }));
  return () => result;
}

describe("applyApiErrors", () => {
  it("focuses the first field in error and returns null when all errors are mapped", async () => {
    const result = await run(
      new ApiError(422, "Données invalides.", { b: ["Mauvais."], a: ["Pire."] }),
    );
    await waitFor(() => expect(screen.getByLabelText("B")).toHaveFocus());
    expect(result()).toBeNull();
  });

  it("returns errors on unknown fields as the general message", async () => {
    const result = await run(new ApiError(422, "Données invalides.", { zzz: ["Inconnu."] }));
    expect(result()).toBe("Inconnu.");
  });

  it("returns the detail when there are no field errors, and a generic message otherwise", async () => {
    expect((await run(new ApiError(422, "Refusé.", {})))()).toBe("Refusé.");
    expect((await run(new Error("boom")))()).toBe(fr.errors.generic);
  });
});
