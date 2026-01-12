"""
X Signal Processor - Analyzes signals and generates tweet variants
Handles engagement scoring, entity extraction, and content transformation
"""

import re
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class XSignalProcessor:
    """Process X channel signals and generate optimized tweets"""
    
    # High-priority keywords for scoring
    HIGH_PRIORITY_TICKERS = [
        'NVDA', 'NVIDIA', 'TSLA', 'TESLA', 'AAPL', 'APPLE', 'META', 'FACEBOOK',
        'AMZN', 'AMAZON', 'GOOGL', 'GOOGLE', 'MSFT', 'MICROSOFT', 'NFLX', 'NETFLIX',
        'BTC', 'BITCOIN', 'ETH', 'ETHEREUM'
    ]
    
    MAJOR_INDICES = ['DOW', 'DOW JONES', 'NASDAQ', 'S&P 500', 'S&P', 'SPX', 'VIX']
    
    DRAMA_KEYWORDS = [
        'BREAKING', 'ALERT', 'URGENT', 'CRISIS', 'ATTACK', 'WAR', 'KILLING',
        'COLLAPSE', 'SOARS', 'PLUNGES', 'RECORD', 'HISTORIC', 'UNPRECEDENTED',
        'SHUTDOWN', 'BANKRUPTCY', 'LAWSUIT', 'SCANDAL'
    ]
    
    IGNORE_KEYWORDS = [
        'dividend', 'conference call', 'earnings date', 'webcast', 'facility expansion'
    ]
    
    GEOPOLITICAL_KEYWORDS = [
        'TRUMP', 'BIDEN', 'KREMLIN', 'RUSSIA', 'CHINA', 'UKRAINE', 'PENTAGON',
        'CONGRESS', 'SENATE', 'FED', 'FEDERAL RESERVE', 'POWELL'
    ]
    
    FINANCIAL_KEYWORDS = [
        'BILLION', 'TRILLION', 'IPO', 'ACQUISITION', 'MERGER', 'BUYOUT',
        'BANKRUPTCY', 'LAWSUIT', 'EARNINGS', 'REVENUE', 'PROFIT'
    ]
    
    def __init__(self, db=None, grok_api=None):
        """Initialize signal processor"""
        self.db = db
        self.grok_api = grok_api  # Optional Grok API for context-aware generation
        
    def classify_signal(self, title: str, message: str) -> str:
        """
        Classify signal type based on title
        Returns: 'uwhale-news-bot', 'x-news-bot', or 'flow-bot'
        """
        title_lower = title.lower()
        
        if 'uwhale' in title_lower or 'uw economic' in title_lower:
            return 'uwhale-news-bot'
        elif 'fsmn' in title_lower or 'elite news' in title_lower:
            return 'x-news-bot'
        elif 'flow' in title_lower or 'contract' in title_lower or 'premium' in message:
            return 'flow-bot'
        
        return 'unknown'
    
    def extract_entities(self, text: str) -> Dict:
        """
        Extract tickers, companies, keywords, and numbers from signal text
        """
        entities = {
            'tickers': [],
            'companies': [],
            'keywords': [],
            'financial_numbers': []
        }
        
        # Extract tickers ($SYMBOL format)
        ticker_pattern = r'\$([A-Z]{1,5})\b'
        entities['tickers'] = list(set(re.findall(ticker_pattern, text)))
        
        # Extract company mentions
        for ticker in self.HIGH_PRIORITY_TICKERS:
            if ticker in text.upper():
                if ticker not in entities['tickers']:
                    entities['tickers'].append(ticker)
        
        # Extract major indices
        for index in self.MAJOR_INDICES:
            if index in text.upper():
                entities['keywords'].append(index)
        
        # Extract drama keywords
        for keyword in self.DRAMA_KEYWORDS:
            if keyword in text.upper():
                entities['keywords'].append(keyword)
        
        # Extract geopolitical keywords
        for keyword in self.GEOPOLITICAL_KEYWORDS:
            if keyword in text.upper():
                entities['keywords'].append(keyword)
        
        # Extract financial keywords
        for keyword in self.FINANCIAL_KEYWORDS:
            if keyword in text.upper():
                entities['keywords'].append(keyword)
        
        # Extract financial numbers (with B/M/K suffixes or percentages)
        number_patterns = [
            r'\$[\d,.]+\s*[BMK](?:illion)?',  # $1.5B, $500M, $100K
            r'[\d,.]+%',  # 5.2%, 0.5%
            r'[\d,.]+\s*(?:points?|pts)',  # 241.73 points
        ]
        
        for pattern in number_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            entities['financial_numbers'].extend(matches)
        
        # Remove duplicates and limit
        entities['tickers'] = list(set(entities['tickers']))[:10]
        entities['keywords'] = list(set(entities['keywords']))[:15]
        entities['financial_numbers'] = list(set(entities['financial_numbers']))[:10]
        
        return entities
    
    def calculate_engagement_score(self, signal_text: str, entities: Dict, 
                                   signal_time: datetime, signal_type: str) -> Dict:
        """
        Calculate multi-factor engagement score (0.0 - 1.0)
        Returns score and breakdown
        """
        score_breakdown = {}
        
        # 1. Ticker Weight (30%)
        ticker_score = self._score_tickers(entities['tickers'])
        score_breakdown['ticker_impact'] = {
            'score': ticker_score,
            'weight': 0.30,
            'contribution': ticker_score * 0.30,
            'details': f"Found {len(entities['tickers'])} tickers"
        }
        
        # 2. Drama/Urgency (25%)
        drama_score = self._score_drama(entities['keywords'], signal_text)
        score_breakdown['drama_urgency'] = {
            'score': drama_score,
            'weight': 0.25,
            'contribution': drama_score * 0.25,
            'details': f"Drama keywords: {len([k for k in entities['keywords'] if k in self.DRAMA_KEYWORDS])}"
        }
        
        # 3. Financial Impact (20%)
        impact_score = self._score_financial_impact(entities['financial_numbers'], signal_text)
        score_breakdown['financial_impact'] = {
            'score': impact_score,
            'weight': 0.20,
            'contribution': impact_score * 0.20,
            'details': f"Major financial numbers: {len(entities['financial_numbers'])}"
        }
        
        # 4. Timeliness (15%)
        time_score = self._score_timeliness(signal_time)
        score_breakdown['timeliness'] = {
            'score': time_score,
            'weight': 0.15,
            'contribution': time_score * 0.15,
            'details': f"Age: {self._get_age_string(signal_time)}"
        }
        
        # 5. Controversy/Relevance (10%)
        controversy_score = self._score_controversy(entities['keywords'], signal_text)
        score_breakdown['controversy'] = {
            'score': controversy_score,
            'weight': 0.10,
            'contribution': controversy_score * 0.10,
            'details': f"Geopolitical/controversial content detected"
        }
        
        # Calculate total score
        total_score = sum(factor['contribution'] for factor in score_breakdown.values())
        
        # Check for ignore keywords (reduce score significantly)
        if self._should_ignore(signal_text):
            total_score *= 0.3  # Reduce by 70%
            score_breakdown['penalty'] = {
                'score': 0.0,
                'weight': 0.0,
                'contribution': 0.0,
                'details': 'Low-priority content detected'
            }
        
        return {
            'total_score': round(total_score, 2),
            'breakdown': score_breakdown,
            'recommendation': self._get_recommendation(total_score)
        }
    
    def _score_tickers(self, tickers: List[str]) -> float:
        """Score based on ticker importance"""
        if not tickers:
            return 0.1
        
        high_priority_count = sum(1 for t in tickers if t in self.HIGH_PRIORITY_TICKERS)
        
        if high_priority_count > 0:
            return min(0.9 + (high_priority_count * 0.05), 1.0)
        elif len(tickers) >= 3:
            return 0.6
        elif len(tickers) >= 1:
            return 0.4
        
        return 0.1
    
    def _score_drama(self, keywords: List[str], text: str) -> float:
        """Score based on drama/urgency indicators"""
        drama_count = sum(1 for k in keywords if k in self.DRAMA_KEYWORDS)
        
        # Check for all caps (indicates urgency)
        all_caps_ratio = len([c for c in text if c.isupper()]) / max(len(text), 1)
        
        base_score = min(drama_count * 0.25, 0.8)
        
        if all_caps_ratio > 0.5:  # More than 50% caps
            base_score += 0.2
        
        # Market close is always high interest
        if 'CLOSE' in text.upper() and any(idx in text.upper() for idx in self.MAJOR_INDICES):
            base_score = max(base_score, 0.7)
        
        return min(base_score, 1.0)
    
    def _score_financial_impact(self, numbers: List[str], text: str) -> float:
        """Score based on financial magnitude"""
        if not numbers:
            return 0.3
        
        # Look for billions/trillions
        if any('B' in n.upper() or 'BILLION' in n.upper() for n in numbers):
            return 0.95
        
        # Look for millions
        if any('M' in n.upper() or 'MILLION' in n.upper() for n in numbers):
            return 0.7
        
        # Major indices mentioned
        if any(idx in text.upper() for idx in self.MAJOR_INDICES):
            return 0.85
        
        return 0.5
    
    def _score_timeliness(self, signal_time: datetime) -> float:
        """Score based on how fresh the signal is"""
        age = datetime.now() - signal_time
        age_minutes = age.total_seconds() / 60
        
        if age_minutes < 2:
            return 1.0
        elif age_minutes < 5:
            return 0.9
        elif age_minutes < 15:
            return 0.7
        elif age_minutes < 60:
            return 0.5
        elif age_minutes < 240:  # 4 hours
            return 0.3
        else:
            return 0.1
    
    def _score_controversy(self, keywords: List[str], text: str) -> float:
        """Score based on controversial/geopolitical content"""
        geo_count = sum(1 for k in keywords if k in self.GEOPOLITICAL_KEYWORDS)
        
        if geo_count >= 3:
            return 0.9
        elif geo_count >= 2:
            return 0.7
        elif geo_count >= 1:
            return 0.5
        
        return 0.3
    
    def _should_ignore(self, text: str) -> bool:
        """Check if signal should be ignored"""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.IGNORE_KEYWORDS)
    
    def _get_age_string(self, signal_time: datetime) -> str:
        """Get human-readable age string"""
        age = datetime.now() - signal_time
        age_seconds = age.total_seconds()
        
        if age_seconds < 60:
            return f"{int(age_seconds)}s ago"
        elif age_seconds < 3600:
            return f"{int(age_seconds / 60)}m ago"
        else:
            return f"{int(age_seconds / 3600)}h ago"
    
    def _get_recommendation(self, score: float) -> str:
        """Get posting recommendation based on score"""
        if score >= 0.9:
            return "POST_IMMEDIATELY"
        elif score >= 0.7:
            return "POST_HIGH_TRAFFIC"
        elif score >= 0.5:
            return "CONSIDER_POSTING"
        elif score >= 0.3:
            return "PROBABLY_SKIP"
        else:
            return "REJECT"
    
    def generate_tweet_variants(self, signal_text: str, entities: Dict, 
                                signal_type: str, score_data: Dict) -> List[Dict]:
        """
        Generate ONE professional, factual, engaging tweet variant using Grok API
        REQUIRES Grok API to be enabled - no fallback templates
        Returns list with single variant dict or raises error if Grok unavailable
        """
        # Grok API is REQUIRED for tweet generation
        if not self.grok_api:
            logger.error("Grok API not initialized - cannot generate tweet")
            raise ValueError("Grok API is required for tweet generation but not initialized")
        
        if not self.grok_api.is_enabled():
            logger.error("Grok API is disabled - cannot generate tweet")
            raise ValueError("Grok API must be enabled for tweet generation. Please configure and enable Grok in the X module settings.")
        
        try:
            logger.info("Using Grok API to search X trends and generate professional tweet")
            grok_result = self.grok_api.generate_context_aware_tweets(
                signal_text, entities, signal_type
            )
            
            if grok_result.get("success") and grok_result.get("variants"):
                # Use Grok-generated variant (should be only 1)
                grok_variant = grok_result["variants"][0]
                variant_text = grok_variant.get("text", "")
                
                if variant_text:
                    # Calculate engagement prediction
                    predicted_engagement = self._predict_engagement(
                        variant_text, score_data['total_score'], 1.0
                    )
                    
                    variant = {
                        'type': 'professional',
                        'text': variant_text,
                        'predicted_engagement': predicted_engagement,
                        'style': 'Professional, factual, engaging',
                        'recommended': True,
                        'context_used': grok_variant.get("context_used", ""),
                        'relevant_facts': grok_variant.get("relevant_facts", []),
                        'recent_context': grok_result.get("recent_context", "")
                    }
                    
                    logger.info(f"Generated professional tweet using Grok with X trends context")
                    return [variant]
                else:
                    logger.error("Grok returned empty tweet text")
                    raise ValueError("Grok API returned empty tweet text")
            else:
                error_msg = grok_result.get("error", "Unknown error")
                logger.error(f"Grok tweet generation failed: {error_msg}")
                raise ValueError(f"Grok API failed to generate tweet: {error_msg}")
                
        except Exception as e:
            logger.error(f"Grok tweet generation error: {e}")
            raise  # Re-raise the exception instead of falling back to templates
    
    def _generate_factual_variant(self, signal_text: str, entities: Dict, signal_type: str) -> str:
        """Generate factual/professional tweet variant"""
        
        if signal_type == 'uwhale-news-bot':
            # Market close format
            if 'DOW' in signal_text and 'NASDAQ' in signal_text and 'CLOSE' in signal_text.upper():
                return self._format_market_close(signal_text)
            
            # Breaking news format
            if any(kw in signal_text.upper() for kw in self.DRAMA_KEYWORDS):
                return self._format_breaking_news(signal_text, entities)
            
            # Company news format
            if entities['tickers']:
                return self._format_company_news(signal_text, entities)
        
        elif signal_type == 'flow-bot':
            return self._format_options_flow(signal_text, entities)
        
        # Default: Clean up and truncate
        cleaned = self._clean_signal_text(signal_text)
        return cleaned[:280]
    
    def _generate_engaging_variant(self, signal_text: str, entities: Dict, signal_type: str) -> str:
        """Generate engaging/emotional tweet variant"""
        
        if 'DOW' in signal_text and 'CLOSE' in signal_text.upper():
            return f"""Markets rally to close out the day 🚀

📊 All major indices up
💰 Strong finish heading into tomorrow
🎯 Momentum building

{self._extract_key_numbers(signal_text)[:100]}"""
        
        # Add emotional hooks
        cleaned = self._clean_signal_text(signal_text)
        
        if any(kw in signal_text.upper() for kw in ['BREAKING', 'ALERT', 'RECORD']):
            return f"🚨 {cleaned[:250]}"
        
        return f"📊 {cleaned[:270]}"
    
    def _generate_interactive_variant(self, signal_text: str, entities: Dict, signal_type: str) -> str:
        """Generate interactive/question tweet variant"""
        
        cleaned = self._clean_signal_text(signal_text)[:200]
        
        # Add relevant question based on content
        if entities['tickers']:
            ticker = entities['tickers'][0]
            return f"{cleaned}\n\nWhat's your price target for ${ticker}? 🎯"
        
        if 'CLOSE' in signal_text.upper():
            return f"{cleaned}\n\nHow did your portfolio perform today? 📊"
        
        return f"{cleaned}\n\nThoughts? 💭"
    
    def _format_market_close(self, text: str) -> str:
        """Format market close tweet"""
        # Extract numbers
        dow_match = re.search(r'DOW.*?([+-]?[\d,.]+).*?([+-]?[\d.]+)%.*?([\d,.]+)', text, re.IGNORECASE)
        nasdaq_match = re.search(r'NASDAQ.*?([+-]?[\d,.]+).*?([+-]?[\d.]+)%.*?([\d,.]+)', text, re.IGNORECASE)
        sp_match = re.search(r'S&P.*?([+-]?[\d,.]+).*?([+-]?[\d.]+)%.*?([\d,.]+)', text, re.IGNORECASE)
        
        tweet = "📈 Market Close\n\n"
        
        if dow_match:
            tweet += f"DOW: {dow_match.group(1)} pts ({dow_match.group(2)}%)\n"
        if nasdaq_match:
            tweet += f"NASDAQ: {nasdaq_match.group(1)} pts ({nasdaq_match.group(2)}%)\n"
        if sp_match:
            tweet += f"S&P 500: {sp_match.group(1)} pts ({sp_match.group(2)}%)\n"
        
        # Determine sentiment
        if all('+' in str(m.group(1)) for m in [dow_match, nasdaq_match, sp_match] if m):
            tweet += "\nGreen across the board 🟢"
        
        return tweet[:280]
    
    def _format_breaking_news(self, text: str, entities: Dict) -> str:
        """Format breaking news tweet"""
        cleaned = self._clean_signal_text(text)
        
        tweet = "🚨 BREAKING\n\n"
        tweet += cleaned[:240]
        
        # Add tickers if present
        if entities['tickers']:
            tickers_str = ' '.join(f"${t}" for t in entities['tickers'][:3])
            if len(tweet) + len(tickers_str) + 5 < 280:
                tweet += f"\n\n{tickers_str}"
        
        return tweet[:280]
    
    def _format_company_news(self, text: str, entities: Dict) -> str:
        """Format company news tweet"""
        cleaned = self._clean_signal_text(text)
        ticker = entities['tickers'][0] if entities['tickers'] else ''
        
        tweet = f"${ticker}: {cleaned[:250]}"
        return tweet[:280]
    
    def _format_options_flow(self, text: str, entities: Dict) -> str:
        """Format options flow tweet"""
        # Extract key details from flow signal
        ticker_match = re.search(r'([A-Z]{1,5})\s+[\d.]+\s*[CP]', text)
        premium_match = re.search(r'Premium:\s*\$([\d,]+)', text)
        volume_match = re.search(r'Volume:\s*([\d,]+)', text)
        
        tweet = "👀 UNUSUAL OPTIONS ACTIVITY\n\n"
        
        if ticker_match:
            ticker = ticker_match.group(1)
            tweet += f"${ticker}"
            
            if 'P' in text and 'Put' in text:
                tweet += " Puts\n"
            elif 'C' in text and 'Call' in text:
                tweet += " Calls\n"
        
        if volume_match:
            tweet += f"• Volume: {volume_match.group(1)} contracts\n"
        
        if premium_match:
            tweet += f"• Premium: ${premium_match.group(1)}\n"
        
        tweet += "\nSomeone's making a big bet 🎯"
        
        return tweet[:280]
    
    def _clean_signal_text(self, text: str) -> str:
        """Clean and format signal text"""
        # Remove timestamps
        cleaned = re.sub(r'\d{1,2}:\d{2}\s*[AP]M\s*-\s*', '', text)
        
        # Remove excessive whitespace
        cleaned = ' '.join(cleaned.split())
        
        # Remove URLs
        cleaned = re.sub(r'http[s]?://\S+', '', cleaned)
        
        return cleaned.strip()
    
    def _extract_key_numbers(self, text: str) -> str:
        """Extract key numbers from text"""
        numbers = re.findall(r'[+-]?[\d,.]+\s*(?:%|points?|pts)?', text)
        return ' | '.join(numbers[:5])
    
    def _predict_engagement(self, tweet_text: str, base_score: float, style_multiplier: float) -> int:
        """Predict engagement for a tweet variant"""
        # Base engagement from score
        base_engagement = int(base_score * 1500)
        
        # Adjust for style
        adjusted = int(base_engagement * style_multiplier)
        
        # Adjust for length (shorter often better)
        length_penalty = len(tweet_text) / 280
        adjusted = int(adjusted * (1.2 - length_penalty * 0.2))
        
        # Adjust for emoji count (2-3 is optimal)
        emoji_count = len([c for c in tweet_text if ord(c) > 127000])
        if 2 <= emoji_count <= 3:
            adjusted = int(adjusted * 1.1)
        
        return max(adjusted, 100)
    
    def get_star_rating(self, score: float) -> str:
        """Convert score to star rating"""
        if score >= 0.9:
            return "⭐⭐⭐⭐⭐"
        elif score >= 0.7:
            return "⭐⭐⭐⭐"
        elif score >= 0.5:
            return "⭐⭐⭐"
        elif score >= 0.3:
            return "⭐⭐"
        else:
            return "⭐"
    
    def analyze_signal(self, signal_id: int, title: str, message: str, 
                      received_at: str) -> Dict:
        """
        Complete signal analysis using ONLY Grok model
        Everything is done by the model in ONE call - no hard-coded logic
        """
        try:
            # Grok API is REQUIRED
            if not self.grok_api:
                raise ValueError("Grok API is required but not initialized")
            
            if not self.grok_api.is_enabled():
                raise ValueError("Grok API must be enabled for signal analysis")
            
            logger.info(f"Analyzing signal {signal_id} using Grok model (all logic via AI)")
            
            # Call Grok to do EVERYTHING: classify, extract, score, generate tweet
            grok_result = self.grok_api.analyze_signal_complete(
                signal_text=message,
                signal_title=title,
                signal_time=received_at
            )
            
            if not grok_result.get("success"):
                error_msg = grok_result.get("error", "Grok analysis failed")
                logger.error(f"Grok analysis failed for signal {signal_id}: {error_msg}")
                return {
                    'signal_id': signal_id,
                    'error': error_msg,
                    'score': 0.0,
                    'recommendation': 'ERROR'
                }
            
            # Parse Grok's comprehensive analysis
            grok_analysis = grok_result["analysis"]
            
            # Extract components from Grok's response
            classification = grok_analysis.get("classification", {})
            entities = grok_analysis.get("entities", {})
            analysis_data = grok_analysis.get("analysis", {})  # Changed from x_search_results
            score_data = grok_analysis.get("engagement_score", {})
            tweet_data = grok_analysis.get("tweet", {})
            
            # Build variant from Grok's tweet
            variant = {
                'type': 'professional',
                'text': tweet_data.get("text", ""),
                'predicted_engagement': tweet_data.get("predicted_engagement", 1000),
                'style': tweet_data.get("style", "Professional, factual, engaging"),
                'recommended': True,
                'relevant_facts': tweet_data.get("relevant_facts_used", []),
                'context_used': tweet_data.get("context_incorporated", ""),  # Changed from x_context_incorporated
                'engagement_reasoning': tweet_data.get("engagement_reasoning", "")
            }
            
            # Compile final analysis
            analysis = {
                'signal_id': signal_id,
                'signal_type': classification.get("signal_type", "unknown"),
                'source_bot': classification.get("source_bot", "unknown"),
                'entities': entities,
                'score': score_data.get("total_score", 0.5),
                'score_breakdown': score_data.get("breakdown", {}),
                'recommendation': grok_analysis.get("recommendation", "CONSIDER_POSTING"),
                'recommendation_reasoning': grok_analysis.get("recommendation_reasoning", ""),
                'star_rating': score_data.get("star_rating", "⭐⭐⭐"),
                'analysis_data': analysis_data,
                'variants': [variant],
                'analyzed_at': datetime.now().isoformat()
            }
            
            logger.info(f"Signal {signal_id} analyzed by Grok. Score: {analysis['score']:.2f}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing signal {signal_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'signal_id': signal_id,
                'error': str(e),
                'score': 0.0,
                'recommendation': 'ERROR'
            }
