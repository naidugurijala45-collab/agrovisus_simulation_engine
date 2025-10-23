# app/services/report_data_manager.py
import pandas as pd
import logging

class ReportDataManager:
    def __init__(self, simulation_csv_filepath):
        self.filepath = simulation_csv_filepath
        self.df = None
        self._load_data()

    def _load_data(self):
        """
        Loads the simulation CSV into a pandas DataFrame.
        Ensures the 'date' column is parsed correctly and set as index.
        """
        try:
            self.df = pd.read_csv(self.filepath, parse_dates=['date'], index_col='date')
            logging.info(f"Successfully loaded simulation data from {self.filepath}")
        except FileNotFoundError:
            logging.error(f"Report CSV file not found: {self.filepath}")
            self.df = pd.DataFrame() # Initialize empty DataFrame on error
        except Exception as e:
            logging.error(f"Error loading or parsing CSV {self.filepath}: {e}")
            self.df = pd.DataFrame()

    def get_daily_data(self, column_name):
        """
        Returns a pandas Series for a specific daily factor.
        """
        if self.df is not None and column_name in self.df.columns:
            return self.df[column_name]
        logging.warning(f"Column '{column_name}' not found in simulation data.")
        return pd.Series(dtype='object') # Return empty Series if not found

    def get_all_daily_data(self, column_names):
        """
        Returns a DataFrame for multiple daily factors.
        """
        if self.df is not None and all(col in self.df.columns for col in column_names):
            return self.df[column_names]
        missing_cols = [col for col in column_names if col not in self.df.columns]
        if missing_cols:
            logging.warning(f"Missing columns in simulation data: {missing_cols}")
        return pd.DataFrame()

    def get_summary_stats(self, column_name):
        """
        Returns basic summary statistics (min, max, mean, sum) for a column.
        """
        series = self.get_daily_data(column_name)
        if not series.empty and pd.api.types.is_numeric_dtype(series):
            return {
                'min': series.min(),
                'max': series.max(),
                'mean': series.mean(),
                'sum': series.sum()
            }
        return {} # Return empty dict if not numeric or not found

    def get_final_value(self, column_name):
        """
        Returns the last recorded value of a daily factor (e.g., final yield).
        """
        if self.df is not None and not self.df.empty and column_name in self.df.columns:
            return self.df[column_name].iloc[-1]
        return None

    # Add other utility methods as needed, e.g., get_data_by_date_range, etc.