import time
import numpy as np
import pandas as pd
import yfinance as yf

class RealTimeKalman:
    def __init__(self, initial_price, Q=1e-4, R=1e-2):
        """
        Q: Process noise covariance (How fast the 'true' trend changes)
        R: Measurement noise covariance (How much market noise/volatility exists)
        """
        self.x = initial_price  # Hidden true state estimate
        self.P = 1.0            # Initial estimation error variance
        self.Q = Q              
        self.R = R              

    def update(self, measurement):
        # 1. Predict Step
        x_pred = self.x
        P_pred = self.P + self.Q

        # 2. Update Step (Correcting with live data)
        residual = measurement - x_pred
        S = P_pred + self.R        # Total innovation variance
        K = P_pred / S             # Kalman Gain

        self.x = x_pred + K * residual
        self.P = (1 - K) * P_pred

        # Returns updated price estimate and the standard deviation of noise
        return self.x, np.sqrt(S)

def run_realtime_trader(ticker_symbol, deviation_threshold=2.0):
    print(f"Fetching real-time 1-minute data for {ticker_symbol}...")
    # Fetching today's 1-minute bars to simulate live streaming
    ticker = yf.Ticker(ticker_symbol)
    df = ticker.history(period="1d", interval="1m")
    
    if df.empty:
        print("No data found. Ensure the market is open or check the ticker symbol.")
        return

    prices = df['Close'].dropna().values
    timestamps = df.index
    
    # Initialize the Kalman filter with the first known price
    kf = RealTimeKalman(initial_price=prices[0], Q=0.0001, R=0.01)
    
    print("\n--- Starting Live Kalman Filter Tracking ---")
    print(f"{'Timestamp':<20} | {'Live Price':<10} | {'Kalman Est':<10} | {'Signal':<8}")
    print("-" * 60)

    # Simulating the live real-time stream loop
    for i in range(1, len(prices)):
        live_price = prices[i]
        timestamp_str = timestamps[i].strftime('%Y-%m-%d %H:%M')
        
        # Feed the single live price into our filter
        kalman_est, std_dev = kf.update(live_price)
        
        # Calculate Bollinger-like thresholds using Kalman uncertainty
        upper_band = kalman_est + (deviation_threshold * std_dev)
        lower_band = kalman_est - (deviation_threshold * std_dev)
        
        # Signal Generation Logic
        if live_price > upper_band:
            signal = "SHORT 🔴"
        elif live_price < lower_band:
            signal = "LONG  🟢"
        else:
            signal = "HOLD  ⚪"
            
        print(f"{timestamp_str:<20} | {live_price:<10.2f} | {kalman_est:<10.2f} | {signal}")
        
        # Sleep for a moment to simulate real-time ticks arriving
        time.sleep(0.5) 

if __name__ == "__main__":
    # You can change 'AAPL' to any ticker (e.g., 'NVDA', 'SPY', 'BTC-USD')
    run_realtime_trader("AAPL", deviation_threshold=1.5)
