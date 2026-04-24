#!/usr/bin/env python3
"""
Generate the team046 project poster as a single-slide 30x40 inch .pptx.
"""

import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "docs", "team046poster.pptx")

W, H = Inches(30), Inches(40)

# colors
BANNER_BG = RGBColor(0xC0, 0x39, 0x2B)
HEADING_COLOR = RGBColor(0xC0, 0x39, 0x2B)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BLACK = RGBColor(0x22, 0x22, 0x22)
DARK_GRAY = RGBColor(0x44, 0x44, 0x44)
LIGHT_BG = RGBColor(0xF8, 0xF8, 0xF8)

COL_LEFT = Inches(0.6)
COL_RIGHT = Inches(15.5)
COL_W = Inches(13.8)
MARGIN = Inches(0.6)


def add_rect(slide, left, top, width, height, fill):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.fill.background()
    return shape


def add_textbox(slide, left, top, width, height):
    return slide.shapes.add_textbox(left, top, width, height)


def set_text(tf, text, size=20, bold=False, color=BLACK, align=PP_ALIGN.LEFT):
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(size)
    p.font.bold = bold
    p.font.color.rgb = color
    p.alignment = align
    return p


def add_paragraph(tf, text, size=20, bold=False, color=BLACK, space_before=Pt(4)):
    p = tf.add_paragraph()
    p.text = text
    p.font.size = Pt(size)
    p.font.bold = bold
    p.font.color.rgb = color
    p.space_before = space_before
    return p


def add_heading(slide, left, top, width, text):
    tb = add_textbox(slide, left, top, width, Inches(0.55))
    set_text(tb.text_frame, text, size=28, bold=True, color=HEADING_COLOR)
    # underline bar
    add_rect(slide, left, top + Inches(0.5), width, Inches(0.04), HEADING_COLOR)
    return top + Inches(0.6)


