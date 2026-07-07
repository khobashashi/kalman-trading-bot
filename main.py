import time
from datetime import datetime
import numpy as np
import pandas as pd
import yfinance as yf

# Standard 1D Kalman Filter Engine
class RealTimeKalman:
    def __init__(self, initial_price, Q=1e-4, R=1e-2):
        self.x = initial_price  
        self.P = 1.0            
        self.Q = Q              
        self.R = R              

    def update(self, measurement):
        x_pred = self.x
        P_pred = self.P + self.Q
        residual = measurement - x_pred
        S = P_pred + self.R        
        K = P_pred / S             
        self.x = x_pred + K * residual
        self.P = (1 - K) * P_pred
        return self.x, np.sqrt(S)

def run_live_market_bot(ticker_symbol, deviation_threshold=1.5):
    print(f"Initializing Live Kalman Filter for {ticker_symbol}...")
    
    ticker = yf.Ticker(ticker_symbol)
    
    # Initialize the filter with the absolute latest price available right now
    initial_df = ticker.history(period="1d", interval="1m")
    if initial_df.empty:
        print("Market appears to be closed right now, but initializing anyway.")
        # Fallback to last known price if market hasn't opened yet
        last_price = ticker.fast_info.get('lastPrice', 150.0) 
    else:
        last_price = initial_df['Close'].iloc[-1]
        
    kf = RealTimeKalman(initial_price=last_price, Q=0.0001, R=0.01)
    last_processed_timestamp = None

    print(f"Live Tracking Started. Checking prices every 60 seconds...")
    print(f"{'Time (EST)':<12} | {'Live Price':<10} | {'Kalman Est':<10} | {'Signal':<8}")
    print("-" * 55)

    # Infinite loop that keeps running in the cloud
    while True:
        # Check current time in Eastern Standard Time (New York Time)
        # Using a simple conversion since GitHub servers run on UTC time
        current_utc_hour = datetime.utcnow().hour
        current_utc_minute = datetime.utcnow().minute
        
        # Market closes at 4:00 PM EST (which is 8:00 PM or 9:00 PM UTC depending on daylight savings)
        # If the script hits the GitHub 6-hour limit first, GitHub will safely stop it for us.
        
        try:
            # Fetch the most recent 1-minute bars
            df = ticker.history(period="1d", interval="1m")
            if not df.empty:
                latest_row = df.iloc[-1]
                latest_timestamp = df.index[-1]
                live_price = float(latest_row['Close'])
                
                # Only run calculation if a brand new minute-bar has completed
                if latest_timestamp != last_processed_timestamp:
                    last_processed_timestamp = latest_timestamp
                    
                    kalman_est, std_dev = kf.update(live_price)
                    
                    upper_band = kalman_est + (deviation_threshold * std_dev)
                    lower_band = kalman_est - (deviation_threshold * std_dev)
                    
                    if live_price > upper_band:
                        signal = "SHORT 🔴"
                        if current_position == 1: 
                            trading_client.close_all_positions(cancel_orders=True) # Closes everything
                            action_taken = "CLOSED LONG POSITION"
                            current_position = 0
                    elif live_price < lower_band:
                        signal = "LONG  🟢"
                        if current_position <= 0:
                            order = MarketOrderRequest(
                                symbol="BTC/USD", # Alpaca requires a slash for Crypto pairs
                                notional=1000,    # Buy exactly $1,000 worth of Bitcoin
                                side=OrderSide.BUY,
                                time_in_force=TimeInForce.GTC
                            )
                            trading_client.submit_order(order)
                            action_taken = "EXECUTED BUY"
                            current_position = 1
                    else:
                        signal = "HOLD  ⚪"
                        
                    time_str = datetime.now().strftime('%H:%M:%S')
                    print(f"{time_str:<12} | {live_price:<10.2f} | {kalman_est:<10.2f} | {signal}")
                    
        except Exception as e:
            print(f"Error fetching data: {e}. Retrying...")
            
        # Wait 60 seconds before pulling the market price again
        time.sleep(900) 

if __name__ == "__main__":
    # Tracks Apple (AAPL) by default all day
    run_live_market_bot("BTC-USD", deviation_threshold=1.0)
