"""
Bitcoin Price & Sentiment Analysis Dashboard

This Streamlit dashboard displays:
1. Real-time Bitcoin price with interactive charts
2. Latest Bitcoin news articles
3. News sentiment analysis
4. Fear & Greed Index from alternative.me
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import time
import sys
import os
import pytz
import numpy as np

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard.data_queries import (
    get_latest_price,
    get_price_history,
    get_latest_articles,
    get_sentiment_summary,
    get_fear_greed_index,
    get_recent_whale_transactions,
    get_whale_stats,
    get_whale_trend,
    get_block_metrics,
    get_whale_sentiment,
    get_block_whale_correlation,
    get_lstm_predictions
)
from dashboard.binance_ws import start_price_stream, get_realtime_price
from dashboard.cryptocompare_orderbook_ws import start_orderbook_stream, get_orderbook_data

# Page configuration
st.set_page_config(
    page_title="Bitcoin Analytics Dashboard",
    page_icon="B",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        color: #FF9500;
        text-align: center;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #1E1E1E;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
    }
    .article-card {
        background-color: #2C2C2C;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        border-left: 4px solid #FF9500;
    }
    .article-title {
        font-weight: bold;
        color: #FFFFFF;
        margin-bottom: 0.5rem;
    }
    .article-meta {
        font-size: 0.85rem;
        color: #888888;
    }
    .sentiment-positive {
        color: #10B981;
    }
    .sentiment-negative {
        color: #EF4444;
    }
    .sentiment-neutral {
        color: #F59E0B;
    }
    .news-grid {
        max-height: 380px;
        overflow-y: auto;
        overflow-x: hidden;
        padding-right: 8px;
    }
    .news-grid::-webkit-scrollbar {
        width: 6px;
    }
    .news-grid::-webkit-scrollbar-track {
        background: #1E1E1E;
        border-radius: 3px;
    }
    .news-grid::-webkit-scrollbar-thumb {
        background: #FF9500;
        border-radius: 3px;
    }
    .news-grid::-webkit-scrollbar-thumb:hover {
        background: #FFA500;
    }
    /* Fix for metric containers to show full content */
    [data-testid="stMetricContainer"] {
        overflow: visible !important;
    }
    
    /* Ensure metric values aren't clipped - reduce font size for better fit */
    [data-testid="stMetricValue"] {
        overflow: visible !important;
        line-height: 1.2 !important;
        padding: 0.25rem 0 !important;
        font-size: 1.5rem !important;
    }
    
    /* Fix for Streamlit column containers */
    [data-testid="stHorizontalBlock"] {
        overflow: visible !important;
    }
    
    /* Ensure all metric-related elements have proper spacing - smaller labels */
    [data-testid="stMetricLabel"] {
        overflow: visible !important;
        padding: 0.1rem 0 !important;
        font-size: 0.75rem !important;
    }
    
    [data-testid="stMetricDelta"] {
        overflow: visible !important;
        padding: 0.1rem 0 !important;
        font-size: 0.75rem !important;
    }
    
    /* Fix for custom price display - reduce size slightly */
    .price-number {
        overflow: visible !important;
        line-height: 1.2 !important;
        padding: 0.25rem 0 !important;
        font-size: 2rem !important;
    }
    .news-card {
        background: linear-gradient(135deg, #2C2C2C 0%, #1E1E1E 100%);
        border-radius: 10px;
        padding: 14px;
        margin-bottom: 12px;
        overflow: hidden;
        transition: transform 0.15s, box-shadow 0.15s;
        border: 1px solid #3C3C3C;
        cursor: pointer;
    }
    .news-card:hover {
        transform: translateX(4px);
        box-shadow: 0 2px 8px rgba(255, 149, 0, 0.25);
        border-color: #FF9500;
    }
    .news-card-title {
        font-size: 0.95rem;
        font-weight: 600;
        color: #FFFFFF;
        line-height: 1.4;
        margin-bottom: 4px;
    }
    .news-card-time {
        font-size: 0.7rem;
        color: #888888;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 4px;
    }
    .news-card-preview {
        font-size: 0.8rem;
        color: #AAAAAA;
        line-height: 1.4;
        margin-bottom: 10px;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    .news-card-footer {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 8px;
        margin-top: auto;
    }
    .news-source {
        display: inline-block;
        background: #3C3C3C;
        color: #FFA500;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        white-space: nowrap;
    }
    .news-sentiment {
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.7rem;
        font-weight: 600;
        white-space: nowrap;
    }
    .price-flash-green {
        animation: flashGreenText 0.8s ease-in-out;
    }
    .price-flash-red {
        animation: flashRedText 0.8s ease-in-out;
    }
    @keyframes flashGreenText {
        0% { 
            color: #FFFFFF;
        }
        30% { 
            color: #10B981;
        }
        60% { 
            color: #10B981;
        }
        100% { 
            color: #FFFFFF;
        }
    }
    @keyframes flashRedText {
        0% { 
            color: #FFFFFF;
        }
        30% { 
            color: #EF4444;
        }
        60% { 
            color: #EF4444;
        }
        100% { 
            color: #FFFFFF;
        }
    }
    .price-number {
        font-size: 2.5rem;
        font-weight: 600;
        line-height: 1.2;
        color: #FFFFFF;
        transition: color 0.1s;
    }
</style>
""", unsafe_allow_html=True)


def calculate_ma(df, period):
    """Calculate Moving Average"""
    return df['close'].rolling(window=period).mean()


def calculate_rsi(df, period=14):
    """Calculate Relative Strength Index"""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(df, fast=12, slow=26, signal=9):
    """Calculate MACD (Moving Average Convergence Divergence)"""
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def create_price_chart(df, indicators=None):
    """Create an interactive candlestick chart with optional moving averages"""
    if df.empty:
        return None
    
    if indicators is None:
        indicators = []
    
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
        subplot_titles=('Bitcoin Price (OHLC)', 'Volume')
    )
    
    # Candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=df['time'],
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='BTC/USD',
            increasing_line_color='#10B981',
            decreasing_line_color='#EF4444'
        ),
        row=1, col=1
    )
    
    # Add Moving Averages to price chart
    if 'MA50' in indicators:
        ma50 = calculate_ma(df, 50)
        fig.add_trace(
            go.Scatter(
                x=df['time'],
                y=ma50,
                name='MA50',
                line=dict(color='#FF9500', width=2),
                mode='lines'
            ),
            row=1, col=1
        )
    
    if 'MA200' in indicators:
        ma200 = calculate_ma(df, 200)
        fig.add_trace(
            go.Scatter(
                x=df['time'],
                y=ma200,
                name='MA200',
                line=dict(color='#8B5CF6', width=2),
                mode='lines'
            ),
            row=1, col=1
        )
    
    # Volume bar chart
    colors = ['#10B981' if df.iloc[i]['close'] >= df.iloc[i]['open'] else '#EF4444' 
              for i in range(len(df))]
    
    fig.add_trace(
        go.Bar(
            x=df['time'],
            y=df['volume'],
            name='Volume',
            marker_color=colors,
            showlegend=False
        ),
        row=2, col=1
    )
    
    fig.update_layout(
        height=600,
        xaxis_rangeslider_visible=False,
        template='plotly_dark',
        hovermode='x unified',
        margin=dict(l=50, r=50, t=50, b=50),
        legend=dict(x=1.02, y=1, xanchor='left', yanchor='top', bgcolor='rgba(0,0,0,0)')
    )
    
    fig.update_xaxes(title_text="Time", row=2, col=1)
    fig.update_yaxes(title_text="Price (USD)", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    
    return fig


def create_rsi_chart(df):
    """Create a separate RSI chart"""
    if df.empty:
        return None
    
    rsi = calculate_rsi(df, 14)
    
    fig = go.Figure()
    
    fig.add_trace(
        go.Scatter(
            x=df['time'],
            y=rsi,
            name='RSI',
            line=dict(color='#F59E0B', width=2),
            mode='lines'
        )
    )
    
    # Add RSI overbought/oversold lines
    fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.5, annotation_text="Overbought (70)")
    fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.5, annotation_text="Oversold (30)")
    
    fig.update_layout(
        height=300,
        title="RSI (Relative Strength Index)",
        xaxis_title="Time",
        yaxis_title="RSI",
        yaxis_range=[0, 100],
        template='plotly_dark',
        hovermode='x unified',
        margin=dict(l=50, r=50, t=50, b=50),
        legend=dict(x=1.02, y=1, xanchor='left', yanchor='top', bgcolor='rgba(0,0,0,0)')
    )
    
    return fig


