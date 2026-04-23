/**
 * Fire risk explorer: Leaflet map (reliable sizing in previews) + D3 scales / charts.
 * Serve repo root: python3 -m http.server 8000 → /frontend/index.html
 */
(function () {
  "use strict";

  if (typeof L === "undefined" || typeof d3 === "undefined") {
    document.getElementById("error-banner").className = "error-banner visible";
    document.getElementById("error-banner").textContent =
      "Leaflet or D3 failed to load (check network / CDN).";
    return;
  }

  const DATA = {
    grid: new URL("../data/processed/grid_cells.geojson", document.baseURI).href,
    model: new URL("../baselines/outputs/model_results.csv", document.baseURI).href,
    explain: new URL(
      "../outputs/interpretability/explanations.csv",
      document.baseURI
    ).href,
  };

  const METRIC_OPTIONS = [
    { value: "rf_prob", label: "Random Forest P(fire / hotspot)" },
    { value: "hotspot_prob", label: "Hotspot model prob." },
    { value: "arima_prob", label: "ARIMA prob." },
    { value: "arima_forecast", label: "ARIMA forecast" },
    { value: "incident_count", label: "Incidents (interval)" },
    { value: "target_next_interval", label: "Next-interval target" },
  ];

  const el = {
    err: d3.select("#error-banner"),
    dateSlider: d3.select("#date-slider"),
    dateReadout: d3.select("#date-readout"),
    datePrev: d3.select("#date-prev"),
    dateNext: d3.select("#date-next"),
    metric: d3.select("#metric-select"),
    asideTitle: d3.select("#panel-title"),
    detail: d3.select("#cell-detail"),
    shap: d3.select("#shap-chart"),
    status: d3.select("#map-status"),
    explain: d3.select("#explanation"),
    colorG: d3.select("#legend-swatch"),
  };

  const fmt = d3.format(".3f");
  const fmt2 = d3.format(".2f");

  function showError(msg) {
    el.err.classed("visible", true).text(msg);
  }

  function valueExtent(rows, key) {
    const vals = rows
      .map((d) => +d[key])
      .filter((v) => v === v);
    if (!vals.length) {
      return [0, 1];
    }
    return d3.extent(vals);
  }

  function loadExplainIndex(rows) {
    const m = d3.rollup(
      rows,
      (v) => v[0],
      (d) => d.grid_id,
      (d) => d.date
    );
    return (gridId, date) => m.get(gridId)?.get(String(date)) ?? null;
  }

  function normDate(d) {
    if (d instanceof Date) {
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, "0");
      const day = String(d.getDate()).padStart(2, "0");
      return `${y}-${m}-${day}`;
    }
    return String(d);
  }

  function colorScaleFor(rows, metric) {
    const ex0 = valueExtent(rows, metric);
    let lo = ex0[0];
    let hi = ex0[1];
    if (lo === hi) {
      hi = lo + 1e-9;
    }
    return d3.scaleSequential(d3.interpolateYlOrRd).domain([lo, hi]);
  }

  Promise.all([
    d3.json(DATA.grid),
    d3.csv(DATA.model, d3.autoType),
    d3.csv(DATA.explain, d3.autoType).catch(() => []),
  ])
    .then(([geo, modelRows, explainRows]) => {
      for (const r of modelRows) {
        r.date = normDate(r.date);
      }
      for (const r of explainRows) {
        r.date = normDate(r.date);
      }
      const byDate = d3.group(modelRows, (d) => d.date);
      const dates = Array.from(byDate.keys()).sort();
      if (!dates.length) {
        throw new Error("No dates in model_results.csv");
      }

      const explainLookup =
        explainRows && explainRows.length
          ? loadExplainIndex(explainRows)
          : null;

      function explainDatesForGrid(gid) {
        if (!explainRows || !explainRows.length) {
          return [];
        }
        return explainRows
          .filter((r) => r.grid_id === gid)
          .map((r) => r.date)
          .sort();
      }

      let dateIndex = dates.length - 1;

      function currentDateStr() {
        return dates[dateIndex];
      }

      function formatDateLong(iso) {
        const p = String(iso).split("-");
        if (p.length !== 3) {
          return iso;
        }
        const dt = new Date(Number(p[0]), Number(p[1]) - 1, Number(p[2]));
        return dt.toLocaleDateString(undefined, {
          weekday: "short",
          month: "short",
          day: "numeric",
          year: "numeric",
        });
      }

      function syncDateUI() {
        el.dateSlider
          .property("max", Math.max(0, dates.length - 1))
          .property("value", dateIndex);
        el.dateReadout.text(
          formatDateLong(currentDateStr()) +
            "  ·  " +
            (dateIndex + 1) +
            " / " +
            dates.length
        );
        el.datePrev.property("disabled", dateIndex <= 0);
        el.dateNext.property("disabled", dateIndex >= dates.length - 1);
        el.dateSlider.attr("aria-valuetext", currentDateStr());
      }

      function onDateChangedByUser() {
        selectedGid = null;
        renderMap();
        el.asideTitle.text("Select a cell");
        el.detail.html(
          "<p class=\"hint\">Click a cell for drivers and model inputs.</p>"
        );
        el.shap.html("");
        el.explain.html("");
        invalidateMapSize();
      }

      el.metric
        .selectAll("option")
        .data(METRIC_OPTIONS)
        .join("option")
        .attr("value", (d) => d.value)
        .text((d) => d.label);

      el.metric.property("value", "rf_prob");

      const map = L.map("leaflet-map", {
        zoomSnap: 0.25,
        minZoom: 9,
        maxZoom: 18,
      });

      L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        {
          attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
          subdomains: "abcd",
        }
      ).addTo(map);

      let selectedGid = null;
      let currentColorScale = d3
        .scaleSequential(d3.interpolateYlOrRd)
        .domain([0, 1]);
      let styleRmap = null;
      let styleMetric = null;

      function rowMap() {
        const dStr = currentDateStr();
        const sub = byDate.get(dStr) || [];
        return d3.index(sub, (r) => r.grid_id);
      }

      function updateLegend(lo, hi) {
        el.colorG.selectAll("*").remove();
        const w = 160;
        const h = 12;
        const uid = "lg-" + Math.random().toString(36).slice(2);
        const lg = el.colorG
          .append("svg")
          .attr("width", w)
          .attr("height", h);
        const cScale = d3
          .scaleSequential(d3.interpolateYlOrRd)
          .domain([lo, hi]);
        const defs = lg.append("defs");
        const grad = defs
          .append("linearGradient")
          .attr("id", uid)
          .attr("x1", "0%")
          .attr("x2", "100%");
        const n = 24;
        for (let i = 0; i < n; i += 1) {
          const t0 = lo + ((hi - lo) * i) / n;
          const t1 = lo + ((hi - lo) * (i + 1)) / n;
          grad
            .append("stop")
            .attr("offset", `${(i / n) * 100}%`)
            .attr("stop-color", cScale(t0));
          grad
            .append("stop")
            .attr("offset", `${((i + 1) / n) * 100}%`)
            .attr("stop-color", cScale(t1));
        }
        lg.append("rect").attr("width", w).attr("height", h).attr("fill", "url(#" + uid + ")");

        const metric = el.metric.property("value");
        d3.select("#legend-title").text(
          METRIC_OPTIONS.find((m) => m.value === metric)?.label || metric
        );
        d3.select("#legend-min").text(
          Math.abs(lo) < 20 && hi - lo < 1 && Math.abs(hi) < 20
            ? fmt(lo)
            : fmt2(lo)
        );
        d3.select("#legend-max").text(
          Math.abs(lo) < 20 && hi - lo < 1 && Math.abs(hi) < 20
            ? fmt(hi)
            : fmt2(hi)
        );
        currentColorScale = cScale;
        return cScale;
      }

      function syncStyleStateFromControls() {
        const metric = el.metric.property("value");
        const dStr = currentDateStr();
        const sub = byDate.get(dStr) || [];
        styleRmap = d3.index(sub, (r) => r.grid_id);
        styleMetric = metric;
        const cScale = colorScaleFor(sub, metric);
        updateLegend(cScale.domain()[0], cScale.domain()[1]);
      }

      function styleForFeature(feature) {
        const gid = feature.properties.grid_id;
        const metric = styleMetric || el.metric.property("value");
        const row = styleRmap ? styleRmap.get(gid) : null;
        const selected = gid === selectedGid;
        const noData =
          !row || row[metric] === null || row[metric] === undefined;
        const fill = noData
          ? "#3d4555"
          : currentColorScale(+row[metric]);
        return {
          fillColor: fill,
          color: selected ? "#60a5fa" : "#1e293b",
          weight: selected ? 2.5 : 0.4,
          opacity: 1,
          fillOpacity: noData ? 0.35 : 0.82,
        };
      }

      syncStyleStateFromControls();

      const geoLayer = L.geoJSON(geo, {
        style: styleForFeature,
        onEachFeature(feature, layer) {
          layer.on({
            click() {
              selectedGid = feature.properties.grid_id;
              geoLayer.setStyle(styleForFeature);
              showDetail(feature);
            },
            mouseover() {
              const dStr = currentDateStr();
              const rmap = rowMap();
              const row = rmap.get(feature.properties.grid_id);
              const m = el.metric.property("value");
              const t = row && row[m] != null ? fmt2(+row[m]) : "—";
              el.status.text(
                feature.properties.grid_id +
                  " · " +
                  (METRIC_OPTIONS.find((o) => o.value === m)?.label || m) +
                  " = " +
                  t
              );
            },
            mouseout() {
              const dStr = currentDateStr();
              const n = byDate.get(dStr)?.length || 0;
              const metric = el.metric.property("value");
              const lab = METRIC_OPTIONS.find(
                (o) => o.value === metric
              )?.label;
              el.status.text(
                "Date: " + dStr + " · " + n + " modeled cells · " + lab
              );
            },
          });
        },
      }).addTo(map);

      map.fitBounds(geoLayer.getBounds(), { padding: [12, 12], maxZoom: 13 });

      function renderMap() {
        const dStr = currentDateStr();
        const sub = byDate.get(dStr) || [];
        syncStyleStateFromControls();
        geoLayer.setStyle(styleForFeature);
        el.status.text(
          "Date: " +
            dStr +
            " · " +
            sub.length +
            " modeled cells (others: no row this date) · " +
            (METRIC_OPTIONS.find((o) => o.value === styleMetric)?.label ||
              styleMetric)
        );
      }

      function shapBarChart(row) {
        if (!row) {
          el.shap.html("");
          return;
        }
        const top = [
          { name: row.top_driver_1, val: +row.top_driver_1_shap || 0 },
          { name: row.top_driver_2, val: +row.top_driver_2_shap || 0 },
          { name: row.top_driver_3, val: +row.top_driver_3_shap || 0 },
        ].filter((d) => d.name);

        if (!top.length) {
          el.shap.html(
            "<p class=\"hint\">No top-driver SHAP columns for this row.</p>"
          );
          return;
        }
        const W = 280;
        const H = 100;
        const m = { top: 6, right: 8, bottom: 4, left: 6 };
        const w = W - m.left - m.right;
        const h = H - m.top - m.bottom;
        const y = d3
          .scaleBand()
          .domain(top.map((d) => d.name))
          .range([0, h])
          .padding(0.25);
        const vals = top.map((d) => d.val);
        const minV = d3.min(vals);
        const maxV = d3.max(vals);
        const x = d3.scaleLinear().range([0, w]);
        if (minV < 0) {
          x.domain([minV * 1.1 - 1e-6, maxV * 1.1 + 1e-6]);
        } else {
          x.domain([0, (maxV || 0) * 1.05 + 1e-6]);
        }

        el.shap.html("");
        const s = el.shap
          .append("svg")
          .attr("viewBox", `0 0 ${W} ${H}`)
          .attr("width", "100%")
          .append("g")
          .attr("transform", `translate(${m.left},${m.top})`);

        s.append("line")
          .attr("x1", x(0))
          .attr("x2", x(0))
          .attr("y1", 0)
          .attr("y2", h)
          .attr("stroke", "#2d3a4d")
          .attr("stroke-width", 1);

        s.selectAll("rect")
          .data(top)
          .join("rect")
          .attr("class", (d) => "bar" + (d.val < 0 ? " neg" : ""))
          .attr("x", (d) => Math.min(x(0), x(d.val)))
          .attr("y", (d) => y(d.name))
          .attr("width", (d) => Math.abs(x(d.val) - x(0)))
          .attr("height", y.bandwidth());

        s.selectAll("text.lbl")
          .data(top)
          .join("text")
          .attr("class", "bar-label")
          .attr("x", 0)
          .attr("y", (d) => y(d.name) + y.bandwidth() / 2)
          .attr("dy", "0.32em")
          .text((d) => d.name);
      }

      function showDetail(feature) {
        const gid = feature.properties.grid_id;
        const dStr = currentDateStr();
        const rmap = rowMap();
        const row = rmap.get(gid);

        if (!row) {
          el.asideTitle.text(gid);
          el.detail.html(
            "<p class=\"hint\">No model row for this cell and date in model_results.csv.</p>"
          );
          el.explain.html("");
          el.shap.html("");
          return;
        }

        el.asideTitle.text(gid);
        const metric = el.metric.property("value");
        const keys = [
          "date",
          "incident_count",
          "temperature",
          "humidity",
          "precipitation",
          "wind",
          "rolling_sum_7",
          "rolling_sum_14",
          "rf_prob",
          "rf_pred",
          "hotspot_prob",
          "arima_prob",
          "arima_pred",
        ];
        const exRow = explainLookup
          ? explainLookup(gid, dStr)
          : null;
        if (exRow) {
          shapBarChart(exRow);
          el.explain.html(
            exRow.explanation_text
              ? "<div class=\"explain-box\">" +
                exRow.explanation_text +
                "</div>"
              : ""
          );
        } else {
          const altDates = explainDatesForGrid(gid);
          const subsetNote =
            "<p class=\"hint\">SHAP text and driver bars are only in " +
            "<code>outputs/interpretability/explanations.csv</code> for a " +
            "<strong>small curated subset</strong> of (cell, date) pairs " +
            "(e.g. high <code>rf_prob</code> runs), not for every grid day.</p>";
          if (altDates.length) {
            el.explain.html(
              subsetNote +
                "<p class=\"hint\">For <strong>" +
                gid +
                "</strong>, that file includes dates: " +
                altDates.join(", ") +
                ". Move the <strong>time scrubber</strong> (slider or ← →) to " +
                "one of those days to load the narrative and SHAP bars.</p>"
            );
          } else {
            el.explain.html(
              subsetNote +
                "<p class=\"hint\">This grid id never appears in that file; " +
                "pick another cell or extend the pipeline to export SHAP for " +
                "more (grid_id, date) rows.</p>"
            );
          }
          el.shap.html("");
        }

        const rows = keys
          .filter(
            (k) =>
              row[k] !== undefined &&
              row[k] !== null &&
              String(row[k]) !== ""
          )
          .map(
            (k) =>
              "<tr><th>" +
              k +
              "</th><td>" +
              (typeof row[k] === "number" ? fmt2(row[k]) : String(row[k])) +
              (k === metric ? " (mapped)" : "") +
              "</td></tr>"
          );
        el.detail.html(
          "<table class=\"dl-table\">" + rows.join("") + "</table>"
        );
      }

      function invalidateMapSize() {
        map.invalidateSize();
        try {
          map.fitBounds(geoLayer.getBounds(), { padding: [12, 12], maxZoom: 13 });
        } catch (e) {
          /* ignore */
        }
      }

      syncDateUI();
      el.dateSlider.on("input", () => {
        dateIndex = Number(el.dateSlider.property("value"));
        syncDateUI();
        onDateChangedByUser();
      });
      el.datePrev.on("click", () => {
        if (dateIndex > 0) {
          dateIndex -= 1;
          syncDateUI();
          onDateChangedByUser();
        }
      });
      el.dateNext.on("click", () => {
        if (dateIndex < dates.length - 1) {
          dateIndex += 1;
          syncDateUI();
          onDateChangedByUser();
        }
      });
      el.metric.on("change", () => {
        selectedGid = null;
        renderMap();
      });

      d3.select(window).on("resize", invalidateMapSize);
      if (typeof ResizeObserver !== "undefined") {
        const ro = new ResizeObserver(() => {
          requestAnimationFrame(invalidateMapSize);
        });
        ro.observe(document.getElementById("map-container"));
      }
      setTimeout(invalidateMapSize, 50);
      setTimeout(invalidateMapSize, 300);

      renderMap();
    })
    .catch((e) => {
      console.error(e);
      showError(
        (e && e.message) ||
          "Load failed. Serve the repo with a local web server; file:// blocks fetch. Example: python3 -m http.server 8000"
      );
    });
})();
