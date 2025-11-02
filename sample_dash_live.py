# dash_orderbook_with_chart.py
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import asyncio
import json
import pandas as pd
import websockets
from threading import Thread, Lock
import time
from collections import deque
from datetime import datetime
from sqlalchemy import create_engine
import sys
import os

# Add parent directory to path for config imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from configs.config import DB_CONFIG
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    print("Warning: Database config not found. Running in WebSocket-only mode.")

ORDERBOOK_URL = "wss://stream.binance.com:9443/ws/btcusdt@depth20@100ms"
TRADE_URL = "wss://stream.binance.com:9443/ws/btcusdt@trade"

app = dash.Dash(__name__)
app.title = "BTC/USDT Trading Dashboard"

# Thread locks for safe data access
orderbook_lock = Lock()
candle_lock = Lock()
trade_lock = Lock()
db_lock = Lock()

# Store order book data
order_book_data = {
    'bids': pd.DataFrame(columns=['Price', 'Amount']),
    'asks': pd.DataFrame(columns=['Price', 'Amount']),
    'last_price': None,
    'last_update': None,
    'connected': False
}

# Store candle data - keep last 60 minutes of 1-minute candles
candle_data = {
    'candles': deque(maxlen=60),
    'current_candle': {
        'start_time': None,
        'open': None,
        'high': None,
        'low': None,
        'close': None,
        'volume': 0
    }
}

# Store live trade data
trade_data = {
    'price': None,
    'prev_price': None,
    'timestamp': None,
    'volume_24h': 0,
    'trades_count': 0
}

# Store database data
db_data = {
    'whale_transactions': pd.DataFrame(),
    'whale_stats': {},
    'sentiment_data': pd.DataFrame(),
    'last_update': None
}

# Database engine
db_engine = None

def get_db_engine():
    """Create a SQLAlchemy database engine"""
    global db_engine
    if db_engine is None and DB_AVAILABLE:
        try:
            connection_string = (
                f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
                f"@localhost:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
            )
            db_engine = create_engine(connection_string)
            print("Database connection established")
        except Exception as e:
            print(f"Database connection failed: {str(e)}")
    return db_engine

def fetch_whale_transactions():
    """Fetch recent whale transactions from database"""
    engine = get_db_engine()
    if engine is None:
        return pd.DataFrame()
    
    try:
        query = """
        SELECT
            txid,
            detected_at,
            value_btc,
            value_usd,
            btc_price_at_detection,
            status,
            primary_input_address,
            primary_output_address
        FROM whale_transactions
        ORDER BY detected_at DESC
        LIMIT 10
        """
        df = pd.read_sql_query(query, engine)
        return df
    except Exception as e:
        print(f"Error fetching whale transactions: {str(e)}")
        return pd.DataFrame()

def fetch_whale_stats():
    """Fetch whale statistics for last 24 hours"""
    engine = get_db_engine()
    if engine is None:
        return {}
    
    try:
        query = """
        SELECT
            COUNT(*) as transaction_count,
            SUM(value_btc) as total_btc,
            SUM(value_usd) as total_usd,
            AVG(value_btc) as avg_btc,
            MAX(value_btc) as max_btc
        FROM whale_transactions
        WHERE detected_at > NOW() - INTERVAL '24 hours'
        """
        df = pd.read_sql_query(query, engine)
        if not df.empty:
            return df.iloc[0].to_dict()
        return {}
    except Exception as e:
        print(f"Error fetching whale stats: {str(e)}")
        return {}

def fetch_sentiment_summary():
    """Fetch sentiment data"""
    engine = get_db_engine()
    if engine is None:
        return pd.DataFrame()
    
    try:
        query = """
        SELECT 
            bucket,
            article_count,
            avg_sentiment,
            positive_count,
            negative_count,
            neutral_count
        FROM sentiment_1h
        ORDER BY bucket DESC
        LIMIT 24
        """
        df = pd.read_sql_query(query, engine)
        return df.sort_values('bucket')
    except Exception as e:
        print(f"Error fetching sentiment data: {str(e)}")
        return pd.DataFrame()

