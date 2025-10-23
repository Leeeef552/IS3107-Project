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

ORDERBOOK_URL = "wss://stream.binance.com:9443/ws/btcusdt@depth20@100ms"
TRADE_URL = "wss://stream.binance.com:9443/ws/btcusdt@trade"

app = dash.Dash(__name__)
app.title = "BTC/USDT Trading Dashboard"

# Thread locks for safe data access
orderbook_lock = Lock()
candle_lock = Lock()

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
    'candles': deque(maxlen=60),  # Store completed candles
    'current_candle': {
        'start_time': None,
        'open': None,
        'high': None,
        'low': None,
        'close': None,
        'volume': 0
    }
}

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
                    trade_data = json.loads(msg)
                    
                    price = float(trade_data.get('p', 0))
                    quantity = float(trade_data.get('q', 0))
                    trade_time = trade_data.get('T', 0) / 1000
                    trade_datetime = datetime.fromtimestamp(trade_time)
                    
                    # Round down to the start of the current minute
                    candle_time = trade_datetime.replace(second=0, microsecond=0)
                    
                    with candle_lock:
                        current = candle_data['current_candle']
                        
                        # Check if we need to start a new candle
                        if current['start_time'] is None or current['start_time'] != candle_time:
                            # Save the previous candle if it exists
                            if current['start_time'] is not None and current['open'] is not None:
                                candle_data['candles'].append({
                                    'time': current['start_time'],
                                    'open': current['open'],
                                    'high': current['high'],
                                    'low': current['low'],
                                    'close': current['close'],
                                    'volume': current['volume']
                                })
                                if len(candle_data['candles']) <= 3:
                                    print(f"Candle completed: O:{current['open']:.2f} H:{current['high']:.2f} L:{current['low']:.2f} C:{current['close']:.2f}")
                            
                            # Start new candle
                            current['start_time'] = candle_time
                            current['open'] = price
                            current['high'] = price
                            current['low'] = price
                            current['close'] = price
                            current['volume'] = quantity
                        else:
                            # Update current candle
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
                    # Headers
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
                    
                    # Asks (sells)
                    html.Div(id='asks-display'),
                    
                    # Spread indicator
                    html.Div(id='spread-display', style={
                        'padding': '12px',
                        'textAlign': 'center',
                        'backgroundColor': '#131722',
                        'borderTop': '1px solid #2b3139',
                        'borderBottom': '1px solid #2b3139'
                    }),
                    
                    # Bids (buys)
                    html.Div(id='bids-display')
                ], style={
                    'backgroundColor': '#1e2329',
                    'borderRadius': '4px',
                    'marginBottom': '12px'
                }),
                
                # Market stats
                html.Div([
                    html.Div(id='last-price-display', style={
                        'fontSize': '20px',
                        'fontWeight': '600',
                        'color': '#0ecb81',
                        'textAlign': 'center',
                        'marginBottom': '4px'
                    }),
                    html.Div("Last Market Price", style={
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
     Output('last-price-display', 'children')],
    [Input('interval', 'n_intervals')]
)
def update_dashboard(n):
    # Update candlestick chart with thread safety
    with candle_lock:
        completed_candles = list(candle_data['candles'])
        current = candle_data['current_candle'].copy()
    
    # Combine completed candles with current candle
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
        
        # Add candlestick chart
        fig.add_trace(go.Candlestick(
            x=times,
            open=opens,
            high=highs,
            low=lows,
            close=closes,
            increasing=dict(line=dict(color='#0ecb81'), fillcolor='#0ecb81'),
            decreasing=dict(line=dict(color='#f6465d'), fillcolor='#f6465d'),
            name='BTC/USDT'
        ))
        
        fig.update_layout(
            template='plotly_dark',
            paper_bgcolor='#1e2329',
            plot_bgcolor='#1e2329',
            margin=dict(l=10, r=10, t=10, b=30),
            xaxis=dict(
                showgrid=True,
                gridcolor='#2b3139',
                showline=False,
                zeroline=False,
                rangeslider=dict(visible=False)
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='#2b3139',
                showline=False,
                zeroline=False,
                side='right'
            ),
            hovermode='x unified',
            showlegend=False,
            font=dict(color='#848e9c', size=11)
        )
    else:
        # Empty chart while waiting for data
        fig = go.Figure()
        fig.update_layout(
            template='plotly_dark',
            paper_bgcolor='#1e2329',
            plot_bgcolor='#1e2329',
            xaxis=dict(showgrid=False, rangeslider=dict(visible=False)),
            yaxis=dict(showgrid=False),
            annotations=[{
                'text': 'Waiting for candle data...',
                'xref': 'paper',
                'yref': 'paper',
                'x': 0.5,
                'y': 0.5,
                'showarrow': False,
                'font': {'size': 14, 'color': '#848e9c'}
            }]
        )
    
    # Update order book with thread safety
    with orderbook_lock:
        bids = order_book_data['bids'].copy()
        asks = order_book_data['asks'].copy()
        last_price = order_book_data['last_price']
    
    if bids.empty or asks.empty:
        return fig, "Loading...", "Loading...", "...", "..."
    
    # Create bids display (top 10)
    bids_rows = []
    for i in range(min(10, len(bids))):
        row = bids.iloc[i]
        bids_rows.append(html.Div([
            html.Div(f"{row['Total']:.5f}", style={'width': '30%', 'textAlign': 'right', 'color': '#b7bdc6'}),
            html.Div(f"{row['Amount']:.5f}", style={'width': '30%', 'textAlign': 'right', 'color': '#e0e3eb'}),
            html.Div(f"{row['Price']:.2f}", style={'width': '40%', 'textAlign': 'right', 'color': '#0ecb81', 'fontWeight': '500'})
        ], style={
            'display': 'flex',
            'padding': '6px 12px',
            'fontSize': '12px',
            'fontFamily': 'monospace',
            'backgroundColor': '#1e2329' if i % 2 == 0 else '#181a20'
        }))
    
    # Create asks display (top 10, reversed)
    asks_rows = []
    asks_reversed = asks.iloc[::-1].head(10)
    for i in range(len(asks_reversed)):
        row = asks_reversed.iloc[i]
        asks_rows.append(html.Div([
            html.Div(f"{row['Total']:.5f}", style={'width': '30%', 'textAlign': 'right', 'color': '#b7bdc6'}),
            html.Div(f"{row['Amount']:.5f}", style={'width': '30%', 'textAlign': 'right', 'color': '#e0e3eb'}),
            html.Div(f"{row['Price']:.2f}", style={'width': '40%', 'textAlign': 'right', 'color': '#f6465d', 'fontWeight': '500'})
        ], style={
            'display': 'flex',
            'padding': '6px 12px',
            'fontSize': '12px',
            'fontFamily': 'monospace',
            'backgroundColor': '#1e2329' if i % 2 == 0 else '#181a20'
        }))
    
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
    
    return fig, html.Div(bids_rows), html.Div(asks_rows), spread_display, last_price_str

if __name__ == '__main__':
    print("Starting BTC/USDT Trading Dashboard...")
    print("Waiting for WebSocket connections...")
    
    # Start WebSocket threads with slight delay
    Thread(target=run_orderbook_websocket, daemon=True).start()
    time.sleep(0.5)
    Thread(target=run_trade_websocket, daemon=True).start()
    time.sleep(1)
    
    print("Starting Dash server on http://127.0.0.1:8050")
    app.run(debug=True, host='127.0.0.1', port=8050)