def create_macd_chart(df):
    """Create a separate MACD chart"""
    if df.empty:
        return None
    
    macd_line, signal_line, histogram = calculate_macd(df)
    
    fig = go.Figure()
    
    fig.add_trace(
        go.Scatter(
            x=df['time'],
            y=macd_line,
            name='MACD',
            line=dict(color='#10B981', width=2),
            mode='lines'
        )
    )
    
    fig.add_trace(
        go.Scatter(
            x=df['time'],
            y=signal_line,
            name='Signal',
            line=dict(color='#EF4444', width=2),
            mode='lines'
        )
    )
    
    fig.add_trace(
        go.Bar(
            x=df['time'],
            y=histogram,
            name='Histogram',
            marker_color=['#10B981' if h >= 0 else '#EF4444' for h in histogram],
            opacity=0.6
        )
    )
    
    fig.update_layout(
        height=300,
        title="MACD (Moving Average Convergence Divergence)",
        xaxis_title="Time",
        yaxis_title="MACD",
        template='plotly_dark',
        hovermode='x unified',
        margin=dict(l=50, r=50, t=50, b=50),
        legend=dict(x=1.02, y=1, xanchor='left', yanchor='top', bgcolor='rgba(0,0,0,0)')
    )
    
    return fig


def create_sentiment_chart(df):
    """Create sentiment trend chart"""
    if df.empty:
        return None
    
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        subplot_titles=('Average Sentiment Score', 'Article Distribution'),
        row_heights=[0.5, 0.5]
    )
    
    # Sentiment score line
    fig.add_trace(
        go.Scatter(
            x=df['bucket'],
            y=df['avg_sentiment'],
            mode='lines+markers',
            name='Avg Sentiment',
            line=dict(color='#FF9500', width=3),
            fill='tozeroy',
            fillcolor='rgba(255, 149, 0, 0.1)'
        ),
        row=1, col=1
    )
    
    # Add zero line
    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=1, col=1)
    
    # Stacked bar chart for sentiment distribution
    fig.add_trace(
        go.Bar(x=df['bucket'], y=df['positive_count'], name='Positive', 
               marker_color='#10B981'),
        row=2, col=1
    )
    fig.add_trace(
        go.Bar(x=df['bucket'], y=df['neutral_count'], name='Neutral',
               marker_color='#F59E0B'),
        row=2, col=1
    )
    fig.add_trace(
        go.Bar(x=df['bucket'], y=df['negative_count'], name='Negative',
               marker_color='#EF4444'),
        row=2, col=1
    )
    
    fig.update_layout(
        height=500,
        template='plotly_dark',
        barmode='stack',
        hovermode='x unified',
        margin=dict(l=50, r=50, t=50, b=50)
    )
    
    fig.update_yaxes(title_text="Sentiment Score", row=1, col=1)
    fig.update_yaxes(title_text="Article Count", row=2, col=1)
    fig.update_xaxes(title_text="Time", row=2, col=1)
    
    return fig


def create_fear_greed_gauge(fng_data):
    """Create a speedometer-style gauge for Fear & Greed Index"""
    if fng_data is None:
        return None
    
    value = fng_data['value']
    
    # Define color ranges
    if value <= 25:
        color = "#EF4444"  # Extreme Fear - Red
    elif value <= 45:
        color = "#F59E0B"  # Fear - Orange
    elif value <= 55:
        color = "#F59E0B"  # Neutral - Yellow
    elif value <= 75:
        color = "#10B981"  # Greed - Light Green
    else:
        color = "#059669"  # Extreme Greed - Dark Green
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=value,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': f"<b>{fng_data['classification']}</b>", 'font': {'size': 24}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white"},
            'bar': {'color': color, 'thickness': 0.75},
            'bgcolor': "rgba(0,0,0,0)",
            'borderwidth': 2,
            'bordercolor': "white",
            'steps': [
                {'range': [0, 25], 'color': 'rgba(239, 68, 68, 0.3)'},
                {'range': [25, 45], 'color': 'rgba(245, 158, 11, 0.3)'},
                {'range': [45, 55], 'color': 'rgba(245, 158, 11, 0.2)'},
                {'range': [55, 75], 'color': 'rgba(16, 185, 129, 0.3)'},
                {'range': [75, 100], 'color': 'rgba(5, 150, 105, 0.3)'}
            ],
            'threshold': {
                'line': {'color': "white", 'width': 4},
                'thickness': 0.75,
                'value': value
            }
        }
    ))
    
    fig.update_layout(
        height=300,
        template='plotly_dark',
        margin=dict(l=20, r=20, t=60, b=20),
        font={'color': "white", 'family': "Arial"}
    )
    
    return fig


def create_whale_chart(df):
    """Create whale transaction volume chart"""
    if df.empty:
        return None

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        subplot_titles=('Whale Transaction Count', 'Total BTC Volume'),
        row_heights=[0.5, 0.5]
    )

    # Transaction count bar chart
    fig.add_trace(
        go.Bar(
            x=df['bucket'],
            y=df['transaction_count'],
            name='Whale Txs',
            marker_color='#FF9500',
            hovertemplate='<b>%{y}</b> whales<br>%{x}<extra></extra>'
        ),
        row=1, col=1
    )

    # BTC volume area chart
    fig.add_trace(
        go.Scatter(
            x=df['bucket'],
            y=df['total_btc'],
            mode='lines+markers',
            name='Total BTC',
            line=dict(color='#10B981', width=3),
            fill='tozeroy',
            fillcolor='rgba(16, 185, 129, 0.2)',
            hovertemplate='<b>%{y:.2f} BTC</b><br>%{x}<extra></extra>'
        ),
        row=2, col=1
    )

    fig.update_layout(
        height=400,
        template='plotly_dark',
        hovermode='x unified',
        showlegend=False,
        margin=dict(l=50, r=50, t=50, b=50)
    )

    fig.update_yaxes(title_text="Count", row=1, col=1)
    fig.update_yaxes(title_text="BTC", row=2, col=1)
    fig.update_xaxes(title_text="Time", row=2, col=1)

    return fig


def create_orderbook_table(orderbook_data):
    """Create order book table display"""
    if not orderbook_data:
        return None
    
    bids = orderbook_data.get('bids', [])
    asks = orderbook_data.get('asks', [])
    
    if not bids or not asks:
        return None
    
    # Get top 20 levels
    bids = bids[:20]
    asks = asks[:20]
    
    # Create dataframes with error handling
    try:
        bids_df = pd.DataFrame(bids)
        asks_df = pd.DataFrame(asks)
        
        # Add cumulative totals
        if not bids_df.empty and 'quantity' in bids_df.columns and 'price' in bids_df.columns:
            bids_df['total'] = bids_df['quantity'].cumsum()
            bids_df = bids_df.sort_values('price', ascending=False)
        else:
            return None
        
        if not asks_df.empty and 'quantity' in asks_df.columns and 'price' in asks_df.columns:
            asks_df['total'] = asks_df['quantity'].cumsum()
            asks_df = asks_df.sort_values('price', ascending=True)
        else:
            return None
        
        return bids_df, asks_df
    except Exception as e:
        print(f"Error creating orderbook table: {e}")
        return None


