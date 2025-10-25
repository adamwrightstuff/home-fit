"""
Geographic Coverage Test Suite
Tests HomeFit scoring across all 50 states with representative addresses
"""

import pytest
import requests
import time
import json
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class TestLocation:
    """Test location with expected characteristics."""
    address: str
    city: str
    state: str
    expected_area_type: str  # urban_core, suburban, exurban, rural
    expected_metro: str = None
    expected_score_range: Tuple[int, int] = (0, 100)
    expected_confidence_min: int = 50


# Representative test locations across all 50 states
TEST_LOCATIONS = [
    # Major Urban Cores
    TestLocation("1600 Pennsylvania Avenue NW, Washington, DC", "Washington", "DC", "urban_core", "Washington", (60, 90), 80),
    TestLocation("350 5th Ave, New York, NY", "New York", "NY", "urban_core", "New York", (50, 85), 85),
    TestLocation("1 Hacker Way, Menlo Park, CA", "Menlo Park", "CA", "suburban", "San Francisco", (70, 95), 85),
    TestLocation("1600 Amphitheatre Pkwy, Mountain View, CA", "Mountain View", "CA", "suburban", "San Francisco", (75, 95), 85),
    TestLocation("1 Microsoft Way, Redmond, WA", "Redmond", "WA", "suburban", "Seattle", (70, 90), 80),
    TestLocation("1 Apple Park Way, Cupertino, CA", "Cupertino", "CA", "suburban", "San Francisco", (75, 95), 85),
    
    # State Capitals (Urban/Suburban)
    TestLocation("1 Capitol Square, Columbus, OH", "Columbus", "OH", "urban_core", "Columbus", (60, 85), 75),
    TestLocation("100 N Carson St, Carson City, NV", "Carson City", "NV", "exurban", None, (40, 70), 60),
    TestLocation("1 Capitol Ave, Augusta, ME", "Augusta", "ME", "exurban", None, (35, 65), 55),
    TestLocation("600 E Boulevard Ave, Bismarck, ND", "Bismarck", "ND", "exurban", None, (30, 60), 50),
    
    # Suburban Areas
    TestLocation("123 Main St, Plano, TX", "Plano", "TX", "suburban", "Dallas", (65, 85), 75),
    TestLocation("456 Oak Ave, Naperville, IL", "Naperville", "IL", "suburban", "Chicago", (70, 90), 80),
    TestLocation("789 Pine St, Bellevue, WA", "Bellevue", "WA", "suburban", "Seattle", (70, 90), 80),
    TestLocation("321 Elm St, Scottsdale, AZ", "Scottsdale", "AZ", "suburban", "Phoenix", (65, 85), 75),
    
    # Rural Areas
    TestLocation("123 County Road 45, Cody, WY", "Cody", "WY", "rural", None, (20, 50), 40),
    TestLocation("456 Farm Road 12, Pierre, SD", "Pierre", "SD", "rural", None, (25, 55), 45),
    TestLocation("789 Rural Route 3, Montpelier, VT", "Montpelier", "VT", "rural", None, (30, 60), 50),
    TestLocation("321 Back Road, Juneau, AK", "Juneau", "AK", "rural", None, (15, 45), 35),
    
    # Edge Cases
    TestLocation("123 Military Base Rd, Fort Bragg, NC", "Fort Bragg", "NC", "exurban", None, (40, 70), 60),
    TestLocation("456 New Development Blvd, Frisco, TX", "Frisco", "TX", "suburban", "Dallas", (60, 85), 70),
    TestLocation("789 Island Way, Key West, FL", "Key West", "FL", "exurban", None, (35, 65), 55),
    
    # All 50 States Coverage (sampling)
    TestLocation("123 Main St, Birmingham, AL", "Birmingham", "AL", "urban_core", "Birmingham", (50, 80), 70),
    TestLocation("456 Oak St, Anchorage, AK", "Anchorage", "AK", "urban_core", "Anchorage", (45, 75), 65),
    TestLocation("789 Pine St, Phoenix, AZ", "Phoenix", "AZ", "urban_core", "Phoenix", (55, 85), 75),
    TestLocation("321 Elm St, Little Rock, AR", "Little Rock", "AR", "urban_core", "Little Rock", (45, 75), 65),
    TestLocation("654 Maple St, Sacramento, CA", "Sacramento", "CA", "urban_core", "Sacramento", (60, 85), 75),
    TestLocation("987 Cedar St, Denver, CO", "Denver", "CO", "urban_core", "Denver", (65, 90), 80),
    TestLocation("147 Birch St, Hartford, CT", "Hartford", "CT", "urban_core", "Hartford", (55, 80), 70),
    TestLocation("258 Spruce St, Dover, DE", "Dover", "DE", "exurban", None, (40, 70), 60),
    TestLocation("369 Willow St, Tallahassee, FL", "Tallahassee", "FL", "exurban", None, (45, 75), 65),
    TestLocation("741 Poplar St, Atlanta, GA", "Atlanta", "GA", "urban_core", "Atlanta", (60, 85), 75),
    TestLocation("852 Hickory St, Honolulu, HI", "Honolulu", "HI", "urban_core", "Honolulu", (50, 80), 70),
    TestLocation("963 Sycamore St, Boise, ID", "Boise", "ID", "urban_core", "Boise", (55, 80), 70),
    TestLocation("159 Ash St, Springfield, IL", "Springfield", "IL", "exurban", None, (40, 70), 60),
    TestLocation("357 Dogwood St, Indianapolis, IN", "Indianapolis", "IN", "urban_core", "Indianapolis", (55, 80), 70),
    TestLocation("468 Redwood St, Des Moines, IA", "Des Moines", "IA", "urban_core", "Des Moines", (50, 80), 70),
    TestLocation("579 Sequoia St, Topeka, KS", "Topeka", "KS", "exurban", None, (35, 65), 55),
    TestLocation("680 Magnolia St, Frankfort, KY", "Frankfort", "KY", "exurban", None, (35, 65), 55),
    TestLocation("791 Cypress St, Baton Rouge, LA", "Baton Rouge", "LA", "urban_core", "Baton Rouge", (45, 75), 65),
    TestLocation("802 Hemlock St, Augusta, ME", "Augusta", "ME", "exurban", None, (30, 60), 50),
    TestLocation("913 Fir St, Annapolis, MD", "Annapolis", "MD", "suburban", "Baltimore", (60, 85), 75),
    TestLocation("024 Pine St, Boston, MA", "Boston", "MA", "urban_core", "Boston", (65, 90), 80),
    TestLocation("135 Oak St, Lansing, MI", "Lansing", "MI", "exurban", None, (40, 70), 60),
    TestLocation("246 Maple St, St. Paul, MN", "St. Paul", "MN", "urban_core", "Minneapolis", (60, 85), 75),
    TestLocation("357 Elm St, Jackson, MS", "Jackson", "MS", "urban_core", "Jackson", (40, 70), 60),
    TestLocation("468 Birch St, Jefferson City, MO", "Jefferson City", "MO", "exurban", None, (35, 65), 55),
    TestLocation("579 Cedar St, Helena, MT", "Helena", "MT", "rural", None, (25, 55), 45),
    TestLocation("680 Willow St, Lincoln, NE", "Lincoln", "NE", "urban_core", "Lincoln", (45, 75), 65),
    TestLocation("791 Poplar St, Carson City, NV", "Carson City", "NV", "exurban", None, (30, 60), 50),
    TestLocation("802 Hickory St, Concord, NH", "Concord", "NH", "exurban", None, (35, 65), 55),
    TestLocation("913 Sycamore St, Trenton, NJ", "Trenton", "NJ", "suburban", "Philadelphia", (55, 80), 70),
    TestLocation("024 Ash St, Santa Fe, NM", "Santa Fe", "NM", "exurban", None, (40, 70), 60),
    TestLocation("135 Dogwood St, Albany, NY", "Albany", "NY", "urban_core", "Albany", (50, 80), 70),
    TestLocation("246 Redwood St, Raleigh, NC", "Raleigh", "NC", "urban_core", "Raleigh", (55, 80), 70),
    TestLocation("357 Sequoia St, Bismarck, ND", "Bismarck", "ND", "exurban", None, (25, 55), 45),
    TestLocation("468 Magnolia St, Columbus, OH", "Columbus", "OH", "urban_core", "Columbus", (55, 80), 70),
    TestLocation("579 Cypress St, Oklahoma City, OK", "Oklahoma City", "OK", "urban_core", "Oklahoma City", (50, 80), 70),
    TestLocation("680 Hemlock St, Salem, OR", "Salem", "OR", "urban_core", "Salem", (50, 80), 70),
    TestLocation("791 Fir St, Harrisburg, PA", "Harrisburg", "PA", "exurban", None, (40, 70), 60),
    TestLocation("802 Pine St, Providence, RI", "Providence", "RI", "urban_core", "Providence", (50, 80), 70),
    TestLocation("913 Oak St, Columbia, SC", "Columbia", "SC", "urban_core", "Columbia", (45, 75), 65),
    TestLocation("024 Maple St, Pierre, SD", "Pierre", "SD", "rural", None, (20, 50), 40),
    TestLocation("135 Elm St, Nashville, TN", "Nashville", "TN", "urban_core", "Nashville", (55, 80), 70),
    TestLocation("246 Birch St, Austin, TX", "Austin", "TX", "urban_core", "Austin", (60, 85), 75),
    TestLocation("357 Cedar St, Salt Lake City, UT", "Salt Lake City", "UT", "urban_core", "Salt Lake City", (55, 80), 70),
    TestLocation("468 Willow St, Montpelier, VT", "Montpelier", "VT", "rural", None, (25, 55), 45),
    TestLocation("579 Poplar St, Richmond, VA", "Richmond", "VA", "urban_core", "Richmond", (50, 80), 70),
    TestLocation("680 Hickory St, Olympia, WA", "Olympia", "WA", "exurban", None, (40, 70), 60),
    TestLocation("791 Sycamore St, Charleston, WV", "Charleston", "WV", "exurban", None, (35, 65), 55),
    TestLocation("802 Ash St, Madison, WI", "Madison", "WI", "urban_core", "Madison", (55, 80), 70),
    TestLocation("913 Dogwood St, Cheyenne, WY", "Cheyenne", "WY", "exurban", None, (30, 60), 50),
]


