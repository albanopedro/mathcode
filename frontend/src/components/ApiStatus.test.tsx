import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApiStatus } from "./ApiStatus";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const HEALTHY = { status: "ok", version: "0.1.0", environment: "development" };

describe("ApiStatus", () => {
  it("shows the checking state first", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})));

    render(<ApiStatus />);

    expect(screen.getByRole("status")).toHaveTextContent("Verificando…");
  });

  it("shows version and environment when the API is online", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(HEALTHY)));

    render(<ApiStatus />);

    expect(await screen.findByText(/Online · v0\.1\.0 · desenvolvimento/)).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith("/api/health", expect.anything());
  });

  it("shows offline when the request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    render(<ApiStatus />);

    expect(await screen.findByText(/Não foi possível conectar à API/)).toBeInTheDocument();
  });

  it("shows offline on an HTTP error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({}, 500)));

    render(<ApiStatus />);

    expect(await screen.findByText(/A API respondeu com HTTP 500/)).toBeInTheDocument();
  });

  it("treats a gateway error as an unreachable API", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 502 })));

    render(<ApiStatus />);

    expect(
      await screen.findByText(/Não foi possível conectar à API \(HTTP 502\)/),
    ).toBeInTheDocument();
  });

  it("does not trust a response with an unexpected shape", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ status: "ok" })));

    render(<ApiStatus />);

    expect(await screen.findByText(/formato inesperado/)).toBeInTheDocument();
  });

  it("checks again when the user clicks retry", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(jsonResponse(HEALTHY));
    vi.stubGlobal("fetch", fetchMock);

    render(<ApiStatus />);
    await userEvent.click(await screen.findByRole("button", { name: "Tentar de novo" }));

    expect(await screen.findByText(/Online/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