def create_depth_chart(orderbook_data, current_price=None):
    """
    Create professional exchange-style order book depth chart (Binance/Bitstamp style).
    
    This chart shows cumulative order book depth with:
    1. Step-style lines for smooth staircase look
    2. Semi-transparent gradient fills
    3. Interactive hover tooltips
    4. Vertical line at mid/current price
    5. Professional color scheme: green (bids), red (asks)
    6. Responsive layout with proper aspect ratio
    """
    if not orderbook_data:
        return None
    
    bids = orderbook_data.get('bids', [])
    asks = orderbook_data.get('asks', [])
    
    if not bids or not asks:
        return None
    
    try:
        # Convert to pandas DataFrames for easier manipulation
        bids_df = pd.DataFrame(bids)
        asks_df = pd.DataFrame(asks)
        
        # Validate required columns exist
        if 'price' not in bids_df.columns or 'quantity' not in bids_df.columns:
            return None
        if 'price' not in asks_df.columns or 'quantity' not in asks_df.columns:
            return None
        
        # Sort: bids descending (highest first), asks ascending (lowest first)
        bids_df = bids_df.sort_values('price', ascending=False).reset_index(drop=True)
        asks_df = asks_df.sort_values('price', ascending=True).reset_index(drop=True)
        
        # Calculate cumulative amounts (depth) - this creates the classic depth chart shape
        bids_df['cum_quantity'] = bids_df['quantity'].cumsum()
        asks_df['cum_quantity'] = asks_df['quantity'].cumsum()
        
        # Calculate mid price
        if current_price:
            mid_price = current_price
            label = "Current Price"
        elif len(bids_df) > 0 and len(asks_df) > 0:
            best_bid = bids_df['price'].iloc[0]
            best_ask = asks_df['price'].iloc[0]
            mid_price = (best_bid + best_ask) / 2
            spread = best_ask - best_bid
            spread_pct = (spread / best_bid) * 100
            label = f"Mid: ${mid_price:,.2f}"
        else:
            mid_price = None
            label = ""
        
        # Create figure with optimized settings
        fig = go.Figure()
        
        # Add bid side (buy orders) - GREEN with enhanced styling
        fig.add_trace(go.Scatter(
            x=bids_df['price'],
            y=bids_df['cum_quantity'],
            mode='lines',
            name='Bids',
            line=dict(
                color='rgb(0, 230, 118)',  # Bright green (Binance-style)
                width=2.5,
                shape='hv'  # Horizontal-vertical step for staircase effect
            ),
            fill='tozeroy',
            fillcolor='rgba(0, 230, 118, 0.15)',  # Subtle green gradient
            fillgradient=dict(
                type='vertical',
                colorscale=[[0, 'rgba(0, 230, 118, 0.3)'], [1, 'rgba(0, 230, 118, 0.05)']]
            ),
            hovertemplate=(
                '<b style="color:#00E676">BUY SIDE</b><br>' +
                '<b>Price:</b> $%{x:,.2f}<br>' +
                '<b>Cumulative:</b> %{y:.4f} BTC<br>' +
                '<b>Total Value:</b> $%{customdata:,.0f}<br>' +
                '<extra></extra>'
            ),
            customdata=bids_df['cum_quantity'] * bids_df['price']
        ))
        
        # Add ask side (sell orders) - RED with enhanced styling
        fig.add_trace(go.Scatter(
            x=asks_df['price'],
            y=asks_df['cum_quantity'],
            mode='lines',
            name='Asks',
            line=dict(
                color='rgb(246, 70, 93)',  # Bright red (Binance-style)
                width=2.5,
                shape='hv'  # Step line for staircase effect
            ),
            fill='tozeroy',
            fillcolor='rgba(246, 70, 93, 0.15)',  # Subtle red gradient
            fillgradient=dict(
                type='vertical',
                colorscale=[[0, 'rgba(246, 70, 93, 0.3)'], [1, 'rgba(246, 70, 93, 0.05)']]
            ),
            hovertemplate=(
                '<b style="color:#F6465D">SELL SIDE</b><br>' +
                '<b>Price:</b> $%{x:,.2f}<br>' +
                '<b>Cumulative:</b> %{y:.4f} BTC<br>' +
                '<b>Total Value:</b> $%{customdata:,.0f}<br>' +
                '<extra></extra>'
            ),
            customdata=asks_df['cum_quantity'] * asks_df['price']
        ))
        
        # Add vertical line at mid/current price with annotation
        if mid_price:
            # Add subtle background area at mid price
            max_depth = max(
                bids_df['cum_quantity'].max() if len(bids_df) > 0 else 0,
                asks_df['cum_quantity'].max() if len(asks_df) > 0 else 0
            )
            
            fig.add_vline(
                x=mid_price,
                line_dash="dot",
                line_color="rgba(255, 193, 7, 0.8)",  # Amber/yellow
                line_width=2.5,
                opacity=1
            )
            
            # Add annotation with better styling
            fig.add_annotation(
                x=mid_price,
                y=max_depth * 0.95,
                text=label,
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowwidth=2,
                arrowcolor="rgba(255, 193, 7, 0.8)",
                ax=0,
                ay=-40,
                bgcolor="rgba(255, 193, 7, 0.2)",
                bordercolor="rgba(255, 193, 7, 0.8)",
                borderwidth=2,
                borderpad=6,
                font=dict(size=12, color="white", family="Arial Black")
            )
        
        # Professional layout matching Binance/Bitstamp style
        fig.update_layout(
            title={
                'text': "<b>Market Depth</b>",
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 20, 'color': '#E0E0E0', 'family': 'Arial Black'}
            },
            xaxis_title="<b>Price (USD)</b>",
            yaxis_title="<b>Cumulative Volume (BTC)</b>",
            template='plotly_dark',
            height=550,
            hovermode='x unified',
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5,
                bgcolor="rgba(30, 30, 30, 0.8)",
                bordercolor="rgba(255, 255, 255, 0.3)",
                borderwidth=1,
                font=dict(size=12, color="white", family="Arial")
            ),
            margin=dict(l=70, r=50, t=100, b=70),
            plot_bgcolor='#161A1E',  # Darker background
            paper_bgcolor='#0E1117',
            xaxis=dict(
                gridcolor='rgba(128, 128, 128, 0.15)',
                gridwidth=1,
                zeroline=False,
                tickformat='$,.0f',
                tickfont=dict(size=11, color='#B0B0B0'),
                title_font=dict(size=13, color='#E0E0E0')
            ),
            yaxis=dict(
                gridcolor='rgba(128, 128, 128, 0.15)',
                gridwidth=1,
                zeroline=False,
                tickformat='.3f',
                tickfont=dict(size=11, color='#B0B0B0'),
                title_font=dict(size=13, color='#E0E0E0')
            ),
            hoverlabel=dict(
                bgcolor="rgba(30, 30, 30, 0.95)",
                font_size=12,
                font_family="Arial",
                bordercolor="rgba(255, 255, 255, 0.3)"
            )
        )
        
        # Add range slider for better interaction (optional, can be removed if too cluttered)
        fig.update_xaxes(
            rangeslider_visible=False,  # Keep it clean like exchanges
            fixedrange=False  # Allow zoom
        )
        
        return fig
    
    except Exception as e:
        print(f"Error creating depth chart: {e}")
        return None


def create_block_metrics_chart(df):
    """Create a chart for block metrics"""
    if df.empty:
        return None
    
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=('Whale Activity (BTC)', 'Exchange Flow (BTC)', 'Consolidation & Distribution'),
        row_heights=[0.4, 0.3, 0.3]
    )
    
    # Whale activity
    fig.add_trace(
        go.Scatter(
            x=df['block_timestamp'],
            y=df['whale_total_external_btc'],
            mode='lines+markers',
            name='Whale External BTC',
            line=dict(color='#FF9500', width=2),
            fill='tozeroy',
            fillcolor='rgba(255, 149, 0, 0.2)'
        ),
        row=1, col=1
    )
    
    # Exchange flow
    fig.add_trace(
        go.Scatter(
            x=df['block_timestamp'],
            y=df['to_exchange_btc'],
            mode='lines+markers',
            name='To Exchange',
            line=dict(color='#EF4444', width=2)
        ),
        row=2, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=df['block_timestamp'],
            y=df['from_exchange_btc'],
            mode='lines+markers',
            name='From Exchange',
            line=dict(color='#10B981', width=2)
        ),
        row=2, col=1
    )
    
    # Consolidation & Distribution
    fig.add_trace(
        go.Scatter(
            x=df['block_timestamp'],
            y=df['consolidation_index'],
            mode='lines+markers',
            name='Consolidation',
            line=dict(color='#8B5CF6', width=2)
        ),
        row=3, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=df['block_timestamp'],
            y=df['distribution_index'],
            mode='lines+markers',
            name='Distribution',
            line=dict(color='#3B82F6', width=2)
        ),
        row=3, col=1
    )
    
    fig.update_layout(
        height=700,
        template='plotly_dark',
        hovermode='x unified',
        margin=dict(l=50, r=50, t=50, b=50),
        legend=dict(x=1.02, y=1, xanchor='left', yanchor='top', bgcolor='rgba(0,0,0,0)')
    )
    
    fig.update_yaxes(title_text="BTC", row=1, col=1)
    fig.update_yaxes(title_text="BTC", row=2, col=1)
    fig.update_yaxes(title_text="Index", row=3, col=1)
    fig.update_xaxes(title_text="Block Time", row=3, col=1)
    
    return fig


def create_sentiment_gauge_chart(sentiment_data):
    """Create a gauge chart for whale sentiment"""
    if sentiment_data.empty:
        return None
    
    latest_sentiment = sentiment_data.iloc[-1]
    score = latest_sentiment['score']
    sentiment_label = latest_sentiment['sentiment']
    
    # Define color ranges
    if sentiment_label == 'bullish':
        color = "#10B981"  # Green
    elif sentiment_label == 'bearish':
        color = "#EF4444"  # Red
    else:
        color = "#F59E0B"  # Orange
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': f"<b>Whale Sentiment</b><br><span style='font-size:0.8em;color:{color}'>{sentiment_label.title()}</span>", 
               'font': {'size': 20}},
        gauge={
            'axis': {'range': [-1, 1], 'tickwidth': 1, 'tickcolor': "white"},
            'bar': {'color': color, 'thickness': 0.75},
            'bgcolor': "rgba(0,0,0,0)",
            'borderwidth': 2,
            'bordercolor': "white",
            'steps': [
                {'range': [-1, -0.5], 'color': 'rgba(239, 68, 68, 0.3)'},
                {'range': [-0.5, 0], 'color': 'rgba(245, 158, 11, 0.3)'},
                {'range': [0, 0.5], 'color': 'rgba(16, 185, 129, 0.3)'},
                {'range': [0.5, 1], 'color': 'rgba(5, 150, 105, 0.3)'}
            ],
            'threshold': {
                'line': {'color': "white", 'width': 4},
                'thickness': 0.75,
                'value': score
            }
        }
    ))
    
    fig.update_layout(
        height=300,
        template='plotly_dark',
        margin=dict(l=20, r=20, t=60, b=20),
        font={'color': "white", 'family': "Arial"}
    )
    
    return fig


