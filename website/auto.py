from flask import Flask, jsonify, request
import ccxt
import pandas as pd
import numpy as np
from termcolor import colored
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time  # For delays
from threading import Thread, Lock  # To prevent race conditions

app = Flask(__name__, static_folder='.', static_url_path='')

@app.route('/')
def index():
    return app.send_static_file('index.html')

# Initialize kraken Exchange
exchange = ccxt.kraken()

# --- Selenium Configuration ---
EXNESS_WEB_TERMINAL_URL = "https://my.exness.com/accounts/sign-in"  # REPLACE
USERNAME = "mohdhassanidrees@gmail.com"  # REPLACE
PASSWORD = "Qasim@273322"  # REPLACE

# --- Global Variables ---
driver = None  # Selenium WebDriver instance
trading_enabled = True  # Flag to enable/disable trading
trade_lock = Lock()  # Thread lock for safe trading operations
last_signal = None #Store last signal to avoid double trading on same setup

# --- Helper Functions for Selenium Interaction (REPLACE with actual element IDs/CSS Selectors) ---
def login(driver, username, password):
    try:
        username_field = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "username-field-id")))  # REPLACE
        password_field = driver.find_element(By.ID, "password-field-id")  # REPLACE
        username_field.send_keys(username)
        password_field.send_keys(password)
        login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")  # REPLACE
        login_button.click()
        WebDriverWait(driver, 20).until(EC.url_contains("trading-area"))  # REPLACE
        print(colored("Logged in to Exness.", "green"))
        return True
    except Exception as e:
        print(colored(f"Login failed: {e}", "red"))
        return False

def place_order(driver, symbol, trade_type, volume, stop_loss, take_profit):
    try:
        print(colored(f"Attempting to place order: {trade_type} {symbol} Volume: {volume} SL: {stop_loss} TP: {take_profit}", "yellow"))
        symbol_field = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "symbol-field")))  # REPLACE
        symbol_field.clear()  # Clear previous value
        symbol_field.send_keys(symbol)

        if trade_type == "Buy":
            buy_button = driver.find_element(By.ID, "buy-button")  # REPLACE
            buy_button.click()
        else:
            sell_button = driver.find_element(By.ID, "sell-button")  # REPLACE
            sell_button.click()

        volume_field = driver.find_element(By.ID, "volume-field")  # REPLACE
        volume_field.clear()
        volume_field.send_keys(str(volume))

        stop_loss_field = driver.find_element(By.ID, "stop-loss-field")  # REPLACE
        stop_loss_field.clear()
        stop_loss_field.send_keys(str(stop_loss))

        take_profit_field = driver.find_element(By.ID, "take-profit-field")  # REPLACE
        take_profit_field.clear()
        take_profit_field.send_keys(str(take_profit))

        place_order_button = driver.find_element(By.ID, "place-order-button")  # REPLACE
        place_order_button.click()
        print(colored(f"Order placed successfully: {trade_type} {symbol} Volume: {volume} SL: {stop_loss} TP: {take_profit}", "green"))
        return True
    except Exception as e:
        print(colored(f"Error placing order: {e}", "red"))
        return False

# --- Data Fetching and Analysis Functions (From Previous Code) ---
def fetch_data(pair, timeframe, limit=100):
    try:
        url = f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval={timeframe}"
        print(colored(f"Fetching data from: {url}", "blue"))  # Log the request URL
        ohlcv = exchange.fetch_ohlcv(pair, timeframe, limit=limit)
        if not ohlcv:
            print(colored("No data returned from binance API.", "red"))

        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        print(colored(f"Error fetching data from binance API: {e}", "red"))  # Log the error message
        return None

def detect_bos(df):
    bos = None
    for i in range(1, len(df)):
        if df['high'][i] > df['high'][i-1]:  # Uptrend BOS
            bos = "BOS Up"
        elif df['low'][i] < df['low'][i-1]:  # Downtrend BOS
            bos = "BOS Down"
    return bos

def detect_choch(df):
    choch = None
    if df['close'].iloc[-1] > df['open'].iloc[-2] and df['close'].iloc[-2] < df['open'].iloc[-3]:  # Uptrend CHoCH
        choch = "CHoCH Up"
    elif df['close'].iloc[-1] < df['open'].iloc[-2] and df['close'].iloc[-2] > df['open'].iloc[-3]:  # Downtrend CHoCH
        choch = "CHoCH Down"
    return choch

def detect_fvg(df):
    fvg = None
    for i in range(2, len(df)):
        if df['low'][i] > df['high'][i-2]:  # Upward FVG
            fvg = "FVG Up"
        elif df['high'][i] < df['low'][i-2]:  # Downward FVG
            fvg = "FVG Down"
    return fvg

