import { describe, expect, it, vi } from "vitest";

import { fixtures, jsonResponse } from "../test/fixtures";
import { ApiError, calculate } from "./api";

describe("calculate", () => {
  it("posts the input as JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(fixtures.equation));
    vi.stubGlobal("fetch", fetchMock);

    await calculate("2x + 5 = 17");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/calculate",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input: "2x + 5 = 17" }),
      }),
    );
  });

  it("returns successes and math errors alike (both are HTTP 200)", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse(fixtures.equation))
        .mockResolvedValueOnce(jsonResponse(fixtures.divisionByZero)),
    );

    expect((await calculate("2x + 5 = 17")).success).toBe(true);
    expect((await calculate("10 + 1/0")).error?.code).toBe("DIVISION_BY_ZERO");
  });

  it("returns the MathResult the API sends with HTTP 503", async () => {
    const busy = {
      ...fixtures.timeout,
      error: { code: "SERVER_BUSY", message: "Ocupado.", position: null },
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(busy, 503)));

    expect((await calculate("2 + 2")).error?.code).toBe("SERVER_BUSY");
  });

  it("reports an unreachable API when the proxy answers 502", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 502 })));

    await expect(calculate("2 + 2")).rejects.toThrow(/Não foi possível conectar à API/);
  });

  it("reports a rejected request (422)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: [] }, 422)));

    await expect(calculate("2 + 2")).rejects.toThrow(/HTTP 422/);
  });

  it("sends allow_ai only when asked to", async () => {
    // A new Response each time: a body can be read only once.
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(fixtures.aiEquation)));
    vi.stubGlobal("fetch", fetchMock);

    await calculate("resolva x mais 3 igual a 10", null, null, true);
    await calculate("resolva x mais 3 igual a 10", null, null, false);

    const bodies = vi
      .mocked(fetch)
      .mock.calls.map((call) => JSON.parse(call[1]!.body as string) as unknown);
    expect(bodies).toEqual([
      { input: "resolva x mais 3 igual a 10", allow_ai: true },
      { input: "resolva x mais 3 igual a 10" },
    ]);
  });

  it("does not trust an unexpected body", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ answer: 4 })));

    const promise = calculate("2 + 2");
    await expect(promise).rejects.toBeInstanceOf(ApiError);
    await expect(promise).rejects.toThrow(/formato inesperado/);
  });
});