class TestGeographicCoverage:
    """Test suite for geographic coverage across all 50 states."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = []
    
    def test_single_location(self, location: TestLocation) -> Dict:
        """Test a single location and return results."""
        print(f"\n🧪 Testing: {location.address}")
        
        try:
            # Make API request
            response = requests.get(
                f"{self.base_url}/score",
                params={"location": location.address},
                timeout=30
            )
            
            if response.status_code != 200:
                return {
                    "location": location.address,
                    "status": "error",
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "expected_area_type": location.expected_area_type,
                    "expected_score_range": location.expected_score_range
                }
            
            data = response.json()
            
            # Extract key metrics
            total_score = data.get("total_score", 0)
            overall_confidence = data.get("overall_confidence", {})
            data_quality_summary = data.get("data_quality_summary", {})
            
            # Check area classification
            area_classification = data_quality_summary.get("area_classification", {})
            detected_area_type = area_classification.get("type", "unknown")
            
            # Check if area type matches expectation
            area_type_match = detected_area_type == location.expected_area_type
            
            # Check score range
            score_in_range = location.expected_score_range[0] <= total_score <= location.expected_score_range[1]
            
            # Check confidence
            avg_confidence = overall_confidence.get("average_confidence", 0)
            confidence_adequate = avg_confidence >= location.expected_confidence_min
            
            # Check for fallback usage
            fallback_percentage = overall_confidence.get("fallback_percentage", 0)
            using_fallback = fallback_percentage > 0
            
            result = {
                "location": location.address,
                "status": "success",
                "total_score": total_score,
                "area_type_detected": detected_area_type,
                "area_type_expected": location.expected_area_type,
                "area_type_match": area_type_match,
                "score_in_range": score_in_range,
                "confidence": avg_confidence,
                "confidence_adequate": confidence_adequate,
                "fallback_used": using_fallback,
                "fallback_percentage": fallback_percentage,
                "data_sources": data_quality_summary.get("data_sources_used", []),
                "metro_detected": area_classification.get("metro_name"),
                "expected_metro": location.expected_metro,
                "metro_match": area_classification.get("metro_name") == location.expected_metro if location.expected_metro else True,
                "response_time": response.elapsed.total_seconds()
            }
            
            print(f"   ✅ Score: {total_score}/100")
            print(f"   📍 Area: {detected_area_type} (expected: {location.expected_area_type})")
            print(f"   📊 Confidence: {avg_confidence}%")
            print(f"   ⚡ Response time: {response.elapsed.total_seconds():.2f}s")
            
            return result
            
        except requests.exceptions.Timeout:
            return {
                "location": location.address,
                "status": "timeout",
                "error": "Request timed out",
                "expected_area_type": location.expected_area_type
            }
        except Exception as e:
            return {
                "location": location.address,
                "status": "error",
                "error": str(e),
                "expected_area_type": location.expected_area_type
            }
    
    def run_all_tests(self) -> Dict:
        """Run all geographic coverage tests."""
        print("🚀 Starting Geographic Coverage Test Suite")
        print(f"📊 Testing {len(TEST_LOCATIONS)} locations across all 50 states")
        
        start_time = time.time()
        results = []
        
        for i, location in enumerate(TEST_LOCATIONS, 1):
            print(f"\n[{i}/{len(TEST_LOCATIONS)}] Testing {location.state}")
            result = self.test_single_location(location)
            results.append(result)
            
            # Small delay to avoid overwhelming the API
            time.sleep(0.5)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Analyze results
        analysis = self._analyze_results(results, total_time)
        
        return {
            "test_summary": {
                "total_tests": len(TEST_LOCATIONS),
                "successful_tests": len([r for r in results if r["status"] == "success"]),
                "failed_tests": len([r for r in results if r["status"] == "error"]),
                "timeout_tests": len([r for r in results if r["status"] == "timeout"]),
                "total_time_seconds": round(total_time, 2)
            },
            "results": results,
            "analysis": analysis
        }
    
    def _analyze_results(self, results: List[Dict], total_time: float) -> Dict:
        """Analyze test results and provide insights."""
        successful_results = [r for r in results if r["status"] == "success"]
        
        if not successful_results:
            return {"error": "No successful tests to analyze"}
        
        # Area type accuracy
        area_type_matches = [r["area_type_match"] for r in successful_results]
        area_type_accuracy = sum(area_type_matches) / len(area_type_matches) * 100
        
        # Score range accuracy
        score_in_range = [r["score_in_range"] for r in successful_results]
        score_accuracy = sum(score_in_range) / len(score_in_range) * 100
        
        # Confidence analysis
        confidences = [r["confidence"] for r in successful_results]
        avg_confidence = sum(confidences) / len(confidences)
        min_confidence = min(confidences)
        max_confidence = max(confidences)
        
        # Fallback usage
        fallback_usage = [r["fallback_used"] for r in successful_results]
        fallback_percentage = sum(fallback_usage) / len(fallback_usage) * 100
        
        # Response time analysis
        response_times = [r["response_time"] for r in successful_results]
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        
        # State coverage
        states_tested = set()
        for result in successful_results:
            # Extract state from location
            location = result["location"]
            # Simple extraction - could be improved
            if ", " in location:
                parts = location.split(", ")
                if len(parts) >= 2:
                    state = parts[-1].split()[-1]  # Get last word as state
                    states_tested.add(state)
        
        return {
            "area_type_accuracy": round(area_type_accuracy, 1),
            "score_range_accuracy": round(score_accuracy, 1),
            "confidence_metrics": {
                "average": round(avg_confidence, 1),
                "minimum": round(min_confidence, 1),
                "maximum": round(max_confidence, 1)
            },
            "fallback_usage": round(fallback_percentage, 1),
            "performance_metrics": {
                "average_response_time": round(avg_response_time, 2),
                "maximum_response_time": round(max_response_time, 2),
                "total_time": round(total_time, 2)
            },
            "coverage": {
                "states_tested": len(states_tested),
                "states_list": sorted(list(states_tested))
            },
            "success_rate": round(len(successful_results) / len(results) * 100, 1)
        }
    
    def generate_report(self, results: Dict) -> str:
        """Generate a human-readable test report."""
        summary = results["test_summary"]
        analysis = results["analysis"]
        
        report = f"""