def detect_displacement(df):
    displacement = None
    if df['close'].iloc[-1] > df['high'].iloc[-2]:
        displacement = "Displacement Up"
    elif df['close'].iloc[-1] < df['low'].iloc[-2]:
        displacement = "Displacement Down"
    return displacement

def detect_market_structure_shift(df):
    mss = None
    if df['high'].iloc[-1] > df['high'].iloc[-2] and df['low'].iloc[-1] > df['low'].iloc[-2]:
        mss = "Market Structure Shift Up"
    elif df['low'].iloc[-1] < df['low'].iloc[-2] and df['high'].iloc[-1] < df['high'].iloc[-2]:
        mss = "Market Structure Shift Down"
    return mss

def detect_liquidity(df):
    liquidity = None
    if df['low'].iloc[-1] < min(df['low'].iloc[-5:-1]):
        liquidity = "Liquidity Down"
    elif df['high'].iloc[-1] > max(df['high'].iloc[-5:-1]):
        liquidity = "Liquidity Up"
    return liquidity

def detect_liquidity_sweep(df):
    if df['low'].iloc[-1] < min(df['low'].iloc[-3:-1]):  
        return "Liquidity Sweep Down"
    elif df['high'].iloc[-1] > max(df['high'].iloc[-3:-1]):  
        return "Liquidity Sweep Up"
    return None

def detect_flip_zone(df):
    if df['close'].iloc[-1] > df['open'].iloc[-1] and df['close'].iloc[-2] < df['open'].iloc[-2]:
        return "Bullish Flip Zone"
    elif df['close'].iloc[-1] < df['open'].iloc[-1] and df['close'].iloc[-2] > df['open'].iloc[-2]:
        return "Bearish Flip Zone"
    return None

def detect_wyckoff(df):
    if df['low'].iloc[-1] < min(df['low'].iloc[-5:-1]):  
        return "Potential Wyckoff Accumulation"
    elif df['high'].iloc[-1] > max(df['high'].iloc[-5:-1]):  
        return "Potential Wyckoff Distribution"
    return None

def detect_order_flow(df):
    order_flow = None
    if df['close'].iloc[-1] > df['open'].iloc[-1]:
        order_flow = "Order Flow Bullish"
    elif df['close'].iloc[-1] < df['open'].iloc[-1]:
        order_flow = "Order Flow Bearish"
    return order_flow

def detect_order_blocks(df):
    if df['close'].iloc[-2] < df['open'].iloc[-2] and df['close'].iloc[-1] > df['open'].iloc[-1]:  
        return "Bullish Order Block"
    elif df['close'].iloc[-2] > df['open'].iloc[-2] and df['close'].iloc[-1] < df['open'].iloc[-1]:  
        return "Bearish Order Block"
    return None

def detect_breaker_blocks(df):
    if df['high'].iloc[-1] > max(df['high'].iloc[-5:-1]) and df['low'].iloc[-1] > min(df['low'].iloc[-5:-1]):  
        return "Breaker Block Up"
    elif df['low'].iloc[-1] < min(df['low'].iloc[-5:-1]) and df['high'].iloc[-1] < max(df['high'].iloc[-5:-1]):  
        return "Breaker Block Down"
    return None

def detect_redefined_order_block(df):
    if df['close'].iloc[-1] > df['open'].iloc[-1] and df['close'].iloc[-2] < df['open'].iloc[-2]:
        return "Redefined Order Block Bullish"
    elif df['close'].iloc[-1] < df['open'].iloc[-1] and df['close'].iloc[-2] > df['open'].iloc[-2]:
        return "Redefined Order Block Bearish"
    return None

def detect_rejection_block(df):
    if df['high'].iloc[-1] > df['high'].iloc[-2] and df['close'].iloc[-1] < df['open'].iloc[-1]:
        return "Rejection Block Bearish"
    elif df['low'].iloc[-1] < df['low'].iloc[-2] and df['close'].iloc[-1] > df['open'].iloc[-1]:
        return "Rejection Block Bullish"
    return None

def detect_mitigation(df):
    if df['low'].iloc[-1] < min(df['low'].iloc[-5:-1]) and df['close'].iloc[-1] > df['open'].iloc[-1]:
        return "Mitigation Bullish"
    elif df['high'].iloc[-1] > max(df['high'].iloc[-5:-1]) and df['close'].iloc[-1] < df['open'].iloc[-1]:
        return "Mitigation Bearish"
    return None

def detect_inducement(df):
    inducement = None
    if df['high'].iloc[-1] > df['high'].iloc[-2] and df['close'].iloc[-1] < df['open'].iloc[-1]:  
        inducement = "Inducement Trap Bearish"
    elif df['low'].iloc[-1] < df['low'].iloc[-2] and df['close'].iloc[-1] > df['open'].iloc[-1]:  
        inducement = "Inducement Trap Bullish"
    return inducement