def create_sentiment_components_chart(df):
    """Create a chart showing sentiment components over time"""
    if df.empty:
        return None
    
    fig = go.Figure()
    
    fig.add_trace(
        go.Scatter(
            x=df['block_timestamp'],
            y=df['whale_flow_component'],
            mode='lines+markers',
            name='Whale Flow',
            line=dict(color='#FF9500', width=2)
        )
    )
    
    fig.add_trace(
        go.Scatter(
            x=df['block_timestamp'],
            y=df['exchange_pressure_component'],
            mode='lines+markers',
            name='Exchange Pressure',
            line=dict(color='#8B5CF6', width=2)
        )
    )
    
    fig.add_trace(
        go.Scatter(
            x=df['block_timestamp'],
            y=df['fee_pressure_component'],
            mode='lines+markers',
            name='Fee Pressure',
            line=dict(color='#3B82F6', width=2)
        )
    )
    
    fig.add_trace(
        go.Scatter(
            x=df['block_timestamp'],
            y=df['utilization_component'],
            mode='lines+markers',
            name='Utilization',
            line=dict(color='#10B981', width=2)
        )
    )
    
    # Add zero line
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    
    fig.update_layout(
        height=300,
        title="Sentiment Components Over Time",
        xaxis_title="Block Time",
        yaxis_title="Component Value",
        template='plotly_dark',
        hovermode='x unified',
        margin=dict(l=50, r=50, t=50, b=50),
        legend=dict(x=1.02, y=1, xanchor='left', yanchor='top', bgcolor='rgba(0,0,0,0)')
    )
    
    return fig


def create_prediction_metrics(predictions_df):
    """
    Create metrics display for LSTM predictions
    
    Args:
        predictions_df: DataFrame with LSTM predictions
        
    Returns:
        None (displays metrics in Streamlit)
    """
    if predictions_df.empty:
        st.info("No prediction data available.")
        return
    
    # Get the latest prediction
    latest_prediction = predictions_df.iloc[-1]
    
    # Calculate percentage changes
    base_price = latest_prediction['base_price']
    predicted_low = latest_prediction['predicted_low']
    predicted_high = latest_prediction['predicted_high']
    predicted_mean = latest_prediction['predicted_mean']
    predicted_std = latest_prediction['predicted_std']
    
    low_change_pct = ((predicted_low - base_price) / base_price) * 100
    high_change_pct = ((predicted_high - base_price) / base_price) * 100
    mean_change_pct = ((predicted_mean - base_price) / base_price) * 100
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Predicted Low",
            value=f"${predicted_low:,.2f}",
            delta=f"{low_change_pct:.2f}%"
        )
    
    with col2:
        st.metric(
            label="Predicted Mean",
            value=f"${predicted_mean:,.2f}",
            delta=f"{mean_change_pct:.2f}%"
        )
    
    with col3:
        st.metric(
            label="Predicted High",
            value=f"${predicted_high:,.2f}",
            delta=f"{high_change_pct:.2f}%"
        )
    
    with col4:
        st.metric(
            label="Prediction Std Dev",
            value=f"${predicted_std:.2f}"
        )
    
    # Display additional info
    st.caption(f"Base Price: ${base_price:,.2f}")
    st.caption(f"Prediction Time: {latest_prediction['prediction_time'].strftime('%Y-%m-%d %H:%M:%S')} SGT")
    st.caption(f"Model Run ID: {latest_prediction['run_id']}")


def create_price_range_indicator(predictions_df):
    """
    Create a visual indicator showing the predicted price range
    
    Args:
        predictions_df: DataFrame with LSTM predictions
        
    Returns:
        HTML content for the price range indicator
    """
    if predictions_df.empty:
        return None
    
    latest_prediction = predictions_df.iloc[-1]
    base_price = latest_prediction['base_price']
    predicted_low = latest_prediction['predicted_low']
    predicted_high = latest_prediction['predicted_high']
    predicted_mean = latest_prediction['predicted_mean']
    
    # Calculate positions for the indicator
    total_range = predicted_high - predicted_low
    low_pos = (predicted_low - base_price) / total_range * 100 + 50
    mean_pos = (predicted_mean - base_price) / total_range * 100 + 50
    high_pos = (predicted_high - base_price) / total_range * 100 + 50
    
    # Determine color for mean based on direction
    mean_color = "#10B981" if predicted_mean >= base_price else "#EF4444"
    
    return f"""
    <div style="margin: 20px 0;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
            <span>${predicted_low:,.2f}</span>
            <span style="font-weight: bold; color: {mean_color};">${predicted_mean:,.2f}</span>
            <span>${predicted_high:,.2f}</span>
        </div>
        <div style="position: relative; height: 30px; background: linear-gradient(to right, #EF4444, #F59E0B, #10B981); border-radius: 15px;">
            <div style="position: absolute; left: 50%; top: 0; bottom: 0; width: 2px; background: white;"></div>
            <div style="position: absolute; left: {low_pos}%; top: 0; bottom: 0; width: 2px; background: white;"></div>
            <div style="position: absolute; left: {mean_pos}%; top: 0; bottom: 0; width: 4px; background: {mean_color};"></div>
            <div style="position: absolute; left: {high_pos}%; top: 0; bottom: 0; width: 2px; background: white;"></div>
            <div style="position: absolute; left: 50%; top: -20px; transform: translateX(-50%); color: white; font-size: 0.8rem;">Base: ${base_price:,.2f}</div>
        </div>
    </div>
    """


def create_confidence_gauge(predictions_df):
    """
    Create a gauge chart showing prediction confidence based on standard deviation
    
    Args:
        predictions_df: DataFrame with LSTM predictions
        
    Returns:
        Plotly figure
    """
    if predictions_df.empty:
        return None
    
    latest_prediction = predictions_df.iloc[-1]
    base_price = latest_prediction['base_price']
    predicted_std = latest_prediction['predicted_std']
    
    # Calculate confidence as inverse of relative standard deviation
    # Lower std relative to price means higher confidence
    relative_std = predicted_std / base_price
    confidence = max(0, min(100, 100 * (1 - relative_std * 100)))  # Scale to 0-100
    
    # Determine color based on confidence level
    if confidence >= 80:
        color = "#10B981"  # Green
    elif confidence >= 60:
        color = "#F59E0B"  # Orange
    else:
        color = "#EF4444"  # Red
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=confidence,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "<b>Prediction Confidence</b>", 'font': {'size': 20}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white"},
            'bar': {'color': color, 'thickness': 0.75},
            'bgcolor': "rgba(0,0,0,0)",
            'borderwidth': 2,
            'bordercolor': "white",
            'steps': [
                {'range': [0, 60], 'color': 'rgba(239, 68, 68, 0.3)'},
                {'range': [60, 80], 'color': 'rgba(245, 158, 11, 0.3)'},
                {'range': [80, 100], 'color': 'rgba(16, 185, 129, 0.3)'}
            ],
            'threshold': {
                'line': {'color': "white", 'width': 4},
                'thickness': 0.75,
                'value': confidence
            }
        }
    ))
    
    fig.update_layout(
        height=300,
        template='plotly_dark',
        margin=dict(l=20, r=20, t=60, b=20),
        font={'color': "white", 'family': "Arial"}
    )
    
    return fig


