import { DATA, METRIC_OPTIONS, TS_METRICS } from "./config.js";
import {
  createFormatters,
  fieldHasValue,
  loadExplainIndex,
  normDate,
  parseISODate,
  formatDateLong,
  colorScaleFor,
} from "./utils.js";

(function () {
  "use strict";

  const d3 = window.d3;
  const L = window.L;

  if (typeof L === "undefined" || typeof d3 === "undefined") {
    document.getElementById("error-banner").className = "error-banner visible";
    document.getElementById("error-banner").textContent =
      "Leaflet or D3 failed to load (check network / CDN).";
    return;
  }

  const { fmt, fmt2 } = createFormatters(d3);

  const el = {
    err: d3.select("#error-banner"),
    dateSlider: d3.select("#date-slider"),
    dateReadout: d3.select("#date-readout"),
    datePrev: d3.select("#date-prev"),
    dateNext: d3.select("#date-next"),
    datePlay: d3.select("#date-play-toggle"),
    timeControl: d3.select("#time-control-panel"),
    timeReadoutWrap: d3.select("#time-readout-wrap"),
    mapLegend: d3.select("#map-legend"),
    datePlayIcon: d3.select("#date-play-icon"),
    datePlayLabel: d3.select("#date-play-label"),
    metric: d3.select("#metric-select"),
    asideTitle: d3.select("#panel-title"),
    cellHint: d3.select("#cell-hint"),
    distChart: d3.select("#dist-chart"),
    tsChart: d3.select("#ts-chart"),
    tableWrap: d3.select("#table-wrap"),
    shap: d3.select("#shap-chart"),
    status: d3.select("#map-status"),
    explain: d3.select("#explanation"),
    sectionExplain: d3.select("#section-explain"),
    sectionShap: d3.select("#section-shap"),
    sectionSnapshot: d3.select("#section-snapshot"),
    colorG: d3.select("#legend-swatch"),
    tooltip: d3.select("#chart-tooltip"),
  };

  function setInterpretationSections(exRow, hasNarrative) {
    const showExplain = Boolean(!exRow || hasNarrative);
    el.sectionExplain.property("hidden", !showExplain);
    el.sectionShap.property("hidden", !exRow);
  }

  function showError(msg) {
    el.err.classed("visible", true).text(msg);
  }

  function moveTooltip(x, y, html) {
    const pad = 12;
    const node = el.tooltip.node();
    if (!node) {
      return;
    }
    el.tooltip
      .html(html)
      .classed("visible", true)
      .attr("aria-hidden", "false");
    const tw = node.offsetWidth;
    const th = node.offsetHeight;
    const w = window.innerWidth;
    const h = window.innerHeight;
    let left = x + pad;
    let top = y + pad;
    if (left + tw > w) {
      left = x - tw - pad;
    }
    if (top + th > h) {
      top = y - th - pad;
    }
    el.tooltip.style("left", left + "px").style("top", top + "px");
  }

  function hideTooltip() {
    el.tooltip.classed("visible", false).attr("aria-hidden", "true");
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
      const byGrid = d3.rollup(
        modelRows,
        (rows) => rows.slice().sort((a, b) => a.date.localeCompare(b.date)),
        (d) => d.grid_id
      );
      const dates = Array.from(byDate.keys()).sort();
      if (!dates.length) {
        throw new Error("No dates in model_results.csv");
      }

      const explainLookup =
        explainRows && explainRows.length
          ? loadExplainIndex(d3, explainRows)
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

      function rowsForGrid(gid) {
        return byGrid.get(gid) || [];
      }

      let dateIndex = dates.length - 1;
      let selectedGid = null;
      let selectedFeature = null;
      let playbackId = null;

      function currentDateStr() {
        return dates[dateIndex];
      }

      function dateIndexForISO(iso) {
        const t = parseISODate(iso);
        const ts = t.getTime();
        let best = 0;
        let bestD = Infinity;
        dates.forEach((d, i) => {
          const diff = Math.abs(parseISODate(d).getTime() - ts);
          if (diff < bestD) {
            bestD = diff;
            best = i;
          }
        });
        return best;
      }

      function syncDateUI() {
        const maxI = Math.max(0, dates.length - 1);
        const pct = maxI < 1 ? 100 : (dateIndex / maxI) * 100;
        el.timeReadoutWrap.style(
          "--time-progress",
          pct + "%"
        );
        el.dateSlider
          .property("max", maxI)
          .property("value", dateIndex);
        el.dateReadout.text(
          formatDateLong(currentDateStr()) +
            "  ·  " +
            (dateIndex + 1) +
            " / " +
            dates.length
        );
        el.datePrev.property("disabled", dateIndex <= 0);
        el.dateNext.property("disabled", dateIndex >= maxI);
        el.datePlay.property("disabled", dates.length < 2);
        el.dateSlider.attr("aria-valuetext", currentDateStr());
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
        minZoom: 10,
        maxZoom: 18,
        maxBoundsViscosity: 0.75,
      });

      L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
        {
          attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
          subdomains: "abcd",
        }
      ).addTo(map);

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
        const cScale = colorScaleFor(d3, sub, metric);
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
          ? "#9aa5b2"
          : currentColorScale(+row[metric]);
        return {
          fillColor: fill,
          color: selected ? "#2563eb" : "rgba(15, 23, 42, 0.3)",
          weight: selected ? 2.5 : 0.45,
          opacity: 1,
          fillOpacity: noData ? 0.55 : 0.9,
          className: "map-cell" + (selected ? " map-cell--selected" : "") + (noData ? " map-cell--nodata" : ""),
        };
      }

      syncStyleStateFromControls();

      function renderDistributionChart() {
        const metric = el.metric.property("value");
        const dStr = currentDateStr();
        const sub = byDate.get(dStr) || [];
        const label =
          METRIC_OPTIONS.find((m) => m.value === metric)?.label || metric;
        d3.select("#dist-caption").text(
          "Distribution of " +
            label +
            " across " +
            sub.length +
            " cells with a row on this date. Hover a bar for the count in that bin."
        );
        const vals = sub
          .map((d) => +d[metric])
          .filter((v) => v === v);
        el.distChart.html("");

        if (vals.length < 2) {
          el.distChart
            .append("p")
            .attr("class", "hint")
            .text("Not enough values to form a histogram for this day and metric.");
          return;
        }

        const M = { top: 6, right: 8, bottom: 42, left: 36 };
        const W = 320;
        const H = 158;
        const w = W - M.left - M.right;
        const h = H - M.top - M.bottom;

        const ex = d3.extent(vals);
        const hGen = d3
          .histogram()
          .domain(ex)
          .thresholds(14);
        const bins = hGen(vals);
        if (!bins.length) {
          return;
        }
        const maxC = d3.max(bins, (b) => b.length) || 1;
        const xH = d3
          .scaleLinear()
          .domain([bins[0].x0, bins[bins.length - 1].x1])
          .range([0, w]);
        const yH = d3.scaleLinear().domain([0, maxC]).nice().range([h, 0]);
        const axB = d3.axisBottom(xH).ticks(5).tickFormat((v) => fmt2(v));
        const axL = d3
          .axisLeft(yH)
          .ticks(4)
          .tickFormat(d3.format("d"));

        const root = el.distChart
          .append("svg")
          .attr("class", "d3-svg")
          .attr("viewBox", "0 0 " + W + " " + H)
          .attr("width", "100%");
        const g = root
          .append("g")
          .attr("transform", `translate(${M.left},${M.top})`);

        g.append("g")
          .attr("class", "axis")
          .attr("transform", `translate(0,${h})`)
          .call(axB)
          .call((gg) => gg.select(".domain").remove())
          .append("text")
          .attr("x", w / 2)
          .attr("y", 32)
          .attr("text-anchor", "middle")
          .attr("class", "axis-title")
          .text(label);

        g.append("g")
          .attr("class", "axis")
          .call(axL)
          .call((gg) => gg.select(".domain").remove());

        g.selectAll("rect.hist")
          .data(bins)
          .join("rect")
          .attr("class", "hist-bar")
          .attr("x", (b) => xH(b.x0) + 1)
          .attr("width", (b) => Math.max(0, xH(b.x1) - xH(b.x0) - 2))
          .attr("y", (b) => yH(b.length))
          .attr("height", (b) => yH(0) - yH(b.length))
          .attr("fill", "#3b5d8a")
          .on("mouseenter", function (ev, b) {
            d3.select(this).attr("fill", "#60a5fa");
            moveTooltip(
              ev.clientX,
              ev.clientY,
              "<strong>" +
                b.length +
                " cell(s)</strong><br/>[" +
                fmt2(b.x0) +
                " — " +
                fmt2(b.x1) +
                "]"
            );
          })
          .on("mouseleave", function () {
            d3.select(this).attr("fill", "#3b5d8a");
            hideTooltip();
          });
      }

      function renderTimeSeriesForGrid(gid) {
        const rows = rowsForGrid(gid);
        el.tsChart.html("");

        if (rows.length < 2) {
          el.tsChart
            .append("p")
            .attr("class", "hint")
            .text(
              "This grid has too few time points in the model CSV to draw a series."
            );
          return;
        }

        const M = { top: 12, right: 12, left: 48, bottom: 0 };
        const W = 400;
        const tMin = d3.min(rows, (d) => parseISODate(d.date));
        const tMax = d3.max(rows, (d) => parseISODate(d.date));
        const w = W - M.left - M.right;
        const h = 118;
        const xAxisLabelRoom = 40;
        const afterAxisGap = 10;
        const legY = M.top + h + xAxisLabelRoom + afterAxisGap;
        const H = legY + 16;
        const x = d3
          .scaleTime()
          .domain(
            tMin.getTime() === tMax.getTime()
              ? [
                  d3.timeDay.offset(tMin, -1),
                  d3.timeDay.offset(tMax, 1),
                ]
              : [tMin, tMax]
          )
          .range([0, w]);
        const xDom = x.domain();
        const tTick0 = xDom[0];
        const tTick1 = xDom[1];
        const tickCount = 6;
        const tickTimes =
          tTick0.getTime() === tTick1.getTime()
            ? [tTick0, d3.timeDay.offset(tTick0, 1)]
            : d3.range(0, tickCount).map((i) => {
                const t0m = tTick0.getTime();
                const t1m = tTick1.getTime();
                return new Date(
                  t0m + (i / (tickCount - 1)) * (t1m - t0m || 1)
                );
              });
        const allV = rows.flatMap((d) =>
          TS_METRICS.map((m) => +d[m.key])
            .filter((v) => v === v)
        );
        const yM = d3
          .scaleLinear()
          .domain([0, Math.max(1, d3.max(allV) || 1) * 1.05])
          .range([h, 0]);
        const curT = parseISODate(currentDateStr());
        const lineG = d3
          .line()
          .defined((d) => d._v === d._v)
          .x((d) => x(parseISODate(d.date)))
          .y((d) => yM(d._v));

        const root = el.tsChart
          .append("svg")
          .attr("class", "d3-svg d3-interactive")
          .attr("viewBox", "0 0 " + W + " " + H)
          .attr("width", "100%")
          .attr("overflow", "visible");
        const g = root
          .append("g")
          .attr("transform", `translate(${M.left},${M.top})`);

        g.append("g")
          .attr("class", "axis")
          .call(d3.axisLeft(yM).ticks(4).tickFormat((v) => fmt2(v)));

        const xg = g
          .append("g")
          .attr("class", "axis")
          .attr("transform", `translate(0,${h})`)
          .call(
            d3
              .axisBottom(x)
              .tickValues(tickTimes)
              .tickFormat(d3.timeFormat("%b %d"))
          );
        xg
          .selectAll("text")
          .attr("transform", "rotate(-32)")
          .attr("text-anchor", "end")
          .attr("dx", "-0.65em")
          .attr("dy", "0.4em");

        TS_METRICS.forEach((spec) => {
          const pts = rows
            .map((d) => ({
              date: d.date,
              _v: +d[spec.key],
            }))
            .filter((d) => d._v === d._v);
          g.append("path")
            .datum(pts)
            .attr("class", "ts-line")
            .attr("d", lineG)
            .attr("stroke", spec.color)
            .attr("fill", "none")
            .attr("stroke-width", 2.2);
        });

        g.append("line")
          .attr("class", "ts-focus")
          .attr("x1", x(curT))
          .attr("x2", x(curT))
          .attr("y1", 0)
          .attr("y2", h)
          .attr("pointer-events", "none");

        const legend = root
          .append("g")
          .attr("transform", `translate(${M.left + 2},${legY})`)
          .attr("class", "ts-legend");
        const legStep = 112;
        TS_METRICS.forEach((spec, i) => {
          const lg = legend
            .append("g")
            .attr("transform", `translate(${i * legStep},0)`);
          lg.append("line")
            .attr("x1", 0)
            .attr("x2", 20)
            .attr("y1", 0)
            .attr("y2", 0)
            .attr("stroke", spec.color)
            .attr("stroke-width", 3);
          lg.append("text")
            .attr("x", 24)
            .attr("y", 3.5)
            .attr("class", "ts-legend-text")
            .text(spec.name);
        });

        const over = g
          .append("rect")
          .attr("width", w)
          .attr("height", h)
          .attr("fill", "transparent")
          .attr("class", "ts-capture");

        const idxForMouse = (clientX) => {
          const svgN = root.node();
          if (!svgN) {
            return 0;
          }
          const box = root.node().getBoundingClientRect();
          const sc = W / box.width;
          const gx = (clientX - box.left) * sc - M.left;
          const t = x.invert(Math.max(0, Math.min(w, gx)));
          let bestI = 0;
          let bestD = Infinity;
          rows.forEach((r, i) => {
            const dt = Math.abs(parseISODate(r.date) - t);
            if (dt < bestD) {
              bestD = dt;
              bestI = i;
            }
          });
          return bestI;
        };

        over
          .on("mousemove", function (ev) {
            const i = idxForMouse(ev.clientX);
            const r = rows[i];
            const ttip = TS_METRICS.map(
              (m) =>
                "<tr><td style=\"color:" +
                m.color +
                "\">" +
                m.name +
                "</td><td>" +
                (r[m.key] === r[m.key] ? fmt2(+r[m.key]) : "—") +
                "</td></tr>"
            ).join("");
            moveTooltip(
              ev.clientX,
              ev.clientY,
              "<div class=\"tt-header\">" + r.date + "</div><table class=\"tt-table\">" + ttip + "</table>"
            );
          })
          .on("mouseleave", hideTooltip)
          .on("click", function (ev) {
            const i = idxForMouse(ev.clientX);
            dateIndex = dateIndexForISO(rows[i].date);
            syncDateUI();
            onDateChanged();
          });
      }

      function renderShapChart(row) {
        if (!row) {
          el.shap.html("");
          return;
        }
        const top = [
          { name: row.top_driver_1, val: +row.top_driver_1_shap || 0 },
          { name: row.top_driver_2, val: +row.top_driver_2_shap || 0 },
          { name: row.top_driver_3, val: +row.top_driver_3_shap || 0 },
        ]
          .filter((d) => d.name)
          .sort((a, b) => Math.abs(b.val) - Math.abs(a.val));
        if (!top.length) {
          el.shap
            .append("p")
            .attr("class", "hint")
            .text("No top-driver SHAP columns in this row.");
          return;
        }
        const M = { top: 10, right: 12, bottom: 40, left: 136 };
        const W = 320;
        const N = top.length;
        const rowH = 32;
        const h = N * rowH;
        const H = M.top + h + M.bottom;
        const w = W - M.left - M.right;
        const y = d3
          .scaleBand()
          .domain(top.map((d) => d.name))
          .range([0, h])
          .padding(0.18);
        const valsN = top.map((d) => d.val);
        const lo0 = d3.min(valsN);
        const hi0 = d3.max(valsN);
        const pad = Math.max(0.01, (hi0 - lo0) * 0.15 || 0.02);
        const x = d3
          .scaleLinear()
          .domain(
            lo0 < 0 && hi0 > 0
              ? [lo0 * 1.1 - pad, hi0 * 1.1 + pad]
              : [Math.min(0, lo0 - pad), Math.max(0, hi0 + pad)]
          )
          .range([0, w])
          .nice();

        el.shap.html("");
        const fmtShap = d3.format(".3f");
        const svg = el.shap
          .append("svg")
          .attr("class", "d3-svg d3-shap")
          .attr("viewBox", "0 0 " + W + " " + H)
          .attr("width", "100%")
          .attr("role", "img")
          .attr(
            "aria-label",
            "SHAP values: " +
              top
                .map((d) => d.name + " " + fmtShap(d.val))
                .join(", ")
          );
        const g = svg
          .append("g")
          .attr("transform", "translate(" + M.left + "," + M.top + ")");

        g.append("rect")
          .attr("x", 0)
          .attr("y", 0)
          .attr("width", w)
          .attr("height", h)
          .attr("class", "shap-plot-bg")
          .attr("rx", 4);

        g.append("line")
          .attr("class", "shap-zero")
          .attr("x1", x(0))
          .attr("x2", x(0))
          .attr("y1", 0)
          .attr("y2", h)
          .attr("pointer-events", "none");

        const xAxisG = g
          .append("g")
          .attr("class", "axis axis--shap-x")
          .attr("transform", "translate(0," + h + ")");
        xAxisG
          .call(
            d3
              .axisBottom(x)
              .ticks(5)
              .tickSizeOuter(0)
              .tickSizeInner(4)
              .tickFormat((v) => d3.format(".2f")(v))
          );
        xAxisG.select("path").attr("class", "shap-axis-domain");
        xAxisG
          .append("text")
          .attr("class", "shap-axis-title")
          .attr("x", w / 2)
          .attr("y", 32)
          .attr("text-anchor", "middle")
          .text("SHAP (impact on log-odds)");

        const labelPad = 10;
        const rowG = g
          .selectAll("g.shap-rowg")
          .data(top)
          .join("g")
          .attr("class", "shap-rowg")
          .style("cursor", "pointer")
          .attr("transform", (d) => "translate(0," + y(d.name) + ")");

        rowG.each(function (d) {
          const g0 = d3.select(this);
          const bw = y.bandwidth();
          const yc = bw / 2;
          const lab =
            d.name.length > 26
              ? d.name.slice(0, 24) + "…"
              : d.name;
          g0
            .append("text")
            .attr("class", "shap-feat")
            .attr("x", -labelPad)
            .attr("y", yc)
            .attr("dy", "0.35em")
            .attr("text-anchor", "end")
            .text(lab);
          g0
            .append("title")
            .text(
              d.name
            );
          const x0 = d.val < 0 ? x(d.val) : x(0);
          const w0 = Math.max(1, Math.abs(x(d.val) - x(0)));
          const isNeg = d.val < 0;
          g0
            .append("rect")
            .attr("class", "shap-rect")
            .attr("x", x0)
            .attr("y", 0)
            .attr("width", 0)
            .attr("height", bw)
            .attr("ry", 2)
            .attr("rx", 2)
            .attr("fill", isNeg ? "#b4533d" : "#3b7dd6")
            .transition()
            .duration(380)
            .ease(d3.easeCubicOut)
            .attr("width", w0);
          if (w0 > 18) {
            g0
              .append("text")
              .attr("class", "shap-value")
              .attr("y", yc)
              .attr("dy", "0.35em")
              .attr("opacity", 0)
              .attr(
                "x",
                d.val >= 0 ? x(d.val) + 4 : x(d.val) - 4
              )
              .attr("text-anchor", d.val >= 0 ? "start" : "end")
              .text(fmtShap(d.val))
              .transition()
              .duration(300)
              .delay(200)
              .attr("opacity", 1);
          }
        });

        rowG
          .on("mouseenter", function (ev, d) {
            moveTooltip(
              ev.clientX,
              ev.clientY,
              "<div class=\"tt-header\">" +
                d.name +
                "</div>SHAP (log-odds): <strong>" +
                fmt2(d.val) +
                "</strong><br/>Positive → higher fire log-odds; negative → lower."
            );
            d3.select(this).select("rect").attr("opacity", 0.8);
          })
          .on("mouseleave", function () {
            d3.select(this).select("rect").attr("opacity", 1);
            hideTooltip();
          });
      }

      function onDateChanged() {
        renderMap();
        renderDistributionChart();
        if (selectedFeature) {
          showDetail(selectedFeature);
        } else {
          el.asideTitle.text("Select a cell");
          el.tableWrap.html("");
          el.explain.html("");
          el.shap.html("");
          el.sectionSnapshot.property("hidden", true);
          setInterpretationSections(false, false);
          el.tsChart.html(
            "<p class=\"hint\">Select a map cell to load cross-date probability curves. Click the chart to move the time scrubber to that day.</p>"
          );
        }
        invalidateMapSize();
        if (!playbackId) {
          el.dateReadout.classed("date-readout--flash", true);
          window.setTimeout(function () {
            el.dateReadout.classed("date-readout--flash", false);
          }, 320);
        }
      }

      const geoLayer = L.geoJSON(geo, {
        style: styleForFeature,
        onEachFeature(feature, layer) {
          layer.on({
            click() {
              selectedGid = feature.properties.grid_id;
              selectedFeature = feature;
              geoLayer.setStyle(styleForFeature);
              showDetail(feature);
            },
            mouseover() {
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
              const lab = METRIC_OPTIONS.find(
                (o) => o.value === el.metric.property("value")
              )?.label;
              el.status.text(
                "Date: " + dStr + " · " + n + " modeled cells · " + lab
              );
            },
          });
        },
      }).addTo(map);

      const dataBounds = geoLayer.getBounds();
      map.setMaxBounds(dataBounds.pad(0.28));
      map.fitBounds(dataBounds, { padding: [12, 12], maxZoom: 13 });

      function renderMap() {
        const dStr = currentDateStr();
        const sub = byDate.get(dStr) || [];
        syncStyleStateFromControls();
        geoLayer.setStyle(styleForFeature);
        el.status.text(
          dStr +
            " · " +
            sub.length +
            " cells with a row (others: no data this day) · " +
            (METRIC_OPTIONS.find((o) => o.value === styleMetric)?.label ||
              styleMetric)
        );
      }

      function showDetail(feature) {
        const gid = feature.properties.grid_id;
        const dStr = currentDateStr();
        const rmap = rowMap();
        const row = rmap.get(gid);
        selectedGid = gid;
        el.asideTitle.text(gid);
        el.sectionSnapshot.property("hidden", false);
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
        const hasNarrative = Boolean(
          exRow &&
            exRow.explanation_text &&
            String(exRow.explanation_text).trim() !== ""
        );
        if (exRow) {
          renderShapChart(exRow);
          if (hasNarrative) {
            el.explain.html(
              "<div class=\"explain-box\">" +
                exRow.explanation_text +
                "</div>"
            );
          } else {
            el.explain.html("");
          }
        } else {
          const altDates = explainDatesForGrid(gid);
          const subsetNote =
            "<p class=\"hint\">SHAP and narrative text are only in " +
            "<code>explanations.csv</code> for a <strong>curated subset</strong> of (cell, date) pairs.</p>";
          if (altDates.length) {
            el.explain.html(
              subsetNote +
                "<p class=\"hint\">For <strong>" +
                gid +
                "</strong> that file has dates: " +
                altDates.join(", ") +
                ". Scrub the time control to one of these days to load them.</p>"
            );
          } else {
            el.explain.html(
              subsetNote +
                "<p class=\"hint\">This <code>grid_id</code> is not in that file.</p>"
            );
          }
          el.shap.html("");
        }

        setInterpretationSections(exRow, hasNarrative);

        renderTimeSeriesForGrid(gid);
        if (!row) {
          el.tableWrap.html(
            "<p class=\"hint\">No row in model_results.csv for " +
              dStr +
              " — the time series and map still use other rows for this <code>grid_id</code> when available.</p>"
          );
        } else {
          const tableRows = keys
            .filter((k) => fieldHasValue(row[k]))
            .map(
              (k) =>
                "<tr><th>" +
                k +
                "</th><td>" +
                (typeof row[k] === "number" ? fmt2(row[k]) : String(row[k])) +
                (k === metric ? " (mapped)" : "") +
                "</td></tr>"
            );
          if (tableRows.length) {
            el.tableWrap.html(
              "<table class=\"dl-table\">" + tableRows.join("") + "</table>"
            );
          } else {
            el.tableWrap.html(
              "<p class=\"hint\">No non-empty fields to show for this row.</p>"
            );
          }
        }
        geoLayer.setStyle(styleForFeature);
      }

      function invalidateMapSize() {
        map.invalidateSize();
        try {
          const dataBounds = geoLayer.getBounds();
          map.setMaxBounds(dataBounds.pad(0.28));
          map.fitBounds(dataBounds, { padding: [12, 12], maxZoom: 13 });
        } catch (e) {}
      }

      const PLAYBACK_MS = 600;

      function updatePlayButton() {
        const playing = playbackId != null;
        el.timeControl.classed("is-playing", playing);
        el.mapLegend.classed("is-playing", playing);
        el.datePlay
          .attr("aria-pressed", playing ? "true" : "false")
          .attr(
            "aria-label",
            playing ? "Pause date animation" : "Play through all dates from first to last"
          )
          .attr(
            "title",
            playing
              ? "Stop animation (map stays on this date)"
              : "From first date, step through to the last (~0.6s per day)"
          );
        el.datePlayIcon.text(playing ? "⏸" : "▶");
        el.datePlayLabel.text(playing ? "Pause" : "Play");
      }

      function stopPlayback() {
        if (playbackId != null) {
          clearInterval(playbackId);
          playbackId = null;
        }
        updatePlayButton();
      }

      function startPlayback() {
        stopPlayback();
        if (dates.length < 2) {
          return;
        }
        dateIndex = 0;
        syncDateUI();
        onDateChanged();
        if (dateIndex >= dates.length - 1) {
          updatePlayButton();
          return;
        }
        playbackId = setInterval(function playbackTick() {
          if (dateIndex >= dates.length - 1) {
            stopPlayback();
            return;
          }
          dateIndex += 1;
          syncDateUI();
          onDateChanged();
        }, PLAYBACK_MS);
        updatePlayButton();
      }

      syncDateUI();
      updatePlayButton();

      el.dateSlider.on("input", () => {
        stopPlayback();
        dateIndex = Number(el.dateSlider.property("value"));
        syncDateUI();
        onDateChanged();
      });
      el.datePrev.on("click", () => {
        stopPlayback();
        if (dateIndex > 0) {
          dateIndex -= 1;
          syncDateUI();
          onDateChanged();
        }
      });
      el.dateNext.on("click", () => {
        stopPlayback();
        if (dateIndex < dates.length - 1) {
          dateIndex += 1;
          syncDateUI();
          onDateChanged();
        }
      });
      el.datePlay.on("click", () => {
        if (dates.length < 2) {
          return;
        }
        if (playbackId != null) {
          stopPlayback();
        } else {
          startPlayback();
        }
      });
      el.metric.on("change", () => {
        stopPlayback();
        renderMap();
        renderDistributionChart();
        if (selectedFeature) {
          showDetail(selectedFeature);
        }
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

      el.tsChart.html(
        "<p class=\"hint\">Select a map cell. Then hover the time-series plot for all three model probabilities, or <strong>click</strong> the plot to move the time scrubber.</p>"
      );
      renderMap();
      renderDistributionChart();
    })
    .catch((e) => {
      console.error(e);
      showError(
        (e && e.message) ||
          "Load failed. Serve the repo with a local web server; file:// blocks fetch. Example: python3 -m http.server 8000"
      );
    });
})();
