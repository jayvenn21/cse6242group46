import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score,
    roc_curve, precision_recall_curve,
    confusion_matrix, classification_report,
)



plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "#f8f9fa",
    "axes.grid": True,
    "grid.alpha": 0.3,
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
})

colors = {
    "Historical Hotspot": "#e74c3c",
    "ARIMA": "#3498db",
    "Random Forest": "#2ecc71",
}


def compute_metrics(y_true, y_pred, y_prob=None):
    metrics = {
        "Accuracy": accuracy_score(y_true, y_pred),
        "Precision": precision_score(y_true, y_pred, zero_division=0),
        "Recall": recall_score(y_true, y_pred, zero_division=0),
        "F1-Score": f1_score(y_true, y_pred, zero_division=0),
    }
    if y_prob is not None:
        try:
            metrics["ROC-AUC"] = roc_auc_score(y_true, y_prob)
        except ValueError:
            metrics["ROC-AUC"] = np.nan
        try:
            metrics["PR-AUC"] = average_precision_score(y_true, y_prob)
        except ValueError:
            metrics["PR-AUC"] = np.nan
    return metrics


def evaluate_all_models(test_df):
    y_true = test_df["target_next_interval"].values

    models = {}
    if "hotspot_pred" in test_df.columns:
        models["Historical Hotspot"] = {
            "y_pred": test_df["hotspot_pred"].values,
            "y_prob": test_df["hotspot_prob"].values,
        }
    if "arima_pred" in test_df.columns:
        models["ARIMA"] = {
            "y_pred": test_df["arima_pred"].values,
            "y_prob": test_df["arima_prob"].values,
        }
    if "rf_pred" in test_df.columns:
        models["Random Forest"] = {
            "y_pred": test_df["rf_pred"].values,
            "y_prob": test_df["rf_prob"].values,
        }

    rows = []
    for name, preds in models.items():
        m = compute_metrics(y_true, preds["y_pred"], preds["y_prob"])
        m["Model"] = name
        rows.append(m)

    return pd.DataFrame(rows).set_index("Model")


def plot_roc_curves(test_df, plot_dir, save_path=None):
    y_true = test_df["target_next_interval"].values
    fig, ax = plt.subplots(figsize=(7, 6))

    prob_cols = {
        "Historical Hotspot": "hotspot_prob",
        "ARIMA": "arima_prob",
        "Random Forest": "rf_prob",
    }

    for name, col in prob_cols.items():
        if col not in test_df.columns:
            continue
        fpr, tpr, _ = roc_curve(y_true, test_df[col].values)
        auc_val = roc_auc_score(y_true, test_df[col].values)
        ax.plot(fpr, tpr, label=f"{name} (AUC={auc_val:.3f})",
                color=colors.get(name, "gray"), lw=2)

    ax.plot([0, 1], [0, 1], "k--", alpha=0.4, lw=1)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC Curves — Baseline Model Comparison")
    ax.legend(loc="lower right")
    plt.tight_layout()

    save_path = save_path or os.path.join(plot_dir, "roc_curves.png")
    fig.savefig(save_path, dpi=150)
    plt.close(fig)


def plot_pr_curves(test_df, plot_dir, save_path=None):
    y_true = test_df["target_next_interval"].values
    fig, ax = plt.subplots(figsize=(7, 6))

    prob_cols = {
        "Historical Hotspot": "hotspot_prob",
        "ARIMA": "arima_prob",
        "Random Forest": "rf_prob",
    }

    for name, col in prob_cols.items():
        if col not in test_df.columns:
            continue
        prec, rec, _ = precision_recall_curve(y_true, test_df[col].values)
        ap = average_precision_score(y_true, test_df[col].values)
        ax.plot(rec, prec, label=f"{name} (AP={ap:.3f})",
                color=colors.get(name, "gray"), lw=2)

    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("Precision-Recall Curves — Baseline Model Comparison")
    ax.legend(loc="upper right")
    plt.tight_layout()

    save_path = save_path or os.path.join(plot_dir, "precision_recall_curves.png")
    fig.savefig(save_path, dpi=150)
    plt.close(fig)


