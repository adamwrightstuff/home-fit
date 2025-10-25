"""
Telemetry and Analytics System
Tracks score distributions, data quality, and performance metrics by region
"""

import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict


@dataclass
class RequestMetrics:
    """Metrics for a single API request."""
    timestamp: float
    location: str
    lat: float
    lon: float
    area_type: str
    metro_name: Optional[str]
    total_score: float
    confidence: float
    response_time: float
    data_sources_used: List[str]
    fallback_used: bool
    quality_tier: str
    pillar_scores: Dict[str, float]
    pillar_confidences: Dict[str, float]


@dataclass
class RegionalStats:
    """Aggregated statistics for a region."""
    region_name: str
    area_type: str
    request_count: int
    avg_score: float
    avg_confidence: float
    avg_response_time: float
    fallback_rate: float
    quality_tier_distribution: Dict[str, int]
    data_source_usage: Dict[str, int]
    score_distribution: Dict[str, int]  # score ranges
    pillar_performance: Dict[str, Dict[str, float]]


class TelemetryCollector:
    """Collects and analyzes telemetry data for HomeFit."""
    
    def __init__(self, max_requests: int = 10000):
        self.max_requests = max_requests
        self.requests: List[RequestMetrics] = []
        self.lock = threading.Lock()
        self.start_time = time.time()
        
        # Performance counters
        self.total_requests = 0
        self.error_count = 0
        self.timeout_count = 0
        
        # Regional tracking
        self.regional_stats: Dict[str, RegionalStats] = {}
    
    def record_request(self, metrics: RequestMetrics) -> None:
        """Record metrics for a single request."""
        with self.lock:
            self.requests.append(metrics)
            self.total_requests += 1
            
            # Maintain max size
            if len(self.requests) > self.max_requests:
                self.requests = self.requests[-self.max_requests:]
            
            # Update regional stats
            self._update_regional_stats(metrics)
    
    def record_error(self, error_type: str, location: str) -> None:
        """Record an error occurrence."""
        with self.lock:
            if error_type == "timeout":
                self.timeout_count += 1
            else:
                self.error_count += 1
    
    def _update_regional_stats(self, metrics: RequestMetrics) -> None:
        """Update regional statistics."""
        region_key = f"{metrics.area_type}_{metrics.metro_name or 'unknown'}"
        
        if region_key not in self.regional_stats:
            self.regional_stats[region_key] = RegionalStats(
                region_name=region_key,
                area_type=metrics.area_type,
                request_count=0,
                avg_score=0.0,
                avg_confidence=0.0,
                avg_response_time=0.0,
                fallback_rate=0.0,
                quality_tier_distribution={},
                data_source_usage={},
                score_distribution={},
                pillar_performance={}
            )
        
        stats = self.regional_stats[region_key]
        stats.request_count += 1
        
        # Update averages (simple moving average)
        alpha = 0.1  # Smoothing factor
        stats.avg_score = (1 - alpha) * stats.avg_score + alpha * metrics.total_score
        stats.avg_confidence = (1 - alpha) * stats.avg_confidence + alpha * metrics.confidence
        stats.avg_response_time = (1 - alpha) * stats.avg_response_time + alpha * metrics.response_time
        
        # Update fallback rate
        if metrics.fallback_used:
            stats.fallback_rate = (stats.fallback_rate * (stats.request_count - 1) + 1) / stats.request_count
        else:
            stats.fallback_rate = (stats.fallback_rate * (stats.request_count - 1)) / stats.request_count
        
        # Update quality tier distribution
        tier = metrics.quality_tier
        stats.quality_tier_distribution[tier] = stats.quality_tier_distribution.get(tier, 0) + 1
        
        # Update data source usage
        for source in metrics.data_sources_used:
            stats.data_source_usage[source] = stats.data_source_usage.get(source, 0) + 1
        
        # Update score distribution
        score_range = self._get_score_range(metrics.total_score)
        stats.score_distribution[score_range] = stats.score_distribution.get(score_range, 0) + 1
        
        # Update pillar performance
        for pillar, score in metrics.pillar_scores.items():
            if pillar not in stats.pillar_performance:
                stats.pillar_performance[pillar] = {
                    "avg_score": 0.0,
                    "avg_confidence": 0.0,
                    "count": 0
                }
            
            pillar_stats = stats.pillar_performance[pillar]
            pillar_stats["count"] += 1
            pillar_stats["avg_score"] = (pillar_stats["avg_score"] * (pillar_stats["count"] - 1) + score) / pillar_stats["count"]
            
            if pillar in metrics.pillar_confidences:
                conf = metrics.pillar_confidences[pillar]
                pillar_stats["avg_confidence"] = (pillar_stats["avg_confidence"] * (pillar_stats["count"] - 1) + conf) / pillar_stats["count"]
    
    def _get_score_range(self, score: float) -> str:
        """Get score range category."""
        if score >= 90:
            return "90-100"
        elif score >= 80:
            return "80-89"
        elif score >= 70:
            return "70-79"
        elif score >= 60:
            return "60-69"
        elif score >= 50:
            return "50-59"
        elif score >= 40:
            return "40-49"
        elif score >= 30:
            return "30-39"
        elif score >= 20:
            return "20-29"
        elif score >= 10:
            return "10-19"
        else:
            return "0-9"
    
    def get_overall_stats(self) -> Dict[str, Any]:
        """Get overall system statistics."""
        with self.lock:
            if not self.requests:
                return {"error": "No data available"}
            
            # Calculate overall metrics
            total_score = sum(r.total_score for r in self.requests)
            total_confidence = sum(r.confidence for r in self.requests)
            total_response_time = sum(r.response_time for r in self.requests)
            
            avg_score = total_score / len(self.requests)
            avg_confidence = total_confidence / len(self.requests)
            avg_response_time = total_response_time / len(self.requests)
            
            # Error rates
            error_rate = (self.error_count / self.total_requests) * 100 if self.total_requests > 0 else 0
            timeout_rate = (self.timeout_count / self.total_requests) * 100 if self.total_requests > 0 else 0
            
            # Fallback usage
            fallback_requests = sum(1 for r in self.requests if r.fallback_used)
            fallback_rate = (fallback_requests / len(self.requests)) * 100
            
            # Area type distribution
            area_types = [r.area_type for r in self.requests]
            area_type_dist = dict(Counter(area_types))
            
            # Quality tier distribution
            quality_tiers = [r.quality_tier for r in self.requests]
            quality_tier_dist = dict(Counter(quality_tiers))
            
            # Data source usage
            all_sources = []
            for r in self.requests:
                all_sources.extend(r.data_sources_used)
            source_dist = dict(Counter(all_sources))
            
            # Score distribution
            scores = [r.total_score for r in self.requests]
            score_ranges = [self._get_score_range(s) for s in scores]
            score_dist = dict(Counter(score_ranges))
            
            # Uptime
            uptime_hours = (time.time() - self.start_time) / 3600
            
            return {
                "system_metrics": {
                    "total_requests": self.total_requests,
                    "uptime_hours": round(uptime_hours, 2),
                    "requests_per_hour": round(self.total_requests / max(uptime_hours, 0.1), 2),
                    "error_rate": round(error_rate, 2),
                    "timeout_rate": round(timeout_rate, 2)
                },
                "performance_metrics": {
                    "average_score": round(avg_score, 2),
                    "average_confidence": round(avg_confidence, 2),
                    "average_response_time": round(avg_response_time, 2),
                    "fallback_rate": round(fallback_rate, 2)
                },
                "distribution_metrics": {
                    "area_types": area_type_dist,
                    "quality_tiers": quality_tier_dist,
                    "data_sources": source_dist,
                    "score_ranges": score_dist
                },
                "regional_stats": {k: asdict(v) for k, v in self.regional_stats.items()}
            }
    
    def get_regional_analysis(self, area_type: Optional[str] = None, metro_name: Optional[str] = None) -> Dict[str, Any]:
        """Get analysis for specific regions."""
        with self.lock:
            filtered_requests = self.requests
            
            if area_type:
                filtered_requests = [r for r in filtered_requests if r.area_type == area_type]
            
            if metro_name:
                filtered_requests = [r for r in filtered_requests if r.metro_name == metro_name]
            
            if not filtered_requests:
                return {"error": "No data for specified region"}
            
            # Calculate regional metrics
            scores = [r.total_score for r in filtered_requests]
            confidences = [r.confidence for r in filtered_requests]
            response_times = [r.response_time for r in filtered_requests]
            
            # Statistical analysis
            import statistics
            
            return {
                "region_filter": {
                    "area_type": area_type,
                    "metro_name": metro_name
                },
                "sample_size": len(filtered_requests),
                "score_analysis": {
                    "mean": round(statistics.mean(scores), 2),
                    "median": round(statistics.median(scores), 2),
                    "std_dev": round(statistics.stdev(scores) if len(scores) > 1 else 0, 2),
                    "min": round(min(scores), 2),
                    "max": round(max(scores), 2)
                },
                "confidence_analysis": {
                    "mean": round(statistics.mean(confidences), 2),
                    "median": round(statistics.median(confidences), 2),
                    "std_dev": round(statistics.stdev(confidences) if len(confidences) > 1 else 0, 2)
                },
                "performance_analysis": {
                    "mean_response_time": round(statistics.mean(response_times), 2),
                    "median_response_time": round(statistics.median(response_times), 2),
                    "max_response_time": round(max(response_times), 2)
                },
                "data_quality_issues": self._identify_data_quality_issues(filtered_requests)
            }
    
    def _identify_data_quality_issues(self, requests: List[RequestMetrics]) -> List[Dict[str, Any]]:
        """Identify potential data quality issues."""
        issues = []
        
        # Low confidence areas
        low_confidence = [r for r in requests if r.confidence < 50]
        if low_confidence:
            issues.append({
                "type": "low_confidence",
                "count": len(low_confidence),
                "percentage": round(len(low_confidence) / len(requests) * 100, 1),
                "description": "Areas with confidence < 50%"
            })
        
        # High fallback usage
        high_fallback = [r for r in requests if r.fallback_used]
        if high_fallback:
            issues.append({
                "type": "high_fallback_usage",
                "count": len(high_fallback),
                "percentage": round(len(high_fallback) / len(requests) * 100, 1),
                "description": "Areas using fallback scoring"
            })
        
        # Poor quality tiers
        poor_quality = [r for r in requests if r.quality_tier in ['poor', 'very_poor']]
        if poor_quality:
            issues.append({
                "type": "poor_data_quality",
                "count": len(poor_quality),
                "percentage": round(len(poor_quality) / len(requests) * 100, 1),
                "description": "Areas with poor or very poor data quality"
            })
        
        return issues
    
    def export_data(self, filename: str = None) -> str:
        """Export telemetry data to JSON file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"telemetry_export_{timestamp}.json"
        
        with self.lock:
            export_data = {
                "export_timestamp": datetime.now().isoformat(),
                "overall_stats": self.get_overall_stats(),
                "raw_requests": [asdict(r) for r in self.requests[-1000:]]  # Last 1000 requests
            }
        
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        return filename
    
    def clear_old_data(self, days_to_keep: int = 30) -> int:
        """Clear data older than specified days."""
        cutoff_time = time.time() - (days_to_keep * 24 * 3600)
        
        with self.lock:
            old_count = len(self.requests)
            self.requests = [r for r in self.requests if r.timestamp > cutoff_time]
            new_count = len(self.requests)
            cleared_count = old_count - new_count
        
        return cleared_count


# Global telemetry collector instance
telemetry_collector = TelemetryCollector()


def record_request_metrics(location: str, lat: float, lon: float, 
                          response_data: Dict, response_time: float) -> None:
    """Record metrics for a successful API request."""
    try:
        # Extract metrics from response
        total_score = response_data.get("total_score", 0)
        overall_confidence = response_data.get("overall_confidence", {})
        data_quality_summary = response_data.get("data_quality_summary", {})
        
        # Extract area classification
        area_classification = data_quality_summary.get("area_classification", {})
        area_type = area_classification.get("type", "unknown")
        metro_name = area_classification.get("metro_name")
        
        # Extract pillar scores and confidences
        pillars = response_data.get("livability_pillars", {})
        pillar_scores = {}
        pillar_confidences = {}
        
        for pillar_name, pillar_data in pillars.items():
            pillar_scores[pillar_name] = pillar_data.get("score", 0)
            pillar_confidences[pillar_name] = pillar_data.get("confidence", 0)
        
        # Create metrics object
        metrics = RequestMetrics(
            timestamp=time.time(),
            location=location,
            lat=lat,
            lon=lon,
            area_type=area_type,
            metro_name=metro_name,
            total_score=total_score,
            confidence=overall_confidence.get("average_confidence", 0),
            response_time=response_time,
            data_sources_used=data_quality_summary.get("data_sources_used", []),
            fallback_used=overall_confidence.get("fallback_percentage", 0) > 0,
            quality_tier=overall_confidence.get("quality_tier_distribution", {}).get("excellent", 0) > 0 and "excellent" or "good",
            pillar_scores=pillar_scores,
            pillar_confidences=pillar_confidences
        )
        
        # Record metrics
        telemetry_collector.record_request(metrics)
        
    except Exception as e:
        print(f"⚠️  Failed to record telemetry: {e}")


def record_error(error_type: str, location: str) -> None:
    """Record an error occurrence."""
    telemetry_collector.record_error(error_type, location)


def get_telemetry_stats() -> Dict[str, Any]:
    """Get current telemetry statistics."""
    return telemetry_collector.get_overall_stats()


def get_regional_analysis(area_type: str = None, metro_name: str = None) -> Dict[str, Any]:
    """Get regional analysis."""
    return telemetry_collector.get_regional_analysis(area_type, metro_name)


def export_telemetry_data(filename: str = None) -> str:
    """Export telemetry data."""
    return telemetry_collector.export_data(filename)