🏠 HomeFit Geographic Coverage Test Report
==========================================

📊 Test Summary:
- Total Tests: {summary['total_tests']}
- Successful: {summary['successful_tests']} ({summary['successful_tests']/summary['total_tests']*100:.1f}%)
- Failed: {summary['failed_tests']}
- Timeouts: {summary['timeout_tests']}
- Total Time: {summary['total_time_seconds']}s

🎯 Accuracy Metrics:
- Area Type Detection: {analysis['area_type_accuracy']}%
- Score Range Accuracy: {analysis['score_range_accuracy']}%
- Overall Success Rate: {analysis['success_rate']}%

📈 Quality Metrics:
- Average Confidence: {analysis['confidence_metrics']['average']}%
- Confidence Range: {analysis['confidence_metrics']['minimum']}% - {analysis['confidence_metrics']['maximum']}%
- Fallback Usage: {analysis['fallback_usage']}%

⚡ Performance:
- Average Response Time: {analysis['performance_metrics']['average_response_time']}s
- Maximum Response Time: {analysis['performance_metrics']['maximum_response_time']}s

🗺️ Geographic Coverage:
- States Tested: {analysis['coverage']['states_tested']}/50
- States: {', '.join(analysis['coverage']['states_list'])}

🎯 Recommendations:
"""
        
        # Add recommendations based on results
        if analysis['area_type_accuracy'] < 80:
            report += "- ⚠️  Area type detection needs improvement\n"
        
        if analysis['confidence_metrics']['average'] < 70:
            report += "- ⚠️  Data quality needs improvement\n"
        
        if analysis['fallback_usage'] > 30:
            report += "- ⚠️  High fallback usage indicates data gaps\n"
        
        if analysis['performance_metrics']['average_response_time'] > 5:
            report += "- ⚠️  Response times are slow, consider optimization\n"
        
        if analysis['coverage']['states_tested'] < 50:
            report += "- ⚠️  Incomplete state coverage\n"
        
        if not any([
            analysis['area_type_accuracy'] < 80,
            analysis['confidence_metrics']['average'] < 70,
            analysis['fallback_usage'] > 30,
            analysis['performance_metrics']['average_response_time'] > 5,
            analysis['coverage']['states_tested'] < 50
        ]):
            report += "- ✅ All metrics look good!\n"
        
        return report


def run_coverage_tests(base_url: str = "http://localhost:8000") -> Dict:
    """Run the complete geographic coverage test suite."""
    tester = TestGeographicCoverage(base_url)
    results = tester.run_all_tests()
    
    # Generate and print report
    report = tester.generate_report(results)
    print(report)
    
    # Save results to file
    with open('tests/coverage_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    with open('tests/coverage_test_report.txt', 'w') as f:
        f.write(report)
    
    print(f"\n📁 Results saved to:")
    print(f"   - tests/coverage_test_results.json")
    print(f"   - tests/coverage_test_report.txt")
    
    return results


if __name__ == "__main__":
    # Run tests if executed directly
    results = run_coverage_tests()
    
    # Exit with error code if tests failed
    if results["test_summary"]["failed_tests"] > 0:
        exit(1)
