import unittest
import requests
import json
import time
import os
from dotenv import load_dotenv

# Load environment variables for testing
load_dotenv()

class TestDeploymentAPI(unittest.TestCase):
    """
    Comprehensive test suite for the deployment API.
    Tests the complete deployment pipeline from request to deployed application.
    """
    
    def setUp(self):
        """
        Set up test configuration and sample data.
        """
        self.base_url = 'http://localhost:8000'
        self.test_secret = os.getenv('SECRET_KEY', 'your-secret-here')
        self.test_timeout = 120  # seconds
        
        # Sample test request
        self.sample_request = {
            'email': 'test@example.com',
            'secret': self.test_secret,
            'task': 'test-calculator-001',
            'round': 1,
            'nonce': 'test-nonce-12345',
            'brief': 'Create a simple calculator web application with basic arithmetic operations (add, subtract, multiply, divide). The calculator should have a display area and number buttons.',
            'checks': [
                'Page has calculator display',
                'Page has number buttons',
                'Calculator can perform addition',
                'Calculator shows results'
            ],
            'evaluation_url': 'https://httpbin.org/post',
            'attachments': []
        }
    
    def test_home_endpoint(self):
        """
        Test that the home endpoint returns service information.
        """
        print("\n--- Testing Home Endpoint ---")
        
        response = requests.get(f'{self.base_url}/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('service', data)
        self.assertIn('version', data)
        self.assertIn('status', data)
        self.assertIn('endpoints', data)
        
        print("✓ Home endpoint working correctly")
    
    def test_health_check(self):
        """
        Test the health check endpoint.
        """
        print("\n--- Testing Health Check ---")
        
        response = requests.get(f'{self.base_url}/health')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('status', data)
        self.assertIn('timestamp', data)
        
        print("✓ Health check working correctly")
    
    def test_api_status(self):
        """
        Test the API status endpoint.
        """
        print("\n--- Testing API Status ---")
        
        response = requests.get(f'{self.base_url}/api/status')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('status', data)
        self.assertIn('statistics', data)
        
        print("✓ API status working correctly")
    
    def test_invalid_secret(self):
        """
        Test that invalid secrets are rejected.
        """
        print("\n--- Testing Invalid Secret ---")
        
        invalid_request = self.sample_request.copy()
        invalid_request['secret'] = 'invalid-secret'
        
        response = requests.post(
            f'{self.base_url}/api/deploy',
            json=invalid_request,
            headers={'Content-Type': 'application/json'}
        )
        
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertIn('error', data)
        
        print("✓ Invalid secret properly rejected")
    
    def test_missing_fields(self):
        """
        Test that missing required fields are handled properly.
        """
        print("\n--- Testing Missing Fields ---")
        
        incomplete_request = {
            'email': 'test@example.com',
            'secret': self.test_secret
            # Missing other required fields
        }
        
        response = requests.post(
            f'{self.base_url}/api/deploy',
            json=incomplete_request,
            headers={'Content-Type': 'application/json'}
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)
        self.assertIn('Missing required fields', data['error'])
        
        print("✓ Missing fields properly handled")
    
    def test_invalid_json(self):
        """
        Test that invalid JSON is handled properly.
        """
        print("\n--- Testing Invalid JSON ---")
        
        response = requests.post(
            f'{self.base_url}/api/deploy',
            data='invalid json data',
            headers={'Content-Type': 'application/json'}
        )
        
        self.assertEqual(response.status_code, 400)
        
        print("✓ Invalid JSON properly handled")
    
    def test_full_deployment_flow(self):
        """
        Test the complete deployment flow (this is the main integration test).
        Note: This test requires valid API keys and will create an actual repository.
        """
        print("\n--- Testing Full Deployment Flow ---")
        print("This test will create an actual GitHub repository and deploy to Pages")
        
        # Make deployment request
        print("Sending deployment request...")
        
        response = requests.post(
            f'{self.base_url}/api/deploy',
            json=self.sample_request,
            headers={'Content-Type': 'application/json'},
            timeout=self.test_timeout
        )
        
        print(f"Response status: {response.status_code}")
        
        # Check if deployment was successful
        if response.status_code == 200:
            data = response.json()
            
            # Verify response structure
            self.assertIn('status', data)
            self.assertEqual(data['status'], 'success')
            
            self.assertIn('repo_url', data)
            self.assertIn('pages_url', data) 
            self.assertIn('commit_sha', data)
            
            repo_url = data['repo_url']
            pages_url = data['pages_url']
            
            print(f"✓ Deployment successful!")
            print(f"  Repository: {repo_url}")
            print(f"  Pages URL: {pages_url}")
            
            # Test that repository exists
            print("Verifying repository exists...")
            repo_response = requests.get(repo_url, timeout=10)
            self.assertEqual(repo_response.status_code, 200)
            print("✓ Repository is accessible")
            
            # Test that Pages site becomes available (may take a few minutes)
            print("Checking Pages deployment (this may take a while)...")
            pages_available = False
            max_wait_time = 300  # 5 minutes
            check_interval = 15   # Check every 15 seconds
            
            for attempt in range(max_wait_time // check_interval):
                try:
                    pages_response = requests.get(pages_url, timeout=10)
                    if pages_response.status_code == 200:
                        pages_available = True
                        break
                    else:
                        print(f"Pages not ready yet (status: {pages_response.status_code}), waiting...")
                except requests.exceptions.RequestException:
                    print("Pages not ready yet, waiting...")
                
                time.sleep(check_interval)
            
            if pages_available:
                print("✓ Pages site is accessible")
                
                # Basic content verification
                content = pages_response.text.lower()
                if 'calculator' in content:
                    print("✓ Generated content appears correct")
                else:
                    print("⚠ Generated content may not match brief")
            else:
                print("⚠ Pages site not accessible within timeout (this is normal for new deployments)")
                
        elif response.status_code == 500:
            # Server error - likely an issue with API keys or setup
            data = response.json()
            print(f"✗ Deployment failed with server error: {data.get('error', 'Unknown error')}")
            self.fail(f"Deployment failed: {data.get('error', 'Unknown error')}")
            
        else:
            # Other error
            print(f"✗ Unexpected response status: {response.status_code}")
            print(f"Response: {response.text}")
            self.fail(f"Unexpected response status: {response.status_code}")
    
    def test_dashboard_access(self):
        """
        Test that the dashboard is accessible.
        """
        print("\n--- Testing Dashboard Access ---")
        
        response = requests.get(f'{self.base_url}/dashboard')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers.get('content-type', ''))
        
        print("✓ Dashboard is accessible")

def run_specific_test(test_name):
    """
    Run a specific test by name.
    """
    suite = unittest.TestSuite()
    suite.addTest(TestDeploymentAPI(test_name))
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)

