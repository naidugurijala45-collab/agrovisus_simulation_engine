# app/utils/plot_utils.py
import matplotlib

matplotlib.use("Agg")  # Use non-interactive backend
import logging
import os

import matplotlib.pyplot as plt
import seaborn as sns

# Set a consistent style for plots
sns.set_theme(style="whitegrid")
# You might want to define a custom color palette later


def save_plot(fig, filename, output_dir="outputs/plots"):
    """Helper to save plot figures."""
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    fig.savefig(
        filepath, bbox_inches="tight", dpi=300
    )  # bbox_inches='tight' prevents labels/titles from being cut off
    plt.close(fig)  # Close the figure to free memory
    logging.info(f"Plot saved to: {filepath}")
    return filepath  # Return the path for HTML embedding


def plot_time_series(
    df_series, title, ylabel, filename="time_series.png", output_dir="outputs/plots"
):
    """
    Generates and saves a single time-series plot.
    df_series should be a pandas Series with a datetime index.
    """
    fig, ax = plt.subplots(figsize=(12, 6))
    df_series.plot(ax=ax, linewidth=2, color=sns.color_palette("viridis")[0])
    ax.set_title(title, fontsize=16)
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.tick_params(axis="x", rotation=45)
    plt.tight_layout()
    return save_plot(fig, filename, output_dir)


def plot_multiple_time_series(
    df_data,
    title,
    ylabel,
    y_columns=None,
    filename="multiple_time_series.png",
    output_dir="outputs/plots",
):
    """
    Generates and saves a time-series plot for multiple columns.
    df_data should be a pandas DataFrame with a datetime index.
    y_columns (list): List of column names to plot. If None, plots all numeric columns.
    """
    if y_columns is None:
        # Filter to only numeric columns for plotting by default
        numeric_cols = df_data.select_dtypes(include=["number"]).columns.tolist()
        plot_cols = numeric_cols
    else:
        plot_cols = [col for col in y_columns if col in df_data.columns]

    if not plot_cols:
        logging.warning(f"No valid columns to plot for multiple time series: {title}")
        return None

    fig, ax = plt.subplots(figsize=(12, 6))

    # Use a different color palette for multiple lines
    colors = sns.color_palette("tab10", n_colors=len(plot_cols))
    for i, col in enumerate(plot_cols):
        df_data[col].plot(
            ax=ax, label=col.replace("_", " ").title(), color=colors[i], linewidth=2
        )

    ax.set_title(title, fontsize=16)
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.tick_params(axis="x", rotation=45)
    ax.legend(title="Variable")
    plt.tight_layout()
    return save_plot(fig, filename, output_dir)


def plot_bar_chart(
    data_dict,
    title,
    ylabel,
    filename="bar_chart.png",
    output_dir="outputs/plots",
    color=None,
):
    """
    Generates and saves a bar chart.
    data_dict: {'label1': value1, 'label2': value2, ...}
    """
    if not data_dict:
        logging.warning(f"No data provided for bar chart: {title}")
        return None

    labels = list(data_dict.keys())
    values = list(data_dict.values())

    fig, ax = plt.subplots(figsize=(10, 6))

    if color is None:
        # Use colors from the viridis palette for bars
        colors = sns.color_palette("viridis", n_colors=len(labels))
        ax.bar(labels, values, color=colors)
    else:
        ax.bar(labels, values, color=color)

    ax.set_title(title, fontsize=16)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.tick_params(axis="x", rotation=45)
    plt.tight_layout()
    return save_plot(fig, filename, output_dir)


def plot_comparative_time_series(
    df_dict,
    y_column,
    title,
    ylabel,
    filename="comparative_time_series.png",
    output_dir="outputs/plots",
):
    """
    Generates and saves a time-series plot comparing a single variable across multiple scenarios.
    df_dict: {'Scenario Name 1': pandas.DataFrame, 'Scenario Name 2': pandas.DataFrame, ...}
    y_column: The single column name to plot from each DataFrame.
    """
    if not df_dict:
        logging.warning(f"No data provided for comparative time series: {title}")
        return None

    fig, ax = plt.subplots(figsize=(12, 6))

    colors = sns.color_palette(
        "tab10", n_colors=len(df_dict)
    )  # Use a distinct color for each scenario

    for i, (scenario_name, df) in enumerate(df_dict.items()):
        if y_column in df.columns:
            df[y_column].plot(ax=ax, label=scenario_name, color=colors[i], linewidth=2)
        else:
            logging.warning(
                f"Column '{y_column}' not found in scenario '{scenario_name}'."
            )

    ax.set_title(title, fontsize=16)
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.tick_params(axis="x", rotation=45)
    ax.legend(title="Scenario")
    plt.tight_layout()
    return save_plot(fig, filename, output_dir)


def plot_comparative_bar_chart(
    kpis_dict,
    kpi_name,
    title,
    ylabel,
    filename="comparative_bar_chart.png",
    output_dir="outputs/plots",
):
    """
    Generates and saves a bar chart comparing a single KPI across multiple scenarios.
    kpis_dict: {'Scenario Name 1': {'kpi_name_X': value, ...}, 'Scenario Name 2': {...}}
    kpi_name: The specific KPI to compare (e.g., 'final_yield_kg_ha').
    """
    if not kpis_dict:
        logging.warning(f"No data provided for comparative bar chart: {title}")
        return None

    scenario_labels = []
    kpi_values = []
    for scenario_name, kpis in kpis_dict.items():
        if kpi_name in kpis:
            scenario_labels.append(scenario_name)
            kpi_values.append(kpis[kpi_name])
        else:
            logging.warning(
                f"KPI '{kpi_name}' not found for scenario '{scenario_name}'."
            )

    if not scenario_labels:
        return None

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(
        x=scenario_labels,
        y=kpi_values,
        hue=scenario_labels,
        ax=ax,
        palette="viridis",
        legend=False,
    )

    ax.set_title(title, fontsize=16)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_xlabel("Scenario", fontsize=12)
    ax.tick_params(axis="x", rotation=45)
    plt.tight_layout()
    return save_plot(fig, filename, output_dir)


# Add more specific plotting functions later, e.g., for stress factors, N pools, etc.