def update_database_data():
    """Periodically update database data"""
    while True:
        try:
            whale_txs = fetch_whale_transactions()
            whale_stats = fetch_whale_stats()
            sentiment = fetch_sentiment_summary()
            
            with db_lock:
                db_data['whale_transactions'] = whale_txs
                db_data['whale_stats'] = whale_stats
                db_data['sentiment_data'] = sentiment
                db_data['last_update'] = time.time()
            
            time.sleep(30)  # Update every 30 seconds
        except Exception as e:
            print(f"Database update error: {e}")
            time.sleep(30)

async def fetch_order_book():
    """Fetch order book data"""
    while True:
        try:
            async with websockets.connect(ORDERBOOK_URL) as ws:
                print("Connected to order book stream")
                with orderbook_lock:
                    order_book_data['connected'] = True
                
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    
                    if 'bids' in data and 'asks' in data:
                        bids = pd.DataFrame(data['bids'], columns=['Price', 'Amount'], dtype=float)
                        asks = pd.DataFrame(data['asks'], columns=['Price', 'Amount'], dtype=float)
                    elif 'b' in data and 'a' in data:
                        bids = pd.DataFrame(data['b'], columns=['Price', 'Amount'], dtype=float)
                        asks = pd.DataFrame(data['a'], columns=['Price', 'Amount'], dtype=float)
                    else:
                        continue

                    bids = bids.sort_values('Price', ascending=False).head(15)
                    asks = asks.sort_values('Price', ascending=True).head(15)
                    
                    bids['Total'] = bids['Amount'].cumsum()
                    asks['Total'] = asks['Amount'].cumsum()
                    
                    with orderbook_lock:
                        order_book_data['bids'] = bids
                        order_book_data['asks'] = asks
                        
                        if not bids.empty and not asks.empty:
                            order_book_data['last_price'] = (bids.iloc[0]['Price'] + asks.iloc[0]['Price']) / 2
                        
                        order_book_data['last_update'] = time.time()
                    
                    await asyncio.sleep(0.1)
                    
        except Exception as e:
            print(f"Order book error: {e}")
            with orderbook_lock:
                order_book_data['connected'] = False
            await asyncio.sleep(2)

async def fetch_trades():
    """Fetch live trade data and build 1-minute candles"""
    while True:
        try:
            async with websockets.connect(TRADE_URL) as ws:
                print("Connected to trade stream")
                
                while True:
                    msg = await ws.recv()
                    trade_msg = json.loads(msg)
                    
                    price = float(trade_msg.get('p', 0))
                    quantity = float(trade_msg.get('q', 0))
                    trade_time = trade_msg.get('T', 0) / 1000
                    trade_datetime = datetime.fromtimestamp(trade_time)
                    
                    with trade_lock:
                        trade_data['prev_price'] = trade_data['price']
                        trade_data['price'] = price
                        trade_data['timestamp'] = trade_datetime
                        trade_data['trades_count'] += 1
                    
                    candle_time = trade_datetime.replace(second=0, microsecond=0)
                    
                    with candle_lock:
                        current = candle_data['current_candle']
                        
                        if current['start_time'] is None or current['start_time'] != candle_time:
                            if current['start_time'] is not None and current['open'] is not None:
                                candle_data['candles'].append({
                                    'time': current['start_time'],
                                    'open': current['open'],
                                    'high': current['high'],
                                    'low': current['low'],
                                    'close': current['close'],
                                    'volume': current['volume']
                                })
                            
                            current['start_time'] = candle_time
                            current['open'] = price
                            current['high'] = price
                            current['low'] = price
                            current['close'] = price
                            current['volume'] = quantity
                        else:
                            current['high'] = max(current['high'], price)
                            current['low'] = min(current['low'], price)
                            current['close'] = price
                            current['volume'] += quantity
                    
                    await asyncio.sleep(0.1)
                    
        except Exception as e:
            print(f"Trade stream error: {e}")
            await asyncio.sleep(2)

