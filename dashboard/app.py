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

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard.data_queries import (
    get_latest_price,
    get_price_history,
    get_latest_articles,
    get_sentiment_summary,
    get_fear_greed_index
)

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
</style>
""", unsafe_allow_html=True)


def create_price_chart(df):
    """Create an interactive candlestick chart"""
    if df.empty:
        return None
    
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
        margin=dict(l=50, r=50, t=50, b=50)
    )
    
    fig.update_xaxes(title_text="Time", row=2, col=1)
    fig.update_yaxes(title_text="Price (USD)", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    
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


def main():
    """Main dashboard function"""
    
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
    # Row 1: Latest price metrics
    latest_price = get_latest_price()
    
    if latest_price is not None:
        col1, col2, col3, col4, col5 = st.columns(5)
        
        # Convert prices to selected currency
        current_price = latest_price['close'] * exchange_rate
        high_price = latest_price['high'] * exchange_rate
        low_price = latest_price['low'] * exchange_rate
        open_price = latest_price['open'] * exchange_rate
        volume_btc = latest_price['volume']
        volume_currency = volume_btc * current_price
        
        with col1:
            st.metric(
                label=f"Current Price ({currency})",
                value=f"{currency_symbol}{current_price:,.2f}",
                delta=f"{current_price - open_price:,.2f}"
            )
        
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
                value=latest_price['time'].strftime('%m/%d %H:%M')
            )
    
    st.divider()
    
    # Section 1: Bitcoin Price Chart (Full Width)
    st.subheader("Bitcoin Price Chart")
    price_history = get_price_history(price_interval, price_limit)
    
    if not price_history.empty:
        price_chart = create_price_chart(price_history)
        if price_chart:
            st.plotly_chart(price_chart, use_container_width=True)
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
    
    # Footer
    st.divider()
    st.caption("Data sources: Bitstamp (prices), NewsAPI/CryptoCompare/Reddit (news), Alternative.me (Fear & Greed)")
    st.caption("This dashboard is for educational purposes only. Not financial advice.")
    
    # Auto-refresh every 60 seconds (aligned with continuous_updater.py price updates)
    # Works with or without updater running - shows static data if updater is stopped
    time.sleep(60)
    st.rerun()


if __name__ == "__main__":
    main()

