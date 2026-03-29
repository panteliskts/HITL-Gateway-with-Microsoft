#!/usr/bin/env python3
"""
HITL Gateway Dashboard Backend API Tests
========================================
Tests all backend API endpoints for correct schema and functionality.
"""
import os
import requests
import sys
import json
from datetime import datetime

class HITLAPITester:
    def __init__(self, base_url=None):
        if base_url is None:
            base_url = os.getenv("HITL_TEST_BASE_URL", "http://localhost:8000")
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def run_test(self, name, method, endpoint, expected_status=200, expected_fields=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, headers=headers, timeout=10)

            print(f"   Status: {response.status_code}")
            
            success = response.status_code == expected_status
            if success:
                try:
                    data = response.json()
                    print(f"   Response: {json.dumps(data, indent=2)[:200]}...")
                    
                    # Check expected fields if provided
                    if expected_fields:
                        for field in expected_fields:
                            if field not in data:
                                print(f"   ❌ Missing field: {field}")
                                success = False
                            else:
                                print(f"   ✅ Found field: {field}")
                    
                    if success:
                        self.tests_passed += 1
                        print(f"✅ {name} - PASSED")
                        return True, data
                    else:
                        self.failed_tests.append(f"{name} - Missing required fields")
                        print(f"❌ {name} - FAILED (Missing fields)")
                        return False, data
                        
                except json.JSONDecodeError:
                    print(f"   ❌ Invalid JSON response")
                    self.failed_tests.append(f"{name} - Invalid JSON")
                    print(f"❌ {name} - FAILED (Invalid JSON)")
                    return False, {}
            else:
                self.failed_tests.append(f"{name} - Status {response.status_code} != {expected_status}")
                print(f"❌ {name} - FAILED (Status {response.status_code})")
                return False, {}

        except requests.exceptions.RequestException as e:
            print(f"   ❌ Request error: {str(e)}")
            self.failed_tests.append(f"{name} - Request error: {str(e)}")
            print(f"❌ {name} - FAILED (Request error)")
            return False, {}

    def test_health_endpoint(self):
        """Test /api/health endpoint"""
        expected_fields = ['status', 'timestamp', 'version', 'checks']
        return self.run_test(
            "Health Endpoint",
            "GET",
            "api/health",
            200,
            expected_fields
        )

    def test_stats_endpoint(self):
        """Test /api/stats endpoint"""
        expected_fields = [
            'total_requests', 'pending', 'approved', 'rejected', 'escalated',
            'active_agents', 'approval_rate', 'avg_decision_time_seconds', 'p95_decision_time_seconds'
        ]
        return self.run_test(
            "Stats Endpoint",
            "GET",
            "api/stats",
            200,
            expected_fields
        )

    def test_pending_endpoint(self):
        """Test /api/pending endpoint"""
        expected_fields = ['count', 'requests']
        return self.run_test(
            "Pending Endpoint",
            "GET",
            "api/pending",
            200,
            expected_fields
        )

    def test_audit_endpoint(self):
        """Test /api/audit endpoint"""
        expected_fields = ['count', 'events']
        return self.run_test(
            "Audit Endpoint",
            "GET",
            "api/audit",
            200,
            expected_fields
        )

    def print_summary(self):
        """Print test summary"""
        print(f"\n{'='*60}")
        print(f"📊 TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run)*100:.1f}%")
        
        if self.failed_tests:
            print(f"\n❌ FAILED TESTS:")
            for failure in self.failed_tests:
                print(f"   - {failure}")
        else:
            print(f"\n✅ ALL TESTS PASSED!")
        
        return self.tests_passed == self.tests_run

def main():
    print("🚀 Starting HITL Gateway Backend API Tests")
    print(f"⏰ Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tester = HITLAPITester()
    
    # Run all tests
    print("\n" + "="*60)
    print("🧪 RUNNING API ENDPOINT TESTS")
    print("="*60)
    
    tester.test_health_endpoint()
    tester.test_stats_endpoint()
    tester.test_pending_endpoint()
    tester.test_audit_endpoint()
    
    # Print final summary
    success = tester.print_summary()
    
    print(f"\n⏰ Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())