def run_orderbook_websocket():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(fetch_order_book())

def run_trade_websocket():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(fetch_trades())

app.layout = html.Div([
    html.Div([
        html.H1("BTC/USDT Trading Dashboard", style={
            'fontSize': '24px',
            'fontWeight': '600',
            'color': '#e0e3eb',
            'marginBottom': '24px',
            'textAlign': 'center'
        }),
        
        # Live Price Banner
        html.Div([
            html.Div([
                html.Div("Live Price", style={
                    'fontSize': '12px',
                    'color': '#848e9c',
                    'marginBottom': '4px'
                }),
                html.Div(id='live-price-display', style={
                    'fontSize': '32px',
                    'fontWeight': '700',
                    'color': '#0ecb81'
                })
            ], style={'textAlign': 'center'}),
            html.Div(id='price-timestamp', style={
                'fontSize': '11px',
                'color': '#848e9c',
                'textAlign': 'center',
                'marginTop': '8px'
            })
        ], style={
            'backgroundColor': '#1e2329',
            'borderRadius': '8px',
            'padding': '20px',
            'marginBottom': '24px',
            'boxShadow': '0 2px 8px rgba(0,0,0,0.3)'
        }),
        
        # Whale Stats Row
        html.Div(id='whale-stats-row', style={'marginBottom': '24px'}),
        
        html.Div([
            # Left side - Candlestick Chart
            html.Div([
                html.Div("1-Minute Candlestick Chart", style={
                    'fontSize': '16px',
                    'fontWeight': '600',
                    'color': '#e0e3eb',
                    'marginBottom': '12px'
                }),
                dcc.Graph(
                    id='candlestick-chart',
                    config={'displayModeBar': False},
                    style={'height': '500px'}
                )
            ], style={
                'width': '58%',
                'display': 'inline-block',
                'verticalAlign': 'top',
                'paddingRight': '12px'
            }),
            
            # Right side - Order Book
            html.Div([
                html.Div("Order Book", style={
                    'fontSize': '16px',
                    'fontWeight': '600',
                    'color': '#e0e3eb',
                    'marginBottom': '12px'
                }),
                
                html.Div([
                    html.Div([
                        html.Div("Total", style={'width': '30%', 'textAlign': 'right'}),
                        html.Div("Amount", style={'width': '30%', 'textAlign': 'right'}),
                        html.Div("Price", style={'width': '40%', 'textAlign': 'right'})
                    ], style={
                        'display': 'flex',
                        'padding': '10px 12px',
                        'fontSize': '11px',
                        'color': '#848e9c',
                        'borderBottom': '1px solid #2b3139'
                    }),
                    
                    html.Div(id='asks-display'),
                    
                    html.Div(id='spread-display', style={
                        'padding': '12px',
                        'textAlign': 'center',
                        'backgroundColor': '#131722',
                        'borderTop': '1px solid #2b3139',
                        'borderBottom': '1px solid #2b3139'
                    }),
                    
                    html.Div(id='bids-display')
                ], style={
                    'backgroundColor': '#1e2329',
                    'borderRadius': '4px',
                    'marginBottom': '12px'
                }),
                
                html.Div([
                    html.Div(id='last-price-display', style={
                        'fontSize': '20px',
                        'fontWeight': '600',
                        'color': '#0ecb81',
                        'textAlign': 'center',
                        'marginBottom': '4px'
                    }),
                    html.Div("Mid Market Price", style={
                        'fontSize': '11px',
                        'color': '#848e9c',
                        'textAlign': 'center'
                    })
                ], style={
                    'backgroundColor': '#1e2329',
                    'borderRadius': '4px',
                    'padding': '16px'
                })
                
            ], style={
                'width': '40%',
                'display': 'inline-block',
                'verticalAlign': 'top',
                'paddingLeft': '12px'
            })
        ]),
        
        # Whale Transactions Table
        html.Div([
            html.Div("Recent Whale Transactions", style={
                'fontSize': '16px',
                'fontWeight': '600',
                'color': '#e0e3eb',
                'marginBottom': '12px',
                'marginTop': '24px'
            }),
            html.Div(id='whale-transactions-table')
        ]),
        
        # Sentiment Chart
        html.Div([
            html.Div("Sentiment Trend (24h)", style={
                'fontSize': '16px',
                'fontWeight': '600',
                'color': '#e0e3eb',
                'marginBottom': '12px',
                'marginTop': '24px'
            }),
            dcc.Graph(
                id='sentiment-chart',
                config={'displayModeBar': False},
                style={'height': '300px'}
            )
        ])
        
    ], style={
        'maxWidth': '1600px',
        'margin': '0 auto',
        'padding': '24px',
        'fontFamily': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    }),
    
    dcc.Interval(id='interval', interval=500, n_intervals=0)
], style={
    'backgroundColor': '#0b0e11',
    'minHeight': '100vh',
    'padding': '20px'
})