def detect_ifc(df):
    body_size = abs(df['close'].iloc[-1] - df['open'].iloc[-1])
    wick_size = abs(df['high'].iloc[-1] - df['low'].iloc[-1])
    if body_size > wick_size * 1.5:
        return "Bullish IFC" if df['close'].iloc[-1] > df['open'].iloc[-1] else "Bearish IFC"
    return None

def detect_discount_premium_zones(df):
    midpoint = (df['high'].max() + df['low'].min()) / 2
    if df['close'].iloc[-1] < midpoint:
        return "Discount Zone (Bullish)"
    elif df['close'].iloc[-1] > midpoint:
        return "Premium Zone (Bearish)"
    return None

def calculate_tp_sl(entry_price, risk_reward_ratio, risk_amount):
    take_profit = entry_price + (risk_reward_ratio * risk_amount)
    stop_loss = entry_price - risk_amount
    return take_profit, stop_loss

def generate_smc_signal(df):
    entry_price = df['close'].iloc[-1]  # Using the last close price as entry
    risk_reward_ratio = 2.0  # Example risk-reward ratio
    risk_amount = 50.0  # Example risk amount

    take_profit, stop_loss = calculate_tp_sl(entry_price, risk_reward_ratio, risk_amount)

    signals = {
        "Break of Structure": detect_bos(df),
        "Change of Character": detect_choch(df),
        "Fair Value Gaps": detect_fvg(df),
        "Displacement": detect_displacement(df),
        "Market Structure Shift": detect_market_structure_shift(df),
        "Liquidity": detect_liquidity(df),
        "Liquidity Sweep": detect_liquidity_sweep(df),
        "Flip Zone": detect_flip_zone(df),
        "Wyckoff Theory": detect_wyckoff(df),
        "Order Flow": detect_order_flow(df),
        "Order Block": detect_order_blocks(df),
        "Breaker Block": detect_breaker_blocks(df),
        "Redefined Order Block": detect_redefined_order_block(df),
        "Rejection Block": detect_rejection_block(df),
        "Mitigation": detect_mitigation(df),
        "Inducement": detect_inducement(df),
        "Institutional Funding Candle": detect_ifc(df),
        "Zone": detect_discount_premium_zones(df),
    }

    bullish_count = sum(1 for key in signals if signals[key] in ["BOS Up", "CHoCH Up", "FVG Up", "Displacement Up", "Market Structure Shift Up", "Liquidity Up", "Liquidity Sweep Up", "Flip Zone", "Wyckoff Theory", "Order Flow Bullish", "Order Block", "Breaker Block Up", "Redefined Order Block Bullish", "Rejection Block Bullish", "Mitigation Bullish", "Inducement Trap Bullish", "Institutional Funding Candle", "Discount Zone (Bullish)"])
    bearish_count = sum(1 for key in signals if signals[key] in ["BOS Down", "CHoCH Down", "FVG Down", "Displacement Down", "Market Structure Shift Down", "Liquidity Down", "Liquidity Sweep Down", "Bearish Flip Zone", "Potential Wyckoff Distribution", "Order Flow Bearish", "Bearish Order Block", "Breaker Block Down", "Redefined Order Block Bearish", "Rejection Block Bearish", "Mitigation Bearish", "Inducement Trap Bearish", "Institutional Funding Candle", "Premium Zone (Bearish)"])

    if bullish_count > bearish_count:
        return {"signal": "Strong Buy Signal", "take_profit": take_profit, "stop_loss": stop_loss}
    elif bearish_count > bullish_count:
        return {"signal": "Strong Sell Signal", "take_profit": take_profit, "stop_loss": stop_loss}
    return {"signal": "Neutral/Wait Signal", "take_profit": take_profit, "stop_loss": stop_loss}

def calculate_signal_strength(signals):
    """
    Assigns weights to detected signals and calculates an overall confidence score.
    """

    weights = {
        "Break of Structure": 1.5,
        "Change of Character": 1.5,
        "Fair Value Gaps": 1.2,
        "Displacement": 1.3,
        "Market Structure Shift": 1.5,
        "Liquidity": 1.1,
        "Liquidity Sweep": 1.4,
        "Flip Zone": 1.3,
        "Wyckoff Theory": 1.6,
        "Order Flow": 1.3,
        "Order Block": 1.4,
        "Breaker Block": 1.2,
        "Redefined Order Block": 1.3,
        "Rejection Block": 1.2,
        "Mitigation": 1.3,
        "Inducement": 1.1,
        "Institutional Funding Candle": 1.5,
        "Zone": 1.0,
    }
    
    total_weight = sum(weights.values())
    detected_weight = sum(weights[signal] for signal in signals if signals[signal])
    
    confidence_score = (detected_weight / total_weight) * 100
    return confidence_score

