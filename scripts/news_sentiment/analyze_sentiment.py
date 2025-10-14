"""
Sentiment Analysis Module using FinBERT
FinBERT is a BERT model fine-tuned on financial text for sentiment analysis
This provides the most accurate sentiment for cryptocurrency/financial news
"""

import os
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from typing import List, Dict, Tuple
import numpy as np
from utils.logger import get_logger

log = get_logger("analyze_sentiment.py")

# =====================================================================
# SENTIMENT ANALYZER CLASS
# =====================================================================
class SentimentAnalyzer:
    """
    FinBERT-based sentiment analyzer for financial/crypto news
    Falls back to VADER if FinBERT is unavailable
    """
    
    def __init__(self, model_name: str = "ProsusAI/finbert", use_vader_fallback: bool = True):
        """
        Initialize sentiment analyzer
        
        Args:
            model_name: HuggingFace model name (default: FinBERT)
            use_vader_fallback: Use VADER as fallback if FinBERT fails
        """
        self.model_name = model_name
        self.use_vader_fallback = use_vader_fallback
        self.model = None
        self.tokenizer = None
        self.vader_analyzer = None
        
        self._load_model()
    
    def _load_model(self):
        """Load FinBERT model and tokenizer"""
        try:
            log.info(f"Loading {self.model_name}...")
            
            # Load tokenizer and model
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
            
            # Set to evaluation mode
            self.model.eval()
            
            # Use GPU if available
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.model.to(self.device)
            
            log.info(f"FinBERT loaded successfully on {self.device}")
            
        except Exception as e:
            log.error(f"Failed to load FinBERT: {e}")
            
            if self.use_vader_fallback:
                log.info("Loading VADER as fallback...")
                try:
                    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
                    self.vader_analyzer = SentimentIntensityAnalyzer()
                    log.info("VADER loaded as fallback")
                except Exception as vader_error:
                    log.error(f"Failed to load VADER: {vader_error}")
                    raise
            else:
                raise
    
    def _analyze_with_finbert(self, text: str) -> Tuple[float, str, float]:
        """
        Analyze sentiment using FinBERT
        
        Returns:
            (sentiment_score, sentiment_label, confidence)
            sentiment_score: -1 to +1 (negative to positive)
            sentiment_label: 'positive', 'negative', 'neutral'
            confidence: 0 to 1
        """
        try:
            # Truncate text to model's max length
            max_length = 512
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=max_length,
                padding=True
            ).to(self.device)
            
            # Get predictions
            with torch.no_grad():
                outputs = self.model(**inputs)
                predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
            
            # FinBERT outputs: [negative, neutral, positive]
            probs = predictions[0].cpu().numpy()
            negative_prob, neutral_prob, positive_prob = probs
            
            # Calculate sentiment score (-1 to +1)
            sentiment_score = positive_prob - negative_prob
            
            # Determine label
            max_prob_idx = np.argmax(probs)
            labels = ['negative', 'neutral', 'positive']
            sentiment_label = labels[max_prob_idx]
            
            # Confidence is the maximum probability
            confidence = float(np.max(probs))
            
            return float(sentiment_score), sentiment_label, confidence
            
        except Exception as e:
            log.error(f"FinBERT analysis failed: {e}")
            return 0.0, 'neutral', 0.0
    
    def _analyze_with_vader(self, text: str) -> Tuple[float, str, float]:
        """
        Analyze sentiment using VADER (fallback)
        
        Returns:
            (sentiment_score, sentiment_label, confidence)
        """
        try:
            scores = self.vader_analyzer.polarity_scores(text)
            compound = scores['compound']  # -1 to +1
            
            # Determine label based on compound score
            if compound >= 0.05:
                label = 'positive'
            elif compound <= -0.05:
                label = 'negative'
            else:
                label = 'neutral'
            
            # VADER doesn't provide confidence, use absolute compound as proxy
            confidence = abs(compound)
            
            return compound, label, confidence
            
        except Exception as e:
            log.error(f"VADER analysis failed: {e}")
            return 0.0, 'neutral', 0.0
    
    def analyze(self, text: str) -> Dict:
        """
        Analyze sentiment of text
        
        Args:
            text: Text to analyze
            
        Returns:
            Dict with sentiment_score, sentiment_label, confidence, model_used
        """
        if not text or len(text.strip()) == 0:
            return {
                'sentiment_score': 0.0,
                'sentiment_label': 'neutral',
                'confidence': 0.0,
                'model_used': 'none'
            }
        
        # Try FinBERT first
        if self.model is not None:
            score, label, confidence = self._analyze_with_finbert(text)
            model_used = 'finbert'
        # Fallback to VADER
        elif self.vader_analyzer is not None:
            score, label, confidence = self._analyze_with_vader(text)
            model_used = 'vader'
        else:
            return {
                'sentiment_score': 0.0,
                'sentiment_label': 'neutral',
                'confidence': 0.0,
                'model_used': 'none'
            }
        
        return {
            'sentiment_score': score,
            'sentiment_label': label,
            'confidence': confidence,
            'model_used': model_used
        }
    
    def analyze_batch(self, texts: List[str], batch_size: int = 8) -> List[Dict]:
        """
        Analyze sentiment for multiple texts efficiently
        
        Args:
            texts: List of texts to analyze
            batch_size: Batch size for processing
            
        Returns:
            List of sentiment results
        """
        results = []
        
        # Process in batches for efficiency
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            for text in batch:
                result = self.analyze(text)
                results.append(result)
            
            if (i + batch_size) % 50 == 0:
                log.info(f"Analyzed {min(i + batch_size, len(texts))}/{len(texts)} articles")
        
        return results

