import numpy as np
import pandas as pd
from decimal import Decimal

class FeatureEngineeringService:
    def __init__(self, sequence_length=10, num_features=6):
        self.seq_len = sequence_length
        self.num_features = num_features

    def calculate_normalized_features(self, df_m5):
        """
        Translates MQL5 GetFeaturesForSymbol into optimized Pandas math.
        Expects a DataFrame with columns: ['close', 'high', 'low'] sorted from oldest to newest.
        """
        # Ensure we have enough data to calculate metrics (20 bars minimum for Feature 3)
        if len(df_m5) < 21:
            raise ValueError("Incomplete data array provided for feature extraction.")

        features_matrix = []

        # We calculate features looking backward to construct our sequence length
        for shift in range(self.seq_len - 1, -1, -1):
            # Emulate MQL5 index slicing where 0 is current bar, 1 is previous bar
            # In standard Pandas, the last row [-1] is current, [-2] is shift=1
            idx = len(df_m5) - 1 - shift
            
            row_features = [0.0] * self.num_features
            
            # MQL5: features[0] = (close[0] - close[1]) / close[1];
            close_0 = df_m5['close'].iloc[idx]
            close_1 = df_m5['close'].iloc[idx - 1]
            row_features[0] = (close_0 - close_1) / close_1

            # MQL5: features[1] = (close[0] - close[5]) / close[5];
            close_5 = df_m5['close'].iloc[idx - 5]
            row_features[1] = (close_0 - close_5) / close_5

            # MQL5: iATR(symbol, PERIOD_M5, 14)
            # Replicate basic ATR calculation for Feature 2
            high_slice = df_m5['high'].iloc[idx-14:idx+1]
            low_slice = df_m5['low'].iloc[idx-14:idx+1]
            close_slice = df_m5['close'].iloc[idx-15:idx]
            
            tr1 = high_slice - low_slice
            tr2 = (high_slice - close_slice.values).abs()
            tr3 = (low_slice - close_slice.values).abs()
            true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr_val = true_range.mean()
            
            # Represent raw pips division (assuming Gold point spacing value of 0.1)
            point_value = 0.1 
            row_features[2] = atr_val / point_value

            # MQL5: eq = (high20[ArrayMaximum] + low20[ArrayMinimum]) / 2.0; 
            #       features[3] = (close[0] - eq) / eq;
            high_20 = df_m5['high'].iloc[idx-20:idx].max()
            low_20 = df_m5['low'].iloc[idx-20:idx].min()
            eq = (high_20 + low_20) / 2.0
            row_features[3] = (close_0 - eq) / eq

            # Feature 4 & 5 placeholders (OFI and VAP metrics)
            row_features[4] = 0.0
            row_features[5] = 0.0

            # Apply identical scaling multipliers and boundaries
            for i in range(self.num_features):
                if i in [0, 1, 3]:
                    row_features[i] *= 100.0
                # Strict clipping boundary to match MQL5 MathMax/MathMin bounds
                row_features[i] = max(-1.0, min(1.0, row_features[i]))

            features_matrix.append(row_features)

        return features_matrix

    def generate_simulation_data(self, base_price=2350.0, bars=50):
        """Generates random mock bars for pure local sandbox execution inside Codespaces."""
        np.random.seed(42)
        closes = [base_price]
        for _ in range(bars - 1):
            closes.append(closes[-1] + np.random.uniform(-3.0, 3.0))
            
        df = pd.DataFrame({'close': closes})
        df['high'] = df['close'] + np.random.uniform(0.5, 2.0, size=bars)
        df['low'] = df['close'] - np.random.uniform(0.5, 2.0, size=bars)
        return df


import random
import time

class XAUUSDMarketSimulator:
    """
    Generates rolling OHLC dataframes matching the structure 
    expected by FeatureEngineeringService.
    """
    def __init__(self):
        self.current_price = 2350.00

    def generate_market_dataframe(self, ticks_count=50):
        data = []
        base_time = time.time() - (ticks_count * 60)
        
        for i in range(ticks_count):
            change = round(random.uniform(-2.0, 2.0), 2)
            open_p = self.current_price
            close_p = round(open_p + change, 2)
            high_p = round(max(open_p, close_p) + random.uniform(0, 1.0), 2)
            low_p = round(min(open_p, close_p) - random.uniform(0, 1.0), 2)
            
            data.append({
                "timestamp": base_time + (i * 60),
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p,
                "volume": random.randint(100, 500)
            })
            self.current_price = close_p

        return pd.DataFrame(data)