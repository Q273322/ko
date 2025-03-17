from flask import Flask, jsonify, request
import ccxt
import pandas as pd
import mysql.connector
import numpy as np
from termcolor import colored
import os 
app = Flask(__name__, static_folder='.', static_url_path='')
def get_db_connection():
    connection = mysql.connector.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        user=os.environ.get('DB_USER', 'root'),
        password=os.environ.get('DB_PASSWORD', 'Qasim@273322'),  # Replace with a default or handle missing
        database=os.environ.get('DB_NAME', 'bindrs')
    )

    return connection

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    email = data['email']
    password = data['password']
    
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("INSERT INTO users (email, password) VALUES (%s, %s)", (email, password))
    user_id = cursor.lastrowid  # Get the unique ID of the newly created user
    connection.commit()
    cursor.close()
    connection.close()
    
    return jsonify({'message': 'User registered successfully', 'user_id': user_id}), 201


@app.route('/save_earnings', methods=['POST'])
def save_earnings():
    data = request.json
    user_id = data['user_id']  # Assuming you have a way to get the user ID
    earnings = data['earnings']
    
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT total_balance FROM users WHERE id = %s", (user_id,))
    total_balance = cursor.fetchone()[0]  # Get the total balance for the user
    cursor.execute("INSERT INTO earnings (user_id, earnings, total_balance) VALUES (%s, %s, %s)", (user_id, earnings, total_balance))

    connection.commit()
    cursor.close()
    connection.close()
    
    return jsonify({'message': 'Earnings saved successfully'}), 201

@app.route('/withdraw', methods=['POST'])
def withdraw():
    data = request.json
    user_id = data['user_id']  # Assuming you have a way to get the user ID
    earnings = data['earnings']
    
    connection = get_db_connection()
    cursor = connection.cursor()
    
    if earnings > 0:
        # Update total balance in the database
        cursor.execute("UPDATE users SET total_balance = total_balance + %s WHERE id = %s", (earnings, user_id))
        connection.commit()
        
        # Ensure to retrieve the updated total balance after withdrawal
        cursor.execute("SELECT total_balance FROM users WHERE id = %s", (user_id,))
        updated_balance = cursor.fetchone()[0]  # Get the updated total balance for the user
        
        return jsonify({'message': 'Withdrawal successful!', 'total_balance': updated_balance}), 200
    else:
        return jsonify({'message': 'No earnings to withdraw!'}), 400



@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'message': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400
    file.save(f'uploads/{file.filename}')  # Save the file to the uploads directory
    return jsonify({'message': 'File uploaded successfully'}), 201

def login():
    data = request.json
    email = data['email']
    password = data['password']
    
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, password))
    user = cursor.fetchone()
    cursor.close()
    connection.close()
    
    if user:
        return jsonify({'message': 'Login successful'}), 200
    else:
        return jsonify({'message': 'Invalid credentials'}), 401

@app.route('/')
def index():
    return app.send_static_file('index.html')

# Initialize binance Exchange
exchange = ccxt.kraken()

@app.route('/analyze', methods=['GET'])
def analyze():
    symbol = request.args.get('symbol', 'BTC/USD')
    timeframe = request.args.get('timeframe', '1m')  # Default to 1 minute if not provided
    if not symbol:
        return jsonify({"error": "Symbol parameter is required."}), 400
    
    df = fetch_data(symbol, timeframe)

    if df is None:
        return jsonify({"error": "Failed to fetch data"}), 500
    
    signals = generate_smc_signal(df)  # Generate trading signals based on the fetched data

    return jsonify(signals)  # Return the generated signals as a JSON response


# Fetch valid USD pairs
def get_valid_usd_pairs():
    try:
        markets = exchange.load_markets()
        usd_pairs = [symbol for symbol in markets.keys() if symbol.endswith("/USD")]
        return usd_pairs
    except Exception as e:
        print(colored(f"Error fetching market data: {e}", "red"))
        return []

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

if __name__ == '__main__':
    app.run(debug=False)  # Disable debug mode for production