# =====================================================================
# HELPER FUNCTIONS
# =====================================================================
def analyze_articles(articles: List[Dict], analyzer: SentimentAnalyzer = None) -> List[Dict]:
    """
    Analyze sentiment for a list of articles
    
    Args:
        articles: List of article dicts with 'title' and 'content'
        analyzer: SentimentAnalyzer instance (creates new if None)
        
    Returns:
        List of articles with sentiment added
    """
    if analyzer is None:
        analyzer = SentimentAnalyzer()
    
    log.info(f"Analyzing sentiment for {len(articles)} articles...")
    
    enriched_articles = []
    
    for article in articles:
        # Combine title and content for analysis
        title = article.get('title', '')
        content = article.get('content', '')
        
        # Prioritize content, but use title if content is missing
        text_to_analyze = content if content else title
        
        # Analyze sentiment
        sentiment = analyzer.analyze(text_to_analyze)
        
        # Add sentiment to article
        article_with_sentiment = article.copy()
        article_with_sentiment.update({
            'sentiment_score': sentiment['sentiment_score'],
            'sentiment_label': sentiment['sentiment_label'],
            'confidence': sentiment['confidence'],
            'model_used': sentiment['model_used']
        })
        
        enriched_articles.append(article_with_sentiment)
    
    log.info(f"Sentiment analysis completed for {len(enriched_articles)} articles")
    
    # Log statistics
    positive = sum(1 for a in enriched_articles if a['sentiment_label'] == 'positive')
    negative = sum(1 for a in enriched_articles if a['sentiment_label'] == 'negative')
    neutral = sum(1 for a in enriched_articles if a['sentiment_label'] == 'neutral')
    avg_sentiment = np.mean([a['sentiment_score'] for a in enriched_articles])
    
    log.info(f"Sentiment Distribution: {positive} positive, {negative} negative, {neutral} neutral")
    log.info(f"Average Sentiment Score: {avg_sentiment:.3f}")
    
    return enriched_articles

# =====================================================================
# MAIN FUNCTION FOR TESTING
# =====================================================================
def main():
    """Test the sentiment analyzer"""
    
    # Test texts
    test_articles = [
        {
            'title': 'Bitcoin Surges to New All-Time High',
            'content': 'Bitcoin reached a new all-time high today as institutional investors continue to buy. Market sentiment is extremely bullish.'
        },
        {
            'title': 'Bitcoin Crashes 20% in Flash Crash',
            'content': 'Bitcoin experienced a sudden 20% drop today, causing panic in the market. Many traders are concerned about further losses.'
        },
        {
            'title': 'Bitcoin Price Remains Stable',
            'content': 'Bitcoin price has been trading sideways for the past week, with no significant movements in either direction.'
        }
    ]
    
    # Analyze sentiment
    analyzer = SentimentAnalyzer()
    results = analyze_articles(test_articles, analyzer)
    
    # Display results
    print("\nSentiment Analysis Results:\n")
    for i, article in enumerate(results, 1):
        print(f"{i}. {article['title']}")
        print(f"   Sentiment: {article['sentiment_label'].upper()} (score: {article['sentiment_score']:.3f})")
        print(f"   Confidence: {article['confidence']:.3f} | Model: {article['model_used']}\n")

if __name__ == "__main__":
    main()