def determine_trade_signal(signals):
    """
    Determines whether to buy, sell, or stay neutral based on signal strength.
    """

    confidence_score = calculate_signal_strength(signals)
    
    if confidence_score >= 75:
        return "Strong Buy" if signals.get("Break of Structure") else "Strong Sell"
    elif confidence_score >= 50:
        return "Buy" if signals.get("Change of Character") else "Sell"
    elif confidence_score >= 30:
        return "Neutral - Wait for confirmation"
    else:
        return "No Trade - Weak Signals"

# Example usage:
signals = {
    "Break of Structure": True,
    "Change of Character": False,
    "Fair Value Gaps": True,
    "Displacement": True,
    "Market Structure Shift": False,
    "Liquidity": True,
    "Liquidity Sweep": True,
    "Flip Zone": False,
    "Wyckoff Theory": False,
    "Order Flow": True,
    "Order Block": True,
    "Breaker Block": False,
    "Redefined Order Block": False,
    "Rejection Block": False,
    "Mitigation": True,
    "Inducement": False,
    "Institutional Funding Candle": False,
    "Zone": False,
}

decision = determine_trade_signal(signals)
print(f"Trade Decision: {decision}")

def risk_management():

    return "Risk Management Strategy Placeholder"

# --- Trading Function (Executed in a Separate Thread) ---
def trading_loop():
    global driver, trading_enabled, last_signal
    symbol = 'BTC/USD'  # Example, make this configurable
    timeframe = '1m'     # Example, make this configurable
    volume = 0.01       # Example, make this configurable

    while trading_enabled:
        try:
            df = fetch_data(symbol, timeframe)
            if df is not None:
                smc_signal = generate_smc_signal(df)

                if smc_signal["signal"] != "Neutral/Wait Signal":
                    # Check the trade is with different signal
                    if last_signal is None or last_signal["signal"] != smc_signal["signal"]:
                        trade_type = "Buy" if smc_signal["signal"] == "Strong Buy Signal" else "Sell"
                        take_profit = smc_signal["take_profit"]
                        stop_loss = smc_signal["stop_loss"]

                        with trade_lock:  # Acquire lock before trading
                            if trading_enabled and driver is not None:
                                success = place_order(driver, symbol, trade_type, volume, stop_loss, take_profit)
                                if success:
                                    last_signal = smc_signal
                                else:
                                    print(colored("Failed to place order.  Check Selenium interaction.", "red"))
                    else:
                        print(colored("Same trade signal found. Skipping...", "yellow"))
                else:
                    print(colored("Neutral signal. No trade.", "yellow"))
            else:
                print(colored("Failed to fetch data.  Retrying...", "red"))

        except Exception as e:
            print(colored(f"Error in trading loop: {e}", "red"))

        time.sleep(60)  # Check every 60 seconds (adjust as needed)

# --- Flask Routes ---
@app.route('/analyze', methods=['GET'])
def analyze():
    symbol = request.args.get('symbol', 'BTC/USD')
    timeframe = request.args.get('timeframe', '1m')
    if not symbol:
        return jsonify({"error": "Symbol parameter is required."}), 400

    df = fetch_data(symbol, timeframe)
    if df is None:
        return jsonify({"error": "Failed to fetch data"}), 500

    signals = generate_smc_signal(df)
    return jsonify(signals)

@app.route('/start_trading', methods=['POST'])
def start_trading():
    global trading_enabled, driver, trading_thread

    if driver is None:
        try:
            driver = webdriver.Chrome()  # Or Firefox, Edge, etc.
            driver.get(EXNESS_WEB_TERMINAL_URL)
            if login(driver, USERNAME, PASSWORD):
                trading_enabled = True
                trading_thread = Thread(target=trading_loop)
                trading_thread.daemon = True  # Allow the main thread to exit
                trading_thread.start()
                return jsonify({"message": "Trading started."}), 200
            else:
                driver.quit()
                driver = None
                return jsonify({"error": "Exness login failed."}), 400
        except Exception as e:
            if driver:
                driver.quit()
            driver = None
            trading_enabled = False
            return jsonify({"error": f"Failed to initialize Selenium: {e}"}), 500
    else:
        return jsonify({"message": "Trading already running."}), 200


@app.route('/stop_trading', methods=['POST'])
def stop_trading():
    global trading_enabled, driver

    trading_enabled = False
    if driver:
        driver.quit()
        driver = None
    print(colored("Trading stopped.", "yellow"))
    return jsonify({"message": "Trading stopped."}), 200

# --- Main ---
if __name__ == '__main__':
    app.run(debug=True)