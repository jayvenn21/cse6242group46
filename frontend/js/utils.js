export function createFormatters(d3) {
  return {
    fmt: d3.format(".3f"),
    fmt2: d3.format(".2f"),
  };
}

export function fieldHasValue(v) {
  if (v === undefined || v === null) {
    return false;
  }
  if (typeof v === "number") {
    return v === v;
  }
  if (typeof v === "string") {
    return v.trim() !== "";
  }
  return true;
}

export function valueExtent(d3, rows, key) {
  const vals = rows
    .map((d) => +d[key])
    .filter((v) => v === v);
  if (!vals.length) {
    return [0, 1];
  }
  return d3.extent(vals);
}

export function loadExplainIndex(d3, rows) {
  const m = d3.rollup(
    rows,
    (v) => v[0],
    (d) => d.grid_id,
    (d) => d.date
  );
  return (gridId, date) => m.get(gridId)?.get(String(date)) ?? null;
}

export function normDate(d) {
  if (d instanceof Date) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }
  return String(d);
}

export function parseISODate(iso) {
  const p = String(iso).split("-");
  if (p.length !== 3) {
    return new Date(iso);
  }
  return new Date(+p[0], +p[1] - 1, +p[2]);
}

export function formatDateLong(iso) {
  return parseISODate(iso).toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function colorScaleFor(d3, rows, metric) {
  const ex0 = valueExtent(d3, rows, metric);
  let lo = ex0[0];
  let hi = ex0[1];
  if (lo === hi) {
    hi = lo + 1e-9;
  }
  return d3.scaleSequential(d3.interpolateYlOrRd).domain([lo, hi]);
}
