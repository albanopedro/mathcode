import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { fixtures } from "../test/fixtures";
import { graphDetails } from "../utils/graph";
import { GraphView } from "./GraphView";

// jsdom cannot draw: Plotly is replaced, and the test checks what it receives.
const plotly = vi.hoisted(() => ({
  newPlot: vi.fn(() => Promise.resolve()),
  purge: vi.fn(),
}));
vi.mock("plotly.js-basic-dist-min", () => ({ default: plotly }));

describe("GraphView", () => {
  beforeEach(() => {
    plotly.newPlot.mockClear();
    plotly.purge.mockClear();
  });

  it("draws the traces with Plotly, loaded on demand", async () => {
    const details = graphDetails(fixtures.graphParabola)!;
    render(<GraphView details={details} />);

    expect(screen.getByText("Carregando o gráfico…")).toBeInTheDocument();
    await waitFor(() => expect(plotly.newPlot).toHaveBeenCalledTimes(1));
    const [element, data, layout, config] = plotly.newPlot.mock.calls[0] as unknown as [
      HTMLElement,
      unknown[],
      { xaxis: { range: number[] } },
      { displaylogo: boolean; showSendToCloud: boolean; modeBarButtonsToRemove: string[] },
    ];
    expect(element).toBe(screen.getByTestId("graph"));
    expect(data).toHaveLength(2);
    expect(layout.xaxis.range).toEqual([-10, 10]);
    expect(config.displaylogo).toBe(false);
    // No upload to Plotly's cloud (ADR 0001).
    expect(config.showSendToCloud).toBe(false);
    expect(config.modeBarButtonsToRemove).toContain("sendChartToCloud");
    await waitFor(() => expect(screen.queryByText("Carregando o gráfico…")).toBeNull());
  });

  it("describes the graph for screen readers", () => {
    render(<GraphView details={graphDetails(fixtures.graphTwo)!} />);
    expect(screen.getByRole("img")).toHaveAccessibleName("Gráfico de y = x^2, y = 2*x + 1");
  });

  it("releases Plotly when it goes away", async () => {
    const { unmount } = render(<GraphView details={graphDetails(fixtures.graphTan)!} />);
    await waitFor(() => expect(plotly.newPlot).toHaveBeenCalled());
    unmount();
    expect(plotly.purge).toHaveBeenCalledTimes(1);
  });

  it("says so when Plotly cannot be loaded", async () => {
    plotly.newPlot.mockImplementationOnce(() => Promise.reject(new Error("no")));
    render(<GraphView details={graphDetails(fixtures.graphParabola)!} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível carregar o gráfico.");
  });
});
