export const DATA = {
  grid: new URL("../data/processed/grid_cells.geojson", document.baseURI).href,
  model: new URL("../baselines/outputs/model_results.csv", document.baseURI).href,
  explain: new URL(
    "../outputs/interpretability/explanations.csv",
    document.baseURI
  ).href,
};

export const METRIC_OPTIONS = [
  { value: "rf_prob", label: "Random Forest P(fire / hotspot)" },
  { value: "hotspot_prob", label: "Hotspot model prob." },
  { value: "arima_prob", label: "ARIMA prob." },
  { value: "arima_forecast", label: "ARIMA forecast" },
  { value: "incident_count", label: "Incidents (interval)" },
  { value: "target_next_interval", label: "Next-interval target" },
];

export const TS_METRICS = [
  { key: "rf_prob", name: "RF", color: "#7dd3fc" },
  { key: "hotspot_prob", name: "Hotspot", color: "#fb923c" },
  { key: "arima_prob", name: "ARIMA", color: "#4ade80" },
];
