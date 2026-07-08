import time
import os
from datetime import datetime
import numpy as np
import pandas as pd
import yfinance as yf

# 1. Alpaca Trading Imports (Required for automated execution)
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

# 2. Securely load your Alpaca Keys from GitHub Secrets
API_KEY = os.environ.get('ALPACA_API_KEY')
SECRET_KEY = os.environ.get('ALPACA_SECRET_KEY')

# Initialize the Alpaca Client (with a safety net if keys are missing)
if API_KEY and SECRET_KEY:
    trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)
else:
    print("⚠️ Alpaca Keys missing from GitHub Secrets. Running in simulation mode.")
    trading_client = None

# Standard 1D Kalman Filter Engine
class RealTimeKalman:
    def __init__(self, initial_price, Q=1e-5, R=1e-2):
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

def run_live_market_bot(ticker_symbol, deviation_threshold=1.0):
    print(f"Initializing Live Kalman Filter for {ticker_symbol}...")
    
    ticker = yf.Ticker(ticker_symbol)
    
    initial_df = ticker.history(period="3d", interval="1m")
    if initial_df.empty:
        print("Market appears to be closed or no data. Initializing fallback.")
        last_price = ticker.fast_info.get('lastPrice', 63000.0) 
    else:
        last_price = initial_df['Close'].iloc[-1]
        
    kf = RealTimeKalman(initial_price=last_price, Q=0.00001, R=0.01)
    last_processed_timestamp = None

    # 3. FIX: Create the state tracker BEFORE the infinite loop starts
    current_position = 0 

    print(f"Live Tracking Started. Checking prices every 15 minutes...")
    # 4. FIX: Added the 'Action' column to the print headers
    print(f"{'Time (EST)':<12} | {'Live Price':<10} | {'Kalman Est':<10} | {'Signal':<8} | {'Action'}")
    print("-" * 75)

    while True:
        try:
            # Fetch fresh 1-minute data to bypass Yahoo Finance caching
            df = ticker.history(period="1d", interval="1m")
            if not df.empty:
                latest_row = df.iloc[-1]
                latest_timestamp = df.index[-1]
                live_price = float(latest_row['Close'])
                
                if latest_timestamp != last_processed_timestamp:
                    last_processed_timestamp = latest_timestamp
                    
                    kalman_est, std_dev = kf.update(live_price)
                    
                    upper_band = kalman_est + (deviation_threshold * std_dev)
                    lower_band = kalman_est - (deviation_threshold * std_dev)
                    
                    # 5. FIX: Reset signal and action strings every loop
                    signal = "HOLD  ⚪"
                    action_taken = "None"
                    
                    if live_price > upper_band:
                        signal = "SELL 🔴"
                        # Only sell if we are currently holding Bitcoin (Long-Only strategy)
                        if current_position == 1: 
                            if trading_client:
                                trading_client.close_all_positions(cancel_orders=True) 
                                action_taken = "CLOSED LONG POSITION"
                            else:
                                action_taken = "SIMULATED SELL (No Keys)"
                            current_position = 0
                            
                    elif live_price < lower_band:
                        signal = "LONG  🟢"
                        # Only buy if we are currently flat (0)
                        if current_position <= 0:
                            if trading_client:
                                order = MarketOrderRequest(
                                    symbol="BTC/USD", 
                                    notional=1000,    
                                    side=OrderSide.BUY,
                                    time_in_force=TimeInForce.GTC
                                )
                                trading_client.submit_order(order)
                                action_taken = "EXECUTED BUY"
                            else:
                                action_taken = "SIMULATED BUY (No Keys)"
                            current_position = 1
                            
                    time_str = datetime.now().strftime('%H:%M:%S')
                    # 6. FIX: Added action_taken to the end of the print output
                    print(f"{time_str:<12} | {live_price:<10.2f} | {kalman_est:<10.2f} | {signal:<8} | {action_taken}")
                    
        except Exception as e:
            print(f"Error fetching data: {e}. Retrying...")
            
        # Wait 15 minutes (900 seconds) before performing the next check
        time.sleep(300) 

if __name__ == "__main__":
    # Tracks Bitcoin (BTC-USD) with a 1.4 deviation threshold
    run_live_market_bot("USDEUR=X", deviation_threshold=1.4)
