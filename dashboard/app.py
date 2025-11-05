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
    get_whale_trend
)
from dashboard.binance_ws import start_price_stream, get_realtime_price

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


def main():
    """Main dashboard function"""
    
    # Initialize WebSocket price streamer (runs in background thread)
    if 'ws_initialized' not in st.session_state:
        start_price_stream()
        st.session_state.ws_initialized = True
    
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
            index=2,
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
        col1, col2, col3, col4, col5 = st.columns(5)
        
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
        
        # Determine flash class based on price change
        flash_class = ""
        if abs(price_change) > 0.01:  # Only flash if change is significant (> 0.01)
            if price_change > 0:
                flash_class = "price-flash-green"
                st.session_state.price_change_count += 1
            elif price_change < 0:
                flash_class = "price-flash-red"
                st.session_state.price_change_count += 1
        
        # Update previous price
        st.session_state.prev_price = current_price
        
        with col1:
            # Create custom price display with flash animation on the numbers
            # Use change count to ensure animation retriggers on each change
            change_key = st.session_state.get('price_change_count', 0)
            price_id = f"price-number-{change_key}"
            
            # Match Streamlit metric styling - label at top, value in middle, delta at bottom
            # Use same structure and classes as Streamlit metrics for consistency
            price_html = f"""
            <div style="margin-bottom: 0.5rem;">
                <div style="font-size: 0.875rem; color: rgb(163, 168, 184); margin-bottom: 0.25rem;">
                    Current Price ({currency})
                </div>
                <div class="price-number {flash_class}" id="{price_id}" style="font-size: 2.5rem; font-weight: 600; line-height: 1.2; color: #FFFFFF;">
                    {currency_symbol}{current_price:,.2f}
                </div>
                <div style="font-size: 0.875rem; color: {'#10B981' if current_price >= open_price else '#EF4444'}; margin-top: 0.25rem;">
                    {f"{'+' if current_price >= open_price else ''}{current_price - open_price:,.2f}"}
                </div>
            </div>
            <script>
                // Force animation restart on each price change
                (function() {{
                    var priceEl = document.getElementById('{price_id}');
                    if (priceEl) {{
                        var hasFlash = priceEl.classList.contains('price-flash-green') || 
                                      priceEl.classList.contains('price-flash-red');
                        if (hasFlash) {{
                            // Remove and re-add class to retrigger animation
                            priceEl.style.animation = 'none';
                            setTimeout(function() {{
                                priceEl.style.animation = '';
                            }}, 10);
                        }}
                    }}
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
                value=f"{currency_symbol}{volume_currency:,.0f}",
                delta=f"{volume_btc:.2f} BTC",
                delta_color="off"
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
    st.subheader("🐋 Whale Transaction Alerts")

    # Get whale statistics
    whale_stats = get_whale_stats(period_hours=24)

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

        # Two column layout for chart and transactions
        col_chart, col_txs = st.columns([2, 1])

        with col_chart:
            # Whale trend chart
            whale_trend = get_whale_trend(interval='1 hour', limit=24)
            if not whale_trend.empty:
                whale_chart = create_whale_chart(whale_trend)
                if whale_chart:
                    st.plotly_chart(whale_chart, use_container_width=True)
            else:
                st.info("Building whale trend data... Check back soon.")

        with col_txs:
            st.markdown("**Recent Whale Transactions**")

            # Get recent whales
            whales = get_recent_whale_transactions(limit=8)

            if not whales.empty:
                for _, whale in whales.iterrows():
                    # Format time
                    if pd.notna(whale.get('detected_at')):
                        detected_time = whale['detected_at']
                        time_str = detected_time.strftime('%H:%M')
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

                    # Get addresses
                    primary_input = whale.get('primary_input_address', '')
                    primary_output = whale.get('primary_output_address', '')

                    # Decode address types
                    def get_address_badge(addr):
                        """Get badge for address type"""
                        if not addr or pd.isna(addr):
                            return ""
                        if addr.startswith('1'):
                            return '<span style="background: #6B7280; padding: 1px 4px; border-radius: 3px; font-size: 0.55rem; margin-left: 4px;">Legacy</span>'
                        elif addr.startswith('3'):
                            return '<span style="background: #8B5CF6; padding: 1px 4px; border-radius: 3px; font-size: 0.55rem; margin-left: 4px;">Multisig</span>'
                        elif addr.startswith('bc1q'):
                            return '<span style="background: #10B981; padding: 1px 4px; border-radius: 3px; font-size: 0.55rem; margin-left: 4px;">SegWit</span>'
                        elif addr.startswith('bc1p'):
                            return '<span style="background: #F59E0B; padding: 1px 4px; border-radius: 3px; font-size: 0.55rem; margin-left: 4px;">Taproot</span>'
                        return ""

                    from_badge = get_address_badge(primary_input)
                    to_badge = get_address_badge(primary_output)

                    # Format addresses for display
                    from_addr = f"{primary_input[:10]}...{primary_input[-8:]}" if primary_input and pd.notna(primary_input) else "N/A"
                    to_addr = f"{primary_output[:10]}...{primary_output[-8:]}" if primary_output and pd.notna(primary_output) else "N/A"

                    # Create clickable address links
                    from_addr_link = f"https://mempool.space/address/{primary_input}" if primary_input and pd.notna(primary_input) else "#"
                    to_addr_link = f"https://mempool.space/address/{primary_output}" if primary_output and pd.notna(primary_output) else "#"

                    # Display whale card
                    st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #2C2C2C 0%, #1E1E1E 100%);
                                border-radius: 8px; padding: 12px; margin-bottom: 10px;
                                border-left: 3px solid #FF9500;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <div style="font-size: 0.85rem; font-weight: bold; color: #FF9500;">
                                    {whale['value_btc']:.2f} BTC
                                </div>
                                <div style="font-size: 0.7rem; color: #888;">
                                    ${whale['value_usd']:,.0f}
                                </div>
                            </div>
                            <div style="text-align: right;">
                                <div style="font-size: 0.7rem; color: #888;">
                                    {time_str}
                                </div>
                                <div style="font-size: 0.75rem; color: {status_color};">
                                    {status_icon} {status.title()}
                                </div>
                            </div>
                        </div>
                        <div style="margin-top: 10px; font-size: 0.75rem; color: #FFF;">
                            <div style="margin-bottom: 5px;">
                                📤 From: <a href="{from_addr_link}" target="_blank" style="color: #FFF; text-decoration: none; font-weight: 500;">{from_addr}</a>{from_badge}
                            </div>
                            <div>
                                📥 To: <a href="{to_addr_link}" target="_blank" style="color: #FFF; text-decoration: none; font-weight: 500;">{to_addr}</a>{to_badge}
                            </div>
                        </div>
                        <div style="margin-top: 8px;">
                            <a href="{explorer_url}" target="_blank"
                               style="color: #10B981; text-decoration: none; font-size: 0.7rem;">
                                🔗 {tx_short}
                            </a>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No recent whale transactions")

    else:
        st.info("🔍 No whale transactions detected in the last 24 hours. The whale monitor may be starting up or the threshold may be too high. Try running: `python scripts/test_whale_monitor.py`")

        # Show helpful info
        with st.expander("ℹ️ How to start whale monitoring"):
            st.markdown("""
            **Quick Test (Recommended First)**
            ```bash
            python scripts/test_whale_monitor.py
            ```
            This runs with a low threshold (0.01 BTC) to quickly verify the system works.

            **Production Monitoring**
            ```bash
            # Default: 50 BTC threshold
            python scripts/whale_monitor.py

            # Custom threshold
            python scripts/whale_monitor.py --min-btc 10
            ```

            **Check if monitor is running**
            ```bash
            ps aux | grep whale_monitor
            ```

            See [WHALE_MONITOR_README.md](https://github.com/your-repo) for full documentation.
            """)

    # Footer
    st.divider()
    st.caption("Data sources: Binance WebSocket (real-time prices), NewsAPI/CryptoCompare/Reddit (news), Alternative.me (Fear & Greed), Mempool.space (whale txs)")
    st.caption("This dashboard is for educational purposes only. Not financial advice.")
    
    # Auto-refresh every 1 second for real-time price updates
    # WebSocket runs in background thread and updates session state
    time.sleep(1)
    st.rerun()


if __name__ == "__main__":
    main()