def run_safe_tests():
    """
    Run tests that don't require API keys or create resources.
    """
    safe_tests = [
        'test_home_endpoint',
        'test_health_check', 
        'test_api_status',
        'test_invalid_secret',
        'test_missing_fields',
        'test_invalid_json',
        'test_dashboard_access'
    ]
    
    suite = unittest.TestSuite()
    for test in safe_tests:
        suite.addTest(TestDeploymentAPI(test))
    
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)

if __name__ == '__main__':
    print("LLM Code Deployment API Test Suite")
    print("=" * 50)
    
    # Check if server is running
    try:
        response = requests.get('http://localhost:8000/health', timeout=5)
        if response.status_code != 200:
            print("ERROR: API server is not responding properly")
            print("Please start the server with: python app.py")
            exit(1)
    except requests.exceptions.RequestException:
        print("ERROR: Cannot connect to API server at localhost:8000")
        print("Please start the server with: python app.py")
        exit(1)
    
    print("Server is running, starting tests...\n")
    
    # Ask user which tests to run
    print("Test Options:")
    print("1. Run safe tests only (no API keys needed)")
    print("2. Run full test suite (requires valid API keys)")
    print("3. Run specific test")
    
    choice = input("\nEnter your choice (1-3): ").strip()
    
    if choice == '1':
        print("\nRunning safe tests...")
        run_safe_tests()
    elif choice == '2':
        print("\nRunning full test suite...")
        unittest.main(verbosity=2)
    elif choice == '3':
        test_name = input("Enter test method name (e.g., test_home_endpoint): ").strip()
        if hasattr(TestDeploymentAPI, test_name):
            run_specific_test(test_name)
        else:
            print(f"Test '{test_name}' not found")
    else:
        print("Invalid choice, running safe tests...")
        run_safe_tests()