def plot_confusion_matrices(test_df, plot_dir, save_path=None):
    y_true = test_df["target_next_interval"].values
    pred_cols = {
        "Historical Hotspot": "hotspot_pred",
        "ARIMA": "arima_pred",
        "Random Forest": "rf_pred",
    }

    active = [(n, c) for n, c in pred_cols.items() if c in test_df.columns]
    n_models = len(active)
    fig, axes = plt.subplots(1, n_models, figsize=(5 * n_models, 4.5))
    if n_models == 1:
        axes = [axes]

    for ax, (name, col) in zip(axes, active):
        cm = confusion_matrix(y_true, test_df[col].values)
        im = ax.imshow(cm, cmap="Blues", aspect="auto")
        ax.set_xticks([0, 1])
        ax.set_yticks([0, 1])
        ax.set_xticklabels(["No Fire", "Fire"])
        ax.set_yticklabels(["No Fire", "Fire"])
        for i in range(2):
            for j in range(2):
                ax.text(j, i, f"{cm[i, j]:d}",
                        ha="center", va="center",
                        color="white" if cm[i, j] > cm.max() / 2 else "black",
                        fontsize=12)
        ax.set_title(name)
        ax.set_xlabel("Predicted")
        ax.set_ylabel("Actual")

    plt.suptitle("Confusion Matrices — Baseline Models", fontsize=14, y=1.02)
    plt.tight_layout()

    save_path = save_path or os.path.join(plot_dir, "confusion_matrices.png")
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_metrics_comparison(results_df, plot_dir, save_path=None):
    metrics_to_plot = ["Precision", "Recall", "F1-Score", "ROC-AUC", "PR-AUC"]
    available = [m for m in metrics_to_plot if m in results_df.columns]

    plot_data = results_df[available].reset_index()
    plot_data = plot_data.melt(id_vars="Model", var_name="Metric", value_name="Score")

    fig, ax = plt.subplots(figsize=(10, 5.5))
    models_list = plot_data["Model"].unique()
    x = np.arange(len(available))
    width = 0.25

    for i, model in enumerate(models_list):
        subset = plot_data[plot_data["Model"] == model]
        vals = [subset[subset["Metric"] == m]["Score"].values[0] for m in available]
        ax.bar(x + i * width, vals, width, label=model,
               color=colors.get(model, "gray"), edgecolor="white", linewidth=0.5)

    ax.set_xticks(x + width)
    ax.set_xticklabels(available, rotation=15)
    ax.set_ylabel("Score")
    ax.set_ylim(0, 1.05)
    ax.set_title("Model Comparison — Key Metrics")
    ax.legend()
    plt.tight_layout()

    save_path = save_path or os.path.join(plot_dir, "metrics_comparison.png")
    fig.savefig(save_path, dpi=150)
    plt.close(fig)


def plot_feature_importance(model, feature_names, plot_dir, save_path=None):
    importances = model.feature_importances_
    idx = np.argsort(importances)[::-1]

    idx = idx[:15]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(
        [feature_names[i] for i in idx],
        importances[idx],
        color="#2ecc71", edgecolor="white", linewidth=0.5,
    )
    ax.invert_yaxis()
    ax.set_xlabel("Importance")
    ax.set_title("Random Forest — Feature Importances")
    plt.tight_layout()

    save_path = save_path or os.path.join(plot_dir, "feature_importance.png")
    fig.savefig(save_path, dpi=150)
    plt.close(fig)


def write_evaluation_report(results_df, test_df, output_dir, save_path=None):
    save_path = save_path or os.path.join(output_dir, "evaluation_report.txt")

    lines = [
        "=" * 65,
        "  BASELINE MODELS — EVALUATION REPORT",
        "=" * 65,
        "",
        f"Test set size: {len(test_df):,} cell-month observations",
        f"Positive class (target_next_interval=1): {test_df['target_next_interval'].sum():,} "
        f"({test_df['target_next_interval'].mean():.1%})",
        f"Negative class (target_next_interval=0): {(test_df['target_next_interval'] == 0).sum():,} "
        f"({1 - test_df['target_next_interval'].mean():.1%})",
        "",
        "─" * 65,
        "  METRICS SUMMARY",
        "─" * 65,
        "",
        results_df.to_string(float_format="{:.4f}".format),
        "",
        "─" * 65,
        "  CLASSIFICATION REPORTS",
        "─" * 65,
    ]

    y_true = test_df["target_next_interval"].values
    pred_map = {
        "Historical Hotspot": "hotspot_pred",
        "ARIMA": "arima_pred",
        "Random Forest": "rf_pred",
    }
    for name, col in pred_map.items():
        if col in test_df.columns:
            lines.append(f"\n>> {name}:")
            lines.append(classification_report(
                y_true, test_df[col].values,
                target_names=["No Fire", "Fire"], zero_division=0,
            ))

    report_text = "\n".join(lines)
    with open(save_path, "w") as f:
        f.write(report_text)


def run_evaluation(test_df, config, rf_model=None, rf_feature_names=None):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, config["paths"]["output_dir"])
    plot_dir = os.path.join(script_dir, config["paths"]["plot_dir"])
    os.makedirs(plot_dir, exist_ok=True)

    results_df = evaluate_all_models(test_df)

    plot_roc_curves(test_df, plot_dir)
    plot_pr_curves(test_df, plot_dir)
    plot_confusion_matrices(test_df, plot_dir)
    plot_metrics_comparison(results_df, plot_dir)

    if rf_model is not None and rf_feature_names is not None:
        plot_feature_importance(rf_model, rf_feature_names, plot_dir)

    write_evaluation_report(results_df, test_df, output_dir)

    save_df = test_df.copy()
    save_df["date"] = save_df["date"].astype(str)
    results_path = os.path.join(output_dir, "model_results.csv")
    save_df.to_csv(results_path, index=False)

    return results_df