@app.callback(
    [Output('candlestick-chart', 'figure'),
     Output('bids-display', 'children'),
     Output('asks-display', 'children'),
     Output('spread-display', 'children'),
     Output('last-price-display', 'children'),
     Output('live-price-display', 'children'),
     Output('price-timestamp', 'children'),
     Output('whale-stats-row', 'children'),
     Output('whale-transactions-table', 'children'),
     Output('sentiment-chart', 'figure')],
    [Input('interval', 'n_intervals')]
)
def update_dashboard(n):
    # Update candlestick chart
    with candle_lock:
        completed_candles = list(candle_data['candles'])
        current = candle_data['current_candle'].copy()
    
    all_candles = completed_candles.copy()
    if current['start_time'] is not None and current['open'] is not None:
        all_candles.append({
            'time': current['start_time'],
            'open': current['open'],
            'high': current['high'],
            'low': current['low'],
            'close': current['close'],
            'volume': current['volume']
        })
    
    if len(all_candles) > 0:
        times = [c['time'] for c in all_candles]
        opens = [c['open'] for c in all_candles]
        highs = [c['high'] for c in all_candles]
        lows = [c['low'] for c in all_candles]
        closes = [c['close'] for c in all_candles]
        
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=times, open=opens, high=highs, low=lows, close=closes,
            increasing=dict(line=dict(color='#0ecb81'), fillcolor='#0ecb81'),
            decreasing=dict(line=dict(color='#f6465d'), fillcolor='#f6465d'),
            name='BTC/USDT'
        ))
        
        fig.update_layout(
            template='plotly_dark',
            paper_bgcolor='#1e2329',
            plot_bgcolor='#1e2329',
            margin=dict(l=10, r=10, t=10, b=30),
            xaxis=dict(showgrid=True, gridcolor='#2b3139', showline=False, zeroline=False, rangeslider=dict(visible=False)),
            yaxis=dict(showgrid=True, gridcolor='#2b3139', showline=False, zeroline=False, side='right'),
            hovermode='x unified',
            showlegend=False,
            font=dict(color='#848e9c', size=11)
        )
    else:
        fig = go.Figure()
        fig.update_layout(
            template='plotly_dark', paper_bgcolor='#1e2329', plot_bgcolor='#1e2329',
            xaxis=dict(showgrid=False, rangeslider=dict(visible=False)),
            yaxis=dict(showgrid=False),
            annotations=[{'text': 'Waiting for candle data...', 'xref': 'paper', 'yref': 'paper',
                         'x': 0.5, 'y': 0.5, 'showarrow': False, 'font': {'size': 14, 'color': '#848e9c'}}]
        )
    
    # Update order book
    with orderbook_lock:
        bids = order_book_data['bids'].copy()
        asks = order_book_data['asks'].copy()
        last_price = order_book_data['last_price']
    
    with trade_lock:
        live_price = trade_data['price']
        prev_price = trade_data['prev_price']
        timestamp = trade_data['timestamp']
    
    # Get database data
    with db_lock:
        whale_stats = db_data['whale_stats'].copy()
        whale_txs = db_data['whale_transactions'].copy()
        sentiment_df = db_data['sentiment_data'].copy()
    
    if bids.empty or asks.empty:
        return fig, "Loading...", "Loading...", "...", "...", "Loading...", "", html.Div(), html.Div(), go.Figure()
    
    # Create bids display
    bids_rows = []
    for i in range(min(10, len(bids))):
        row = bids.iloc[i]
        bids_rows.append(html.Div([
            html.Div(f"{row['Total']:.5f}", style={'width': '30%', 'textAlign': 'right', 'color': '#b7bdc6'}),
            html.Div(f"{row['Amount']:.5f}", style={'width': '30%', 'textAlign': 'right', 'color': '#e0e3eb'}),
            html.Div(f"{row['Price']:.2f}", style={'width': '40%', 'textAlign': 'right', 'color': '#0ecb81', 'fontWeight': '500'})
        ], style={'display': 'flex', 'padding': '6px 12px', 'fontSize': '12px', 'fontFamily': 'monospace',
                 'backgroundColor': '#1e2329' if i % 2 == 0 else '#181a20'}))
    
    # Create asks display
    asks_rows = []
    asks_reversed = asks.iloc[::-1].head(10)
    for i in range(len(asks_reversed)):
        row = asks_reversed.iloc[i]
        asks_rows.append(html.Div([
            html.Div(f"{row['Total']:.5f}", style={'width': '30%', 'textAlign': 'right', 'color': '#b7bdc6'}),
            html.Div(f"{row['Amount']:.5f}", style={'width': '30%', 'textAlign': 'right', 'color': '#e0e3eb'}),
            html.Div(f"{row['Price']:.2f}", style={'width': '40%', 'textAlign': 'right', 'color': '#f6465d', 'fontWeight': '500'})
        ], style={'display': 'flex', 'padding': '6px 12px', 'fontSize': '12px', 'fontFamily': 'monospace',
                 'backgroundColor': '#1e2329' if i % 2 == 0 else '#181a20'}))
    
    # Calculate spread
    best_bid = bids.iloc[0]['Price']
    best_ask = asks.iloc[0]['Price']
    spread = best_ask - best_bid
    spread_pct = (spread / best_bid) * 100
    spread_display = html.Div([
        html.Span(f"{spread:.2f}", style={'color': '#e0e3eb', 'fontWeight': '600', 'fontSize': '14px'}),
        html.Span(f" ({spread_pct:.3f}%)", style={'color': '#848e9c', 'fontSize': '12px', 'marginLeft': '6px'})
    ])
    
    last_price_str = f"{last_price:.2f}" if last_price else "..."
    
    # Live price display
    if live_price:
        price_color = '#0ecb81'
        if prev_price and live_price < prev_price:
            price_color = '#f6465d'
        elif prev_price and live_price == prev_price:
            price_color = '#e0e3eb'
        live_price_str = f"${live_price:,.2f}"
        timestamp_str = timestamp.strftime("%H:%M:%S") if timestamp else ""
    else:
        price_color = '#848e9c'
        live_price_str = "Waiting for trades..."
        timestamp_str = ""
    
    live_price_elem = html.Span(live_price_str, style={'color': price_color})
    
    # Whale stats cards
    whale_stats_cards = html.Div("Database connection unavailable", style={'color': '#848e9c', 'textAlign': 'center'})
    if whale_stats:
        whale_stats_cards = html.Div([
            html.Div([
                html.Div(f"{whale_stats.get('transaction_count', 0):.0f}", 
                        style={'fontSize': '24px', 'fontWeight': '600', 'color': '#e0e3eb'}),
                html.Div("24h Whale Txs", style={'fontSize': '11px', 'color': '#848e9c', 'marginTop': '4px'})
            ], style={'backgroundColor': '#1e2329', 'padding': '16px', 'borderRadius': '4px', 'textAlign': 'center', 'width': '18%', 'display': 'inline-block', 'marginRight': '2%'}),
            
            html.Div([
                html.Div(f"{whale_stats.get('total_btc', 0):,.2f} BTC", 
                        style={'fontSize': '24px', 'fontWeight': '600', 'color': '#f7931a'}),
                html.Div("Total Volume", style={'fontSize': '11px', 'color': '#848e9c', 'marginTop': '4px'})
            ], style={'backgroundColor': '#1e2329', 'padding': '16px', 'borderRadius': '4px', 'textAlign': 'center', 'width': '18%', 'display': 'inline-block', 'marginRight': '2%'}),
            
            html.Div([
                html.Div(f"${whale_stats.get('total_usd', 0)/1e6:,.1f}M", 
                        style={'fontSize': '24px', 'fontWeight': '600', 'color': '#0ecb81'}),
                html.Div("Total USD Value", style={'fontSize': '11px', 'color': '#848e9c', 'marginTop': '4px'})
            ], style={'backgroundColor': '#1e2329', 'padding': '16px', 'borderRadius': '4px', 'textAlign': 'center', 'width': '18%', 'display': 'inline-block', 'marginRight': '2%'}),
            
            html.Div([
                html.Div(f"{whale_stats.get('avg_btc', 0):,.2f} BTC", 
                        style={'fontSize': '24px', 'fontWeight': '600', 'color': '#e0e3eb'}),
                html.Div("Avg Transaction", style={'fontSize': '11px', 'color': '#848e9c', 'marginTop': '4px'})
            ], style={'backgroundColor': '#1e2329', 'padding': '16px', 'borderRadius': '4px', 'textAlign': 'center', 'width': '18%', 'display': 'inline-block', 'marginRight': '2%'}),
            
            html.Div([
                html.Div(f"{whale_stats.get('max_btc', 0):,.2f} BTC", 
                        style={'fontSize': '24px', 'fontWeight': '600', 'color': '#f6465d'}),
                html.Div("Largest Tx", style={'fontSize': '11px', 'color': '#848e9c', 'marginTop': '4px'})
            ], style={'backgroundColor': '#1e2329', 'padding': '16px', 'borderRadius': '4px', 'textAlign': 'center', 'width': '18%', 'display': 'inline-block'})
        ])
    
    # Whale transactions table
    whale_table = html.Div("No whale transaction data available", style={'color': '#848e9c', 'padding': '20px', 'textAlign': 'center'})
    if not whale_txs.empty:
        whale_rows = []
        for i in range(min(10, len(whale_txs))):
            tx = whale_txs.iloc[i]
            whale_rows.append(html.Div([
                html.Div(tx['detected_at'].strftime("%H:%M:%S") if pd.notna(tx.get('detected_at')) else '-', 
                        style={'width': '12%', 'color': '#848e9c', 'fontSize': '11px'}),
                html.Div(f"{tx['value_btc']:.2f} BTC", 
                        style={'width': '18%', 'color': '#f7931a', 'fontWeight': '500', 'fontSize': '12px'}),
                html.Div(f"${tx['value_usd']/1e6:.2f}M", 
                        style={'width': '15%', 'color': '#0ecb81', 'fontWeight': '500', 'fontSize': '12px'}),
                html.Div(tx['status'] if pd.notna(tx.get('status')) else 'pending', 
                        style={'width': '12%', 'color': '#0ecb81' if tx.get('status') == 'confirmed' else '#ffa500', 
                               'fontSize': '11px', 'textTransform': 'capitalize'}),
                html.Div(f"{str(tx['primary_input_address'])[:8]}..." if pd.notna(tx.get('primary_input_address')) else '-', 
                        style={'width': '20%', 'color': '#b7bdc6', 'fontSize': '11px', 'fontFamily': 'monospace'}),
                html.Div(f"{str(tx['primary_output_address'])[:8]}..." if pd.notna(tx.get('primary_output_address')) else '-', 
                        style={'width': '20%', 'color': '#b7bdc6', 'fontSize': '11px', 'fontFamily': 'monospace'})
            ], style={'display': 'flex', 'padding': '12px', 'borderBottom': '1px solid #2b3139',
                     'backgroundColor': '#1e2329' if i % 2 == 0 else '#181a20'}))
        
        whale_table = html.Div([
            html.Div([
                html.Div("Time", style={'width': '12%', 'fontSize': '11px', 'color': '#848e9c', 'fontWeight': '600'}),
                html.Div("Amount (BTC)", style={'width': '18%', 'fontSize': '11px', 'color': '#848e9c', 'fontWeight': '600'}),
                html.Div("USD Value", style={'width': '15%', 'fontSize': '11px', 'color': '#848e9c', 'fontWeight': '600'}),
                html.Div("Status", style={'width': '12%', 'fontSize': '11px', 'color': '#848e9c', 'fontWeight': '600'}),
                html.Div("From", style={'width': '20%', 'fontSize': '11px', 'color': '#848e9c', 'fontWeight': '600'}),
                html.Div("To", style={'width': '20%', 'fontSize': '11px', 'color': '#848e9c', 'fontWeight': '600'})
            ], style={'display': 'flex', 'padding': '12px', 'backgroundColor': '#131722', 'borderBottom': '2px solid #2b3139'}),
            html.Div(whale_rows)
        ], style={'backgroundColor': '#1e2329', 'borderRadius': '4px', 'overflow': 'hidden'})
    
    # Sentiment chart
    sentiment_fig = go.Figure()
    if not sentiment_df.empty:
        sentiment_fig.add_trace(go.Scatter(
            x=sentiment_df['bucket'],
            y=sentiment_df['avg_sentiment'],
            mode='lines+markers',
            name='Avg Sentiment',
            line=dict(color='#0ecb81', width=2),
            marker=dict(size=6),
            fill='tozeroy',
            fillcolor='rgba(14, 203, 129, 0.1)'
        ))
        
        sentiment_fig.update_layout(
            template='plotly_dark',
            paper_bgcolor='#1e2329',
            plot_bgcolor='#1e2329',
            margin=dict(l=10, r=10, t=10, b=30),
            xaxis=dict(showgrid=True, gridcolor='#2b3139', showline=False),
            yaxis=dict(showgrid=True, gridcolor='#2b3139', showline=False, title='Sentiment Score'),
            hovermode='x unified',
            showlegend=False,
            font=dict(color='#848e9c', size=11)
        )
    else:
        sentiment_fig.update_layout(
            template='plotly_dark',
            paper_bgcolor='#1e2329',
            plot_bgcolor='#1e2329',
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=False),
            annotations=[{'text': 'No sentiment data available', 'xref': 'paper', 'yref': 'paper',
                         'x': 0.5, 'y': 0.5, 'showarrow': False, 'font': {'size': 14, 'color': '#848e9c'}}]
        )
    
    return fig, html.Div(bids_rows), html.Div(asks_rows), spread_display, last_price_str, live_price_elem, timestamp_str, whale_stats_cards, whale_table, sentiment_fig

if __name__ == '__main__':
    print("Starting BTC/USDT Trading Dashboard...")
    print("Waiting for WebSocket connections...")
    
    # Start WebSocket threads
    Thread(target=run_orderbook_websocket, daemon=True).start()
    time.sleep(0.5)
    Thread(target=run_trade_websocket, daemon=True).start()
    time.sleep(0.5)
    
    # Start database update thread if database is available
    if DB_AVAILABLE:
        get_db_engine()  # Initialize database connection
        Thread(target=update_database_data, daemon=True).start()
        print("Database connection thread started")
    else:
        print("Running without database connection")
    
    time.sleep(1)
    
    print("Starting Dash server on http://127.0.0.1:8050")
    app.run(debug=True, host='127.0.0.1', port=8050)