def main():
    """Main dashboard function"""
    
    # Initialize WebSocket price streamer (runs in background thread)
    if 'ws_initialized' not in st.session_state:
        start_price_stream()
        st.session_state.ws_initialized = True
    
    # Initialize WebSocket order book streamer (runs in background thread)
    if 'orderbook_ws_initialized' not in st.session_state:
        start_orderbook_stream()
        st.session_state.orderbook_ws_initialized = True
    
    # Header
    st.markdown('<h1 class="main-header">Bitcoin Analytics Dashboard</h1>', 
                unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("Settings")
        
        # Currency selector
        st.subheader("Currency")
        currency = st.radio(
            "Display Currency",
            options=["USD", "SGD"],
            index=0,
            horizontal=True,
            help="Choose which currency to display prices in"
        )
        
        # Get live exchange rate
        from dashboard.data_queries import get_exchange_rate
        usd_to_sgd = get_exchange_rate('USD', 'SGD')
        currency_symbol = "$" if currency == "USD" else "S$"
        exchange_rate = 1.0 if currency == "USD" else usd_to_sgd
        
        # Show exchange rate info
        if currency == "SGD":
            st.caption(f"1 USD = {usd_to_sgd:.4f} SGD")
        
        st.divider()
        
        # Price Chart Options
        st.subheader("Price Chart")
        
        # Time range presets
        time_range = st.selectbox(
            "Time Range",
            ["Last 24 hours", "Last 7 days", "Last 30 days"],
            index=2,
            help="Select a preset time range for the price chart"
        )
        
        # Map time range to interval and limit
        range_config = {
            "Last 24 hours": ("5min", 288),      # 24h * 60min / 5min
            "Last 7 days": ("1hour", 168),       # 7 days * 24 hours
            "Last 30 days": ("1hour", 720)       # 30 days * 24 hours
        }
        
        price_interval, price_limit = range_config[time_range]
        
        # Show candle interval info
        candle_interval_map = {
            "5min": "5-minute candles",
            "1hour": "1-hour candles",
            "1day": "Daily candles",
            "1week": "Weekly candles"
        }
        st.caption(f"Using {candle_interval_map[price_interval]}")
        
        # Technical Indicators
        st.subheader("Technical Indicators")
        selected_indicators = st.multiselect(
            "Select Indicators",
            options=["MA50", "MA200", "RSI", "MACD"],
            default=[],
            help="Choose technical indicators to display on the chart"
        )
        # Store in session state for access in main chart area
        st.session_state.selected_indicators = selected_indicators
        
        st.divider()
        
        # Sentiment options
        st.subheader("Sentiment Analysis")
        
        sentiment_period = st.selectbox(
            "Analysis Period",
            ["Last 24 hours", "Last 7 days", "Last 30 days"],
            index=0,
            help="Select time period for sentiment analysis"
        )
        
        # Map sentiment period to interval and limit
        sentiment_config = {
            "Last 24 hours": ("1 hour", 24),
            "Last 7 days": ("1 day", 7),
            "Last 30 days": ("1 day", 30)
        }
        
        sentiment_interval, sentiment_limit = sentiment_config[sentiment_period]
        
        # Show data source info
        st.caption("📰 Sources: NewsAPI, CryptoCompare, Reddit")
        
        st.divider()
        
        # Refresh button
        if st.button("Refresh Now", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        
        # Last update time
        import pytz
        singapore_tz = pytz.timezone('Asia/Singapore')
        current_time = datetime.now(singapore_tz)
        st.caption(f"Last updated: {current_time.strftime('%Y-%m-%d %H:%M:%S')} SGT")
    
    # Main content area
    # Row 1: Latest price metrics (Real-time from WebSocket)
    
    # Try to get real-time price from WebSocket first
    ws_price = get_realtime_price()
    
    # Fallback to database if WebSocket data not available
    if ws_price is None:
        latest_price = get_latest_price()
        if latest_price is not None:
            # Convert database price to WebSocket format
            ws_price = {
                'close': latest_price['close'],
                'open': latest_price['open'],
                'high': latest_price['high'],
                'low': latest_price['low'],
                'volume': latest_price['volume'],
                'time': latest_price['time']
            }
    
    if ws_price is not None:
        # Convert prices to selected currency
        current_price = ws_price['close'] * exchange_rate
        high_price = ws_price['high'] * exchange_rate
        low_price = ws_price['low'] * exchange_rate
        open_price = ws_price['open'] * exchange_rate
        volume_btc = ws_price['volume']
        volume_currency = volume_btc * current_price
        
        # Convert time to Singapore timezone
        price_time = ws_price['time']
        if price_time.tzinfo is None:
            price_time = pytz.UTC.localize(price_time)
        singapore_tz = pytz.timezone('Asia/Singapore')
        price_time_sgt = price_time.astimezone(singapore_tz)
        
        # Track price changes for flash animation
        if 'prev_price' not in st.session_state:
            st.session_state.prev_price = current_price
            st.session_state.price_change_count = 0
        
        # Detect price change direction
        prev_price = st.session_state.prev_price
        price_change = current_price - prev_price
        
        # Determine flash class based on price change - trigger on ANY change
        flash_class = ""
        # Check if price actually changed (even by tiny amounts)
        if price_change > 0:
            flash_class = "price-flash-green"
        elif price_change < 0:
            flash_class = "price-flash-red"
        # Always increment change count when price changes to force re-render
        st.session_state.price_change_count += 1
        
        # Update previous price
        st.session_state.prev_price = current_price
        
        # Display metrics with even spacing
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            # Create custom price display with flash animation on the numbers
            # Use change count to ensure animation retriggers on each change
            change_key = st.session_state.get('price_change_count', 0)
            price_id = f"price-number-{change_key}"
            
            # Calculate percentage change
            if open_price > 0:
                percent_change = ((current_price - open_price) / open_price) * 100
                percent_change_str = f"{'+' if percent_change >= 0 else ''}{percent_change:.2f}%"
            else:
                percent_change_str = "0.00%"
            
            # Match Streamlit metric styling - label at top, value in middle, delta at bottom
            # Use same structure and classes as Streamlit metrics for consistency
            price_html = f"""
            <div style="margin-bottom: 0.5rem;">
                <div style="font-size: 0.75rem; color: rgb(163, 168, 184); margin-bottom: 0.25rem;">
                    Current Price ({currency})
                </div>
                <div class="price-number {flash_class}" id="{price_id}" style="font-size: 2rem; font-weight: 600; line-height: 1.2; color: #FFFFFF;">
                    {currency_symbol}{current_price:,.2f}
                </div>
                <div style="font-size: 0.75rem; color: {'#10B981' if current_price >= open_price else '#EF4444'}; margin-top: 0.25rem;">
                    {percent_change_str}
                </div>
            </div>
            <script>
                // Force animation restart on each price change - use requestAnimationFrame for reliable timing
                (function() {{
                    function triggerAnimation() {{
                        var priceEl = document.getElementById('{price_id}');
                        if (priceEl) {{
                            var hasFlash = priceEl.classList.contains('price-flash-green') || 
                                          priceEl.classList.contains('price-flash-red');
                            if (hasFlash) {{
                                // Force animation restart by removing and re-adding the class
                                var flashClass = priceEl.classList.contains('price-flash-green') ? 'price-flash-green' : 'price-flash-red';
                                priceEl.classList.remove('price-flash-green', 'price-flash-red');
                                // Force reflow to ensure class removal is processed
                                void priceEl.offsetWidth;
                                // Re-add the class to trigger animation
                                priceEl.classList.add(flashClass);
                            }}
                        }}
                    }}
                    // Try immediately
                    triggerAnimation();
                    // Also try after a short delay to catch any timing issues
                    requestAnimationFrame(function() {{
                        requestAnimationFrame(triggerAnimation);
                    }});
                }})();
            </script>
            """
            st.markdown(price_html, unsafe_allow_html=True)
        
        with col2:
            st.metric(
                label=f"High ({currency})",
                value=f"{currency_symbol}{high_price:,.2f}"
            )
        
        with col3:
            st.metric(
                label=f"Low ({currency})",
                value=f"{currency_symbol}{low_price:,.2f}"
            )
        
        with col4:
            st.metric(
                label=f"Volume ({currency})",
                value=f"{currency_symbol}{volume_currency:,.0f}"
            )
        
        with col5:
            st.metric(
                label="Last Updated (SGT)",
                value=price_time_sgt.strftime('%m/%d %H:%M:%S')
            )
    
    st.divider()
    
    # Section 1: Bitcoin Price Chart (Full Width)
    st.subheader("Bitcoin Price Chart")
    price_history = get_price_history(price_interval, price_limit)
    
    if not price_history.empty:
        # Get selected indicators from session state (set in sidebar)
        selected_indicators = st.session_state.get('selected_indicators', [])
        price_chart = create_price_chart(price_history, indicators=selected_indicators)
        if price_chart:
            st.plotly_chart(price_chart, use_container_width=True)
        
        # Display RSI as separate chart if selected
        if 'RSI' in selected_indicators:
            rsi_chart = create_rsi_chart(price_history)
            if rsi_chart:
                st.plotly_chart(rsi_chart, use_container_width=True)
        
        # Display MACD as separate chart if selected
        if 'MACD' in selected_indicators:
            macd_chart = create_macd_chart(price_history)
            if macd_chart:
                st.plotly_chart(macd_chart, use_container_width=True)
    else:
        st.info("Loading price data... Make sure the database is populated.")
    
    st.divider()
    
    # Section 2: News Sentiment Analysis (Full Width)
    st.subheader("News Sentiment Analysis")
    sentiment_data = get_sentiment_summary(sentiment_interval, sentiment_limit)
    
    if not sentiment_data.empty:
        # Display metrics
        col1, col2, col3, col4 = st.columns(4)
        
        latest_sentiment = sentiment_data.iloc[-1]
        
        with col1:
            st.metric(
                label="Average Sentiment",
                value=f"{latest_sentiment['avg_sentiment']:.3f}",
                delta=f"{latest_sentiment['avg_sentiment'] - sentiment_data.iloc[-2]['avg_sentiment']:.3f}" if len(sentiment_data) > 1 else None
            )
        
        with col2:
            st.metric(
                label="Total Articles",
                value=f"{int(latest_sentiment['article_count'])}"
            )
        
        with col3:
            pos_pct = (latest_sentiment['positive_count'] / latest_sentiment['article_count'] * 100) if latest_sentiment['article_count'] > 0 else 0
            st.metric(
                label="Positive",
                value=f"{int(latest_sentiment['positive_count'])}",
                delta=f"{pos_pct:.1f}%"
            )
        
        with col4:
            neg_pct = (latest_sentiment['negative_count'] / latest_sentiment['article_count'] * 100) if latest_sentiment['article_count'] > 0 else 0
            st.metric(
                label="Negative",
                value=f"{int(latest_sentiment['negative_count'])}",
                delta=f"{neg_pct:.1f}%",
                delta_color="inverse"
            )
        
        # Sentiment chart
        sentiment_chart = create_sentiment_chart(sentiment_data)
        if sentiment_chart:
            st.plotly_chart(sentiment_chart, use_container_width=True)
    else:
        st.info("No sentiment data available. Run sentiment analysis scripts first.")
    
    st.divider()
    
    # Section 3: Fear & Greed Index + Latest News (Side by Side)
    col_fear, col_news = st.columns([1, 3])
    
    with col_fear:
        st.subheader("Fear & Greed Index")
        fng_data = get_fear_greed_index()
        
        if fng_data:
            fng_gauge = create_fear_greed_gauge(fng_data)
            if fng_gauge:
                st.plotly_chart(fng_gauge, use_container_width=True)
            
            st.caption(f"Updated: {fng_data['timestamp'].strftime('%Y-%m-%d %H:%M')}")
            st.caption("Source: [alternative.me](https://alternative.me/crypto/fear-and-greed-index)")
        else:
            st.warning("Fear & Greed Index unavailable")
    
    with col_news:
        st.subheader("Latest News")
        articles = get_latest_articles(5)
        
        if not articles.empty:
            # Start scrollable container
            st.markdown('<div class="news-grid">', unsafe_allow_html=True)
            
            for _, article in articles.iterrows():
                sentiment_class = f"sentiment-{article['sentiment_label']}" if pd.notna(article['sentiment_label']) else "sentiment-neutral"
                sentiment_label = article['sentiment_label'].title() if pd.notna(article['sentiment_label']) else "Neutral"
                sentiment_score = f"{article['sentiment_score']:.2f}" if pd.notna(article['sentiment_score']) else "0.00"
                
                article_url = article['url'] if pd.notna(article['url']) else "#"
                
                # Format timestamp
                singapore_tz = pytz.timezone('Asia/Singapore')
                if pd.notna(article.get('published_at')):
                    pub_time = pd.to_datetime(article['published_at'])
                    if pub_time.tz is None:
                        pub_time = pub_time.tz_localize('UTC')
                    pub_time_sgt = pub_time.tz_convert(singapore_tz)
                    
                    # Calculate relative time
                    now = datetime.now(singapore_tz)
                    time_diff = now - pub_time_sgt
                    
                    # If less than 24 hours, show relative time
                    # If 24+ hours, show full date and time
                    total_hours = time_diff.total_seconds() / 3600
                    
                    if total_hours < 24:
                        # Less than 24 hours - show relative time
                        if time_diff.seconds >= 3600:
                            hours = time_diff.seconds // 3600
                            time_str = f"{hours}h ago"
                        elif time_diff.seconds >= 60:
                            minutes = time_diff.seconds // 60
                            time_str = f"{minutes}m ago"
                        else:
                            time_str = "Just now"
                    else:
                        # 24+ hours - show full date and time
                        time_str = pub_time_sgt.strftime('%b %d, %Y %H:%M')
                else:
                    time_str = "Unknown time"
                
                # Get preview text from content (first 150 characters)
                content = article.get('content', '')
                if pd.notna(content) and content:
                    preview_text = content[:150] + "..." if len(content) > 150 else content
                    # Escape HTML characters
                    preview_text = preview_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                else:
                    preview_text = "No preview available."
                
                # Escape title for HTML
                title = str(article['title']).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                
                st.markdown(f"""
                <a href="{article_url}" target="_blank" style="text-decoration: none;">
                    <div class="news-card">
                        <div class="news-card-title">{title}</div>
                        <div class="news-card-time">⏱ {time_str}</div>
                        <div class="news-card-preview">{preview_text}</div>
                        <div class="news-card-footer">
                            <span class="news-source">{article['source']}</span>
                            <span class="news-sentiment {sentiment_class}">{sentiment_label} {sentiment_score}</span>
                        </div>
                    </div>
                </a>
                """, unsafe_allow_html=True)
            
            # End scrollable container
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("No articles available. Run sentiment analysis scripts first.")

    st.divider()

    # Section 4: Whale Transaction Alerts
    st.subheader("Whale Transaction Alerts")

    # Get whale statistics
    whale_stats = get_whale_stats(period_hours=24)

    # Get block metrics and whale sentiment data
    block_metrics = get_block_metrics(limit=24)
    whale_sentiment = get_whale_sentiment(limit=24)
    block_whale_correlation = get_block_whale_correlation(limit=24)

    if whale_stats and whale_stats['transaction_count'] > 0:
        # Display summary metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                label="Whales (24h)",
                value=int(whale_stats['transaction_count'])
            )

        with col2:
            st.metric(
                label="Total Volume",
                value=f"{whale_stats['total_btc']:,.2f} BTC",
                delta=f"${whale_stats['total_usd']/1_000_000:,.1f}M",
                delta_color="off"
            )

        with col3:
            st.metric(
                label="Largest Whale",
                value=f"{whale_stats['max_btc']:,.2f} BTC"
            )

        with col4:
            st.metric(
                label="Average Size",
                value=f"{whale_stats['avg_btc']:,.2f} BTC"
            )

        # Create tabs for different views
        tab1, tab2, tab3 = st.tabs(["Recent Transactions", "Block Metrics", "Whale Sentiment"])
        
        with tab1:
            # Single column layout - focus on transactions
            st.markdown("### Recent Whale Transactions")
            
            # Get recent whales
            whales = get_recent_whale_transactions(limit=5)

            if not whales.empty:
                for _, whale in whales.iterrows():
                    # Format time
                    if pd.notna(whale.get('detected_at')):
                        detected_time = whale['detected_at']
                        time_str = detected_time.strftime('%Y-%m-%d %H:%M')
                    else:
                        time_str = "N/A"

                    # Get transaction link
                    txid = whale['txid']
                    tx_short = f"{txid[:8]}...{txid[-6:]}"
                    explorer_url = f"https://mempool.space/tx/{txid}"

                    # Status indicator
                    status = whale.get('status', 'mempool')
                    if status == 'confirmed':
                        status_icon = "✅"
                        status_color = "#10B981"
                    else:
                        status_icon = "⏳"
                        status_color = "#F59E0B"

                    # Get addresses (handle missing columns gracefully)
                    primary_input = whale.get('primary_input_address') or ''
                    primary_output = whale.get('primary_output_address') or ''
                    
                    # If primary_output is not available, try to extract from output_addresses array
                    if not primary_output and 'output_addresses' in whale and pd.notna(whale.get('output_addresses')):
                        output_addrs = whale['output_addresses']
                        if isinstance(output_addrs, list) and len(output_addrs) > 0:
                            primary_output = output_addrs[0]

                    # Decode address types
                    def get_address_badge(addr):
                        """Get badge for address type"""
                        if not addr or pd.isna(addr):
                            return ""
                        if addr.startswith('1'):
                            return '<span style="background: #6B7280; padding: 2px 6px; border-radius: 4px; font-size: 0.65rem; margin-left: 6px;">Legacy</span>'
                        elif addr.startswith('3'):
                            return '<span style="background: #8B5CF6; padding: 2px 6px; border-radius: 4px; font-size: 0.65rem; margin-left: 6px;">Multisig</span>'
                        elif addr.startswith('bc1q'):
                            return '<span style="background: #10B981; padding: 2px 6px; border-radius: 4px; font-size: 0.65rem; margin-left: 6px;">SegWit</span>'
                        elif addr.startswith('bc1p'):
                            return '<span style="background: #F59E0B; padding: 2px 6px; border-radius: 4px; font-size: 0.65rem; margin-left: 6px;">Taproot</span>'
                        return ""

                    from_badge = get_address_badge(primary_input)
                    to_badge = get_address_badge(primary_output)

                    # Format addresses for display (truncate if too long)
                    def format_address(addr, max_len=22):
                        if not addr or pd.isna(addr):
                            return "N/A"
                        if len(addr) > max_len:
                            return f"{addr[:12]}...{addr[-10:]}"
                        return addr
                    
                    from_addr = format_address(primary_input)
                    to_addr = format_address(primary_output)

                    # Create clickable address links
                    from_addr_link = f"https://mempool.space/address/{primary_input}" if primary_input and pd.notna(primary_input) else "#"
                    to_addr_link = f"https://mempool.space/address/{primary_output}" if primary_output and pd.notna(primary_output) else "#"

                    # Get label if available - color code by severity
                    label = whale.get('label', '')
                    label_colors = {
                        'Whale': {'bg': '#FF9500', 'text': '#FFFFFF'},      # Orange background, white text - most dominant
                        'Shark': {'bg': '#8B5CF6', 'text': '#FFFFFF'},      # Purple background, white text - medium
                        'Dolphin': {'bg': '#3B82F6', 'text': '#FFFFFF'}     # Blue background, white text - least intrusive
                    }
                    label_style = label_colors.get(label, {'bg': '#6B7280', 'text': '#FFFFFF'})
                    label_badge = f'<span style="background: {label_style["bg"]}; color: {label_style["text"]}; padding: 3px 8px; border-radius: 4px; font-size: 0.7rem; margin-left: 8px; font-weight: 600; display: inline-block;">{label}</span>' if label else ''

                    # Display whale card with compact styling
                    st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #1E1E1E 0%, #2C2C2C 100%);
                                border-radius: 8px; padding: 10px 12px; margin-bottom: 8px;
                                border-left: 3px solid #FF9500; box-shadow: 0 1px 4px rgba(0,0,0,0.2);">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                            <div style="flex: 1;">
                                <div style="font-size: 1rem; font-weight: bold; color: #FF9500; margin-bottom: 2px; display: flex; align-items: center;">
                                    {whale['value_btc']:,.2f} BTC {label_badge}
                                </div>
                                <div style="font-size: 0.8rem; color: #888; margin-bottom: 6px;">
                                    ${whale.get('value_usd', whale.get('value_btc', 0) * 110000):,.0f}
                                </div>
                                <div style="font-size: 0.8rem; color: #FFF; line-height: 1.4;">
                                    <div style="margin-bottom: 3px;">
                                        <span style="color: #888;">📤 From:</span> 
                                        <a href="{from_addr_link}" target="_blank" style="color: #FFF; text-decoration: none; font-weight: 500; margin-left: 4px;">{from_addr}</a>{from_badge}
                                    </div>
                                    <div style="margin-bottom: 3px;">
                                        <span style="color: #888;">📥 To:</span> 
                                        <a href="{to_addr_link}" target="_blank" style="color: #FFF; text-decoration: none; font-weight: 500; margin-left: 4px;">{to_addr}</a>{to_badge}
                                    </div>
                                    <div style="margin-top: 4px;">
                                        <a href="{explorer_url}" target="_blank"
                                           style="color: #10B981; text-decoration: none; font-size: 0.75rem;">
                                            🔗 {tx_short}
                                        </a>
                                    </div>
                                </div>
                            </div>
                            <div style="text-align: right; margin-left: 12px; min-width: 120px;">
                                <div style="font-size: 0.7rem; color: #888; margin-bottom: 4px;">
                                    {time_str}
                                </div>
                                <div style="font-size: 0.75rem; color: {status_color}; font-weight: 500;">
                                    {status_icon} {status.title()}
                                </div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No recent whale transactions found.")
        
        with tab2:
            # Block Metrics
            if not block_metrics.empty:
                # Display metrics
                col1, col2, col3, col4 = st.columns(4)
                
                latest_block = block_metrics.iloc[-1]
                
                with col1:
                    st.metric(
                        label="Latest Block",
                        value=f"{latest_block['block_height']:,}"
                    )
                
                with col2:
                    st.metric(
                        label="Whale External BTC",
                        value=f"{latest_block['whale_total_external_btc']:.2f}"
                    )
                
                with col3:
                    st.metric(
                        label="To Exchange",
                        value=f"{latest_block['to_exchange_btc']:.2f}"
                    )
                
                with col4:
                    st.metric(
                        label="From Exchange",
                        value=f"{latest_block['from_exchange_btc']:.2f}"
                    )
                
                # Block metrics chart
                block_chart = create_block_metrics_chart(block_metrics)
                if block_chart:
                    st.plotly_chart(block_chart, use_container_width=True)
            else:
                st.info("No block metrics data available.")
        
        with tab3:
            # Whale Sentiment
            if not whale_sentiment.empty:
                # Display sentiment gauge
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    sentiment_gauge = create_sentiment_gauge_chart(whale_sentiment)
                    if sentiment_gauge:
                        st.plotly_chart(sentiment_gauge, use_container_width=True)
                
                with col2:
                    # Display sentiment metrics
                    latest_sentiment = whale_sentiment.iloc[-1]
                    
                    st.markdown("### Latest Sentiment Metrics")
                    
                    col2_1, col2_2 = st.columns(2)
                    
                    with col2_1:
                        st.metric(
                            label="Whale Count",
                            value=int(latest_sentiment['whale_count'])
                        )
                        
                        st.metric(
                            label="Shark Count",
                            value=int(latest_sentiment['shark_count'])
                        )
                    
                    with col2_2:
                        st.metric(
                            label="Dolphin Count",
                            value=int(latest_sentiment['dolphin_count'])
                        )
                        
                        st.metric(
                            label="Sentiment Score",
                            value=f"{latest_sentiment['score']:.3f}"
                        )
                    
                    # Component breakdown
                    st.markdown("### Component Breakdown")
                    
                    components = [
                        ("Whale Flow", latest_sentiment['whale_flow_component'], '#FF9500'),
                        ("Exchange Pressure", latest_sentiment['exchange_pressure_component'], '#8B5CF6'),
                        ("Fee Pressure", latest_sentiment['fee_pressure_component'], '#3B82F6'),
                        ("Utilization", latest_sentiment['utilization_component'], '#10B981')
                    ]
                    
                    for name, value, color in components:
                        st.markdown(f"""
                        <div style="margin-bottom: 8px;">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                                <span>{name}</span>
                                <span>{value:.3f}</span>
                            </div>
                            <div style="background-color: #2C2C2C; height: 8px; border-radius: 4px;">
                                <div style="background-color: {color}; height: 100%; width: {50 + value * 50}%; border-radius: 4px;"></div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                
                # Sentiment components chart
                sentiment_components_chart = create_sentiment_components_chart(whale_sentiment)
                if sentiment_components_chart:
                    st.plotly_chart(sentiment_components_chart, use_container_width=True)
            else:
                st.info("No whale sentiment data available.")

    else:
        st.info("🔍 No whale transactions detected in the last 24 hours. The whale monitor may be starting up or the threshold may be too high. Try running: `python scripts/test_whale_monitor.py`")

        # Show helpful info
        with st.expander("ℹ️ How to start whale monitoring"):
            st.markdown("""
            **Quick Test (Recommended First)**
            bash python scripts/test_whale_monitor.py
            This runs with a low threshold (0.01 BTC) to quickly verify the system works.

                        **Production Monitoring**
            bash # Default: 50 BTC threshold python scripts/whale_monitor.py # Custom threshold python scripts/whale_monitor.py --min-btc 10
            **Check if monitor is running**
            bash ps aux | grep whale_monitor
            See [WHALE_MONITOR_README.md](https://github.com/your-repo) for full documentation.
            """)
    st.divider()
    
    # Section 5: Order Book and Depth Chart
    st.subheader("📊 Order Book & Market Depth")
    
    # Get order book data from WebSocket
    orderbook_data = get_orderbook_data()
    
    # Check if we have valid order book data
    has_valid_data = (
        orderbook_data 
        and isinstance(orderbook_data, dict)
        and orderbook_data.get('bids') 
        and orderbook_data.get('asks')
        and len(orderbook_data['bids']) > 0
        and len(orderbook_data['asks']) > 0
    )
    
    if has_valid_data:
        # Display last update time
        last_update = orderbook_data.get('last_update')
        if last_update:
            singapore_tz = pytz.timezone('Asia/Singapore')
            if last_update.tzinfo is None:
                last_update = pytz.UTC.localize(last_update)
            last_update_sgt = last_update.astimezone(singapore_tz)
            st.caption(f"📡 Live Order Book - Last Update: {last_update_sgt.strftime('%Y-%m-%d %H:%M:%S')} SGT")
        
        # Show spread info
        try:
            best_bid = orderbook_data['bids'][0]['price']
            best_ask = orderbook_data['asks'][0]['price']
            spread = best_ask - best_bid
            spread_pct = (spread / best_bid) * 100
            mid_price = (best_bid + best_ask) / 2
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric(label="Best Bid", value=f"${best_bid:,.2f}")
            with col2:
                st.metric(label="Best Ask", value=f"${best_ask:,.2f}")
            with col3:
                st.metric(label="Spread", value=f"${spread:.2f}", delta=f"{spread_pct:.3f}%")
            with col4:
                st.metric(label="Mid Price", value=f"${mid_price:,.2f}")
        except (KeyError, IndexError, TypeError) as e:
            print(f"Error calculating spread: {e}")
            mid_price = None
        
        # Depth Chart - pass current price for vertical line indicator
        depth_chart = create_depth_chart(orderbook_data, current_price=mid_price)
        if depth_chart:
            st.plotly_chart(depth_chart, use_container_width=True)
        else:
            st.warning("⚠️ Unable to render depth chart. Data may be incomplete.")
        
        # Order Book Table (top 20 levels each side)
        st.markdown("### 📖 Order Book")
        
        orderbook_tables = create_orderbook_table(orderbook_data)
        if orderbook_tables:
            bids_df, asks_df = orderbook_tables
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 🟢 Bids (Buy Orders)")
                if not bids_df.empty:
                    # Format the dataframe for display
                    display_bids = bids_df.copy()
                    display_bids['price'] = display_bids['price'].apply(lambda x: f"${x:,.2f}")
                    display_bids['quantity'] = display_bids['quantity'].apply(lambda x: f"{x:.4f}")
                    display_bids['total'] = display_bids['total'].apply(lambda x: f"{x:.4f}")
                    display_bids.columns = ['Price', 'Quantity (BTC)', 'Total (BTC)']
                    
                    st.dataframe(
                        display_bids,
                        hide_index=True,
                        use_container_width=True,
                        height=400
                    )
                else:
                    st.info("No bid data available")
            
            with col2:
                st.markdown("#### 🔴 Asks (Sell Orders)")
                if not asks_df.empty:
                    # Format the dataframe for display
                    display_asks = asks_df.copy()
                    display_asks['price'] = display_asks['price'].apply(lambda x: f"${x:,.2f}")
                    display_asks['quantity'] = display_asks['quantity'].apply(lambda x: f"{x:.4f}")
                    display_asks['total'] = display_asks['total'].apply(lambda x: f"{x:.4f}")
                    display_asks.columns = ['Price', 'Quantity (BTC)', 'Total (BTC)']
                    
                    st.dataframe(
                        display_asks,
                        hide_index=True,
                        use_container_width=True,
                        height=400
                    )
                else:
                    st.info("No ask data available")
        else:
            st.warning("⚠️ Unable to display order book table. Please wait for data to load.")
    else:
        # Show loading state with better UI
        st.info("🔄 Connecting to Binance order book stream...")
        
        # Create placeholder for depth chart
        with st.container():
            st.markdown("### Market Depth")
            st.empty()
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.info("📊 Market depth chart will appear once data is loaded...")
        
        # Create placeholders for order book tables
        st.markdown("### 📖 Order Book")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 🟢 Bids (Buy Orders)")
            st.info("Waiting for bid data...")
        with col2:
            st.markdown("#### 🔴 Asks (Sell Orders)")
            st.info("Waiting for ask data...")
        
        st.caption("💡 The order book data will appear once the WebSocket connection is established. This usually takes a few seconds.")

    st.divider()

    # Section 6: LSTM Model Predictions
    st.subheader("🤖 LSTM Price Predictions")

    # Get LSTM predictions
    lstm_predictions = get_lstm_predictions(limit=5)

    if not lstm_predictions.empty:
        # Display prediction metrics in a more visually appealing way
        latest_prediction = lstm_predictions.iloc[-1]
        
        # Calculate percentage changes
        base_price = latest_prediction['base_price']
        predicted_low = latest_prediction['predicted_low']
        predicted_high = latest_prediction['predicted_high']
        predicted_mean = latest_prediction['predicted_mean']
        predicted_std = latest_prediction['predicted_std']
        
        low_change_pct = ((predicted_low - base_price) / base_price) * 100
        high_change_pct = ((predicted_high - base_price) / base_price) * 100
        mean_change_pct = ((predicted_mean - base_price) / base_price) * 100
        
        # Calculate prediction validity period
        prediction_time = latest_prediction['prediction_time']
        prediction_expiry = prediction_time + pd.Timedelta(hours=12)
        current_time = pd.Timestamp.now(tz='Asia/Singapore')
        time_remaining = prediction_expiry - current_time
        
        # Format time remaining
        if time_remaining.total_seconds() > 0:
            hours_remaining = int(time_remaining.total_seconds() // 3600)
            minutes_remaining = int((time_remaining.total_seconds() % 3600) // 60)
            time_remaining_str = f"{hours_remaining}h {minutes_remaining}m"
            validity_color = "#10B981"  # Green if still valid
        else:
            time_remaining_str = "Expired"
            validity_color = "#EF4444"  # Red if expired
        
        # Create a visually appealing metrics display
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Create a card for the predicted range
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #1E1E1E 0%, #2C2C2C 100%); 
                        border-radius: 10px; padding: 15px; margin-bottom: 10px; 
                        border-left: 4px solid #FF9500;">
                <div style="font-size: 0.9rem; color: #888; margin-bottom: 5px;">Predicted Range</div>
                <div style="font-size: 1.2rem; font-weight: bold; color: #FF9500; margin-bottom: 5px;">
                    ${predicted_low:,.2f} - ${predicted_high:,.2f}
                </div>
                <div style="font-size: 0.8rem; color: #AAA;">
                    Range: ${(predicted_high - predicted_low):,.2f} ({((predicted_high - predicted_low) / base_price * 100):.2f}%)
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            # Create a card for the predicted mean
            mean_color = "#10B981" if predicted_mean >= base_price else "#EF4444"
            arrow = "↑" if predicted_mean >= base_price else "↓"
            
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #1E1E1E 0%, #2C2C2C 100%); 
                        border-radius: 10px; padding: 15px; margin-bottom: 10px; 
                        border-left: 4px solid {mean_color};">
                <div style="font-size: 0.9rem; color: #888; margin-bottom: 5px;">Predicted Mean</div>
                <div style="font-size: 1.2rem; font-weight: bold; color: {mean_color}; margin-bottom: 5px;">
                    {arrow} ${predicted_mean:,.2f}
                </div>
                <div style="font-size: 0.8rem; color: #AAA;">
                    Change: {mean_change_pct:+.2f}% from base
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            # Create a card for the standard deviation
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #1E1E1E 0%, #2C2C2C 100%); 
                        border-radius: 10px; padding: 15px; margin-bottom: 10px; 
                        border-left: 4px solid #8B5CF6;">
                <div style="font-size: 0.9rem; color: #888; margin-bottom: 5px;">Prediction Std Dev</div>
                <div style="font-size: 1.2rem; font-weight: bold; color: #8B5CF6; margin-bottom: 5px;">
                    ${predicted_std:.2f}
                </div>
                <div style="font-size: 0.8rem; color: #AAA;">
                    {(predicted_std / base_price * 100):.2f}% of base price
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Add a two-column layout for the confidence gauge and prediction validity
        col1, col2 = st.columns(2)
        
        with col1:
            # Add confidence gauge
            confidence_gauge = create_confidence_gauge(lstm_predictions)
            if confidence_gauge:
                st.plotly_chart(confidence_gauge, use_container_width=True)
        
        with col2:
            # Create a card for prediction validity
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #1E1E1E 0%, #2C2C2C 100%); 
                        border-radius: 10px; padding: 20px; height: 100%; 
                        border-left: 4px solid {validity_color};">
                <div style="font-size: 1.1rem; font-weight: bold; color: white; margin-bottom: 15px;">
                    ⏰ Prediction Validity
                </div>
                <div style="font-size: 1.3rem; font-weight: bold; color: {validity_color}; margin-bottom: 10px;">
                    {time_remaining_str}
                </div>
                <div style="font-size: 0.9rem; color: #AAA; margin-bottom: 10px;">
                    Predicted at: {prediction_time.strftime('%Y-%m-%d %H:%M')} SGT
                </div>
                <div style="font-size: 0.9rem; color: #AAA; margin-bottom: 10px;">
                    Expires at: {prediction_expiry.strftime('%Y-%m-%d %H:%M')} SGT
                </div>
                <div style="font-size: 0.8rem; color: #888; margin-top: 15px; padding-top: 10px; border-top: 1px solid #444;">
                    Predictions are valid for 12 hours from the prediction time
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Display additional info in an expander
        with st.expander("Prediction Details"):
            st.markdown(f"""
            - **Base Price**: ${base_price:,.2f}
            - **Prediction Time**: {latest_prediction['prediction_time'].strftime('%Y-%m-%d %H:%M:%S')} SGT
            - **Model Run ID**: {latest_prediction['run_id']}
            - **Created At**: {latest_prediction['created_at'].strftime('%Y-%m-%d %H:%M:%S')} SGT
            - **Prediction Valid Until**: {prediction_expiry.strftime('%Y-%m-%d %H:%M:%S')} SGT
            """)
    else:
        st.info("🔄 No LSTM predictions available. Make sure the prediction model is running and saving results to the database.")
        
        # Show helpful info
        with st.expander("ℹ️ How to start LSTM predictions"):
            st.markdown("""
            **Have you run the training DAG?**
                        
            **Have you run the predictions DAG?**
            
            See the model documentation for more details.
            """)

    # Footer
    st.divider()
    st.caption("Data sources: Binance WebSocket (real-time prices & order book), NewsAPI/CryptoCompare/Reddit (news), Alternative.me (Fear & Greed), Mempool.space (whale txs)")
    st.caption("This dashboard is for educational purposes only. Not financial advice.")
    
    # Auto-refresh every 1 second for real-time price updates
    # WebSocket runs in background thread and updates session state
    time.sleep(2)
    st.rerun()


if __name__ == "__main__":
    main()