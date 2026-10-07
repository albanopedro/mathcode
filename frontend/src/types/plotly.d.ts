// plotly.js-basic-dist-min ships without types: only what GraphView uses.
declare module "plotly.js-basic-dist-min" {
  interface PlotlyStatic {
    newPlot(
      element: HTMLElement,
      data: object[],
      layout?: object,
      config?: object,
    ): Promise<unknown>;
    purge(element: HTMLElement): void;
  }
  const Plotly: PlotlyStatic;
  export default Plotly;
}