def add_bullets(slide, left, top, width, height, items, size=20):
    tb = add_textbox(slide, left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        if i == 0:
            set_text(tf, f"\u2022  {item}", size=size, color=DARK_GRAY)
        else:
            add_paragraph(tf, f"\u2022  {item}", size=size, color=DARK_GRAY,
                          space_before=Pt(8))
    return tb


def add_image(slide, path, left, top, width=None, height=None):
    full = os.path.join(REPO, path)
    if not os.path.exists(full):
        print(f"  [warn] missing: {full}")
        return None
    kwargs = {"left": left, "top": top}
    if width:
        kwargs["width"] = width
    if height:
        kwargs["height"] = height
    return slide.shapes.add_picture(full, **kwargs)


def build():
    prs = Presentation()
    prs.slide_width = W
    prs.slide_height = H
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank

    # ── title banner ──────────────────────────────────────────────
    add_rect(slide, 0, 0, W, Inches(3.2), BANNER_BG)

    tb = add_textbox(slide, Inches(0.8), Inches(0.5), Inches(28.4), Inches(1.4))
    set_text(tb.text_frame,
             "Ignition Insights: Explaining and Forecasting Urban Fire Risk",
             size=52, bold=True, color=WHITE, align=PP_ALIGN.CENTER)

    tb = add_textbox(slide, Inches(0.8), Inches(2.0), Inches(28.4), Inches(0.6))
    set_text(tb.text_frame,
             "Team 46:  Vishruth Anand  |  Vineeth Nareddy  |  Rian Rahman  |  James Reilly  |  Jayanth Vennamreddy",
             size=26, bold=False, color=WHITE, align=PP_ALIGN.CENTER)

    tb = add_textbox(slide, Inches(0.8), Inches(2.55), Inches(28.4), Inches(0.5))
    set_text(tb.text_frame,
             "Georgia Institute of Technology  \u2014  CSE 6242 Data and Visual Analytics",
             size=22, bold=False, color=RGBColor(0xFF, 0xCC, 0xCC), align=PP_ALIGN.CENTER)

    y_start = Inches(3.6)

    # ══════════════════════════════════════════════════════════════
    # LEFT COLUMN
    # ══════════════════════════════════════════════════════════════

    # 1. INTRODUCTION / MOTIVATION
    y = add_heading(slide, COL_LEFT, y_start, COL_W, "Introduction")
    add_bullets(slide, COL_LEFT, y, COL_W, Inches(3.0), [
        "Fire departments make staffing and readiness decisions under uncertainty, "
        "yet fire incidents are not uniformly distributed across a city.",
        "Existing tools show what happened but not where risk is concentrated, "
        "how it changes over time, or why a model flags a particular area.",
        "We built an end-to-end system that forecasts short-horizon fire risk "
        "across a 1 km grid of Atlanta and explains each prediction.",
        "The goal is relative risk ranking and explanation, not perfect "
        "prediction of individual fires (0.5% positive rate).",
    ])

    # 2. DATA
    y = add_heading(slide, COL_LEFT, y_start + Inches(3.8), COL_W, "Data")
    add_bullets(slide, COL_LEFT, y, COL_W, Inches(2.8), [
        "Incidents: 1,473 geocoded fire incidents from 2024 NFIRS PDR Light "
        "(FEMA ArcGIS FeatureServer), filtered to Atlanta, fire codes 100\u2013199.",
        "Weather: Open-Meteo daily archive for Atlanta \u2014 temperature, "
        "humidity, precipitation, wind speed. One row per day, merged citywide.",
        "Grid: 1,176 cells at 1,000 m resolution over the Atlanta metro extent. "
        "364 cells have at least one fire incident in the study period.",
        "Model table: 132,860 cell-day rows with 18 features including "
        "weather, calendar, lags (1/3/7 day), and rolling sums (7/14 day).",
    ])

    # 3. METHODS
    y = add_heading(slide, COL_LEFT, y_start + Inches(7.4), COL_W, "Methods")
    add_bullets(slide, COL_LEFT, y, COL_W, Inches(4.6), [
        "Preprocessing: infer columns, standardize timestamps, project to UTM, "
        "assign grid cells, build full (cell \u00d7 date) panel with lagged features.",
        "Hotspot baseline: 2D Gaussian KDE over training cell centroids "
        "weighted by incident count. Captures static spatial density.",
        "ARIMA baseline: per-cell time-series model for up to 50 most active "
        "cells (min 5 nonzero days). Grid search over (p,d,q) by AIC.",
        "Random Forest: 300 trees, max depth 15, balanced class weights. "
        "Uses all 14 features including encoded grid_id for cell-level effects.",
        "Temporal split: first 80% of dates for training (Jan\u2013Oct), "
        "last 20% for testing (Oct 19\u2013Dec 30). No row shuffling.",
    ])

    # risk heatmap figure
    add_image(slide, "outputs/maps/risk_map_aggregate.png",
              COL_LEFT + Inches(1.5), y_start + Inches(12.5), width=Inches(10.5))

    # label under heatmap
    tb = add_textbox(slide, COL_LEFT, y_start + Inches(23.6), COL_W, Inches(0.5))
    set_text(tb.text_frame,
             "Figure 1: Aggregate RF risk heatmap across all test dates (Atlanta 1 km grid)",
             size=18, bold=False, color=DARK_GRAY, align=PP_ALIGN.CENTER)

    # 4. INTERACTIVE DASHBOARD
    y = add_heading(slide, COL_LEFT, y_start + Inches(24.5), COL_W,
                    "Interactive Dashboard")
    add_bullets(slide, COL_LEFT, y, COL_W, Inches(2.8), [
        "Leaflet basemap + D3 analytical views in a single-page web app.",
        "Metric dropdown: RF probability, hotspot, ARIMA, incident count, target.",
        "Date slider with play/pause animates through 73 test dates; all views update together.",
        "Click a cell to see: score histogram, probability time series, "
        "feature snapshot, and SHAP explanation with driver bar chart.",
    ])

    # dashboard screenshot
    add_image(slide, "outputs/frontend-captures/app_full.png",
              COL_LEFT + Inches(0.5), y_start + Inches(28.0), width=Inches(12.8))

    # caption
    tb = add_textbox(slide, COL_LEFT, y_start + Inches(35.4), COL_W, Inches(0.5))
    set_text(tb.text_frame,
             "Figure 2: Dashboard with choropleth map, time slider, histogram, "
             "and SHAP explanation panel",
             size=18, bold=False, color=DARK_GRAY, align=PP_ALIGN.CENTER)

    # ══════════════════════════════════════════════════════════════
    # RIGHT COLUMN
    # ══════════════════════════════════════════════════════════════

    # 5. RESULTS
    y = add_heading(slide, COL_RIGHT, y_start, COL_W, "Results")
    add_bullets(slide, COL_RIGHT, y, COL_W, Inches(4.2), [
        "Test set: 26,572 cell-date observations, 138 positive (0.52%). "
        "Extreme imbalance makes accuracy misleading (all models > 98%).",
        "Random Forest achieves the best ranking: ROC-AUC 0.65, PR-AUC 0.014 "
        "(\u22483\u00d7 better than random at this positive rate).",
        "Hotspot baseline captures some positives (recall 7.25%) but has "
        "low precision (2.74%). ARIMA improves ranking slightly (ROC-AUC 0.59).",
        "RF threshold yields 0 true positives, but the probability surface "
        "is more informative \u2014 we use it as a continuous risk map, not an alarm.",
    ])

    # metrics comparison figure
    add_image(slide, "baselines/outputs/plots/metrics_comparison.png",
              COL_RIGHT + Inches(0.3), y_start + Inches(4.8), width=Inches(12.8))

    # caption
    tb = add_textbox(slide, COL_RIGHT, y_start + Inches(12.0), COL_W, Inches(0.5))
    set_text(tb.text_frame,
             "Figure 3: Model comparison \u2014 key evaluation metrics",
             size=18, bold=False, color=DARK_GRAY, align=PP_ALIGN.CENTER)

    # ROC curves
    add_image(slide, "baselines/outputs/plots/roc_curves.png",
              COL_RIGHT + Inches(1.5), y_start + Inches(12.8), width=Inches(10.5))

    # caption
    tb = add_textbox(slide, COL_RIGHT, y_start + Inches(21.8), COL_W, Inches(0.5))
    set_text(tb.text_frame,
             "Figure 4: ROC curves for all three baseline models",
             size=18, bold=False, color=DARK_GRAY, align=PP_ALIGN.CENTER)

    # 6. INTERPRETABILITY
    y = add_heading(slide, COL_RIGHT, y_start + Inches(22.5), COL_W,
                    "Interpretability")
    add_bullets(slide, COL_RIGHT, y, COL_W, Inches(2.2), [
        "SHAP TreeExplainer on the RF model generates per-feature "
        "contributions for each cell-date prediction.",
        "Top drivers for high-risk cells: rolling_sum_14, rolling_sum_7 "
        "(recent local activity), followed by month, wind, and grid location.",
        "Narrative explanations are generated and displayed in the dashboard "
        "for every high-probability cell-date.",
    ])

    # SHAP figure
    add_image(slide, "outputs/interpretability/shap_bar.png",
              COL_RIGHT + Inches(2.0), y_start + Inches(25.5), width=Inches(9.5))

    # caption
    tb = add_textbox(slide, COL_RIGHT, y_start + Inches(33.4), COL_W, Inches(0.5))
    set_text(tb.text_frame,
             "Figure 5: SHAP feature importance (mean |SHAP value|)",
             size=18, bold=False, color=DARK_GRAY, align=PP_ALIGN.CENTER)

    # 7. CONCLUSIONS
    y = add_heading(slide, COL_RIGHT, y_start + Inches(34.2), COL_W, "Conclusions")
    add_bullets(slide, COL_RIGHT, y, COL_W, Inches(2.0), [
        "At 0.5% positive rate, binary metrics are insufficient \u2014 "
        "ranked risk surfaces are more useful than yes/no alarms.",
        "Linked views (map + timeline + histogram + explanation) make model "
        "outputs easier to understand and critique than static heatmaps.",
        "Future work: add census/land-use features, improve threshold "
        "calibration, try gradient boosting, conduct a formal user study.",
    ], size=19)

    # REFERENCES
    tb = add_textbox(slide, COL_RIGHT, y_start + Inches(36.0), COL_W, Inches(0.4))
    set_text(tb.text_frame, "References", size=22, bold=True, color=HEADING_COLOR)

    refs = (
        "[1] Wang et al., CityGuard, ACM IMWUT 2019.  "
        "[2] Coffield et al., Fire size prediction, IJWF 2019.  "
        "[3] Lattimer et al., ML in fire simulation, FSJ 2020.  "
        "[4] Asgary et al., Toronto fire clustering, 2010.  "
        "[5] Yuan & Wylie, ARIMA vs RF for Austin fires, 2024.  "
        "[6] Madaio et al., Firebird Atlanta, 2016.  "
        "[7] Jin et al., Deep sequence fire forecasting, ASC 2020.  "
        "[8] Ahn et al., Stacking ensemble fire risk, Fire 2024.  "
        "[9] Zhang et al., Firefighter demand prediction, FSJ 2024.  "
        "[10] Ku et al., GIS fire drivers, 2024.  "
        "[11] Cui et al., Ensemble fire risk, IJDRR 2024.  "
        "[12] Liao et al., Residential fire factors, 2024.  "
        "[13] Kang et al., GIS+ML fire risk, Sustainability 2018.  "
        "[14] Xiao et al., Spatial fire hazard, AAP 2018.  "
        "[15] Jennings, Socioeconomic fire risk, FSJ 2013."
    )
    tb = add_textbox(slide, COL_RIGHT, y_start + Inches(36.4), COL_W, Inches(0.8))
    tf = tb.text_frame
    tf.word_wrap = True
    set_text(tf, refs, size=14, color=DARK_GRAY)

    # ── save ──────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    prs.save(OUT)
    print(f"Saved poster to {OUT}")
    print(f"  Slide size: {prs.slide_width / 914400:.0f} x {prs.slide_height / 914400:.0f} inches")


if __name__ == "__main__":
    build()
