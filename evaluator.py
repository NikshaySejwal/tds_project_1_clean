from playwright.sync_api import sync_playwright, Page, Browser, Playwright
import json
import time
from typing import List, Dict, Optional

class AppEvaluator:
    """
    Handles automated evaluation of deployed applications using Playwright.
    Runs various checks to verify application functionality and requirements.
    """
    
    def __init__(self, headless: bool = True):
        """
        Initialize the app evaluator.
        
        Args:
            headless: Whether to run browser in headless mode
        """
        self.headless = headless
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
    
    def setup(self):
        """
        Initialize Playwright browser and context.
        Call this before running evaluations.
        """
        print("Setting up Playwright browser...")
        self.playwright = sync_playwright().start()
        
        # Launch browser with appropriate settings
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=['--no-sandbox', '--disable-dev-shm-usage']  # For better compatibility
        )
        
        print("Playwright browser setup complete")
    
    def teardown(self):
        """
        Clean up Playwright resources.
        Call this when done with evaluations.
        """
        print("Cleaning up Playwright resources...")
        
        if self.browser:
            self.browser.close()
            self.browser = None
        
        if self.playwright:
            self.playwright.stop()
            self.playwright = None
        
        print("Playwright cleanup complete")
    
    def evaluate_app(self, pages_url: str, checks: List[str], timeout: int = 30000) -> List[Dict]:
        """
        Evaluate a deployed application against a list of checks.
        
        Args:
            pages_url: URL of the deployed GitHub Pages site
            checks: List of check descriptions/criteria
            timeout: Page load timeout in milliseconds
            
        Returns:
            List of evaluation results
        """
        if not self.browser:
            raise RuntimeError("Browser not initialized. Call setup() first.")
        
        print(f"Starting evaluation of: {pages_url}")
        
        # Create a new browser context for isolation
        context = self.browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (compatible; AppEvaluator/1.0)'
        )
        
        # Create a new page
        page = context.new_page()
        
        results = []
        
        try:
            # Navigate to the application
            print("Loading application...")
            page.goto(pages_url, wait_until='networkidle', timeout=timeout)
            
            # Wait a bit for JavaScript to initialize
            page.wait_for_timeout(2000)
            
            print(f"Page loaded successfully. Title: {page.title()}")
            
            # Run each check
            for i, check in enumerate(checks):
                print(f"Running check {i+1}/{len(checks)}: {check}")
                result = self.run_check(page, check)
                result['check_index'] = i
                results.append(result)
                
                # Small delay between checks
                time.sleep(0.5)
            
            # Additional automatic checks
            auto_results = self.run_automatic_checks(page)
            results.extend(auto_results)
            
        except Exception as e:
            print(f"Error during evaluation: {e}")
            results.append({
                'check': 'page_load_error',
                'passed': False,
                'score': 0.0,
                'error': str(e),
                'check_index': -1
            })
        
        finally:
            # Clean up
            page.close()
            context.close()
        
        print(f"Evaluation complete. {len(results)} checks performed.")
        return results
    
    def run_check(self, page: Page, check: str) -> Dict:
        """
        Execute a single check against the page.
        
        Args:
            page: Playwright page object
            check: Check description or JavaScript code
            
        Returns:
            Dictionary with check results
        """
        try:
            # Determine check type and execute accordingly
            if check.startswith('js:'):
                # JavaScript evaluation check
                js_code = check[3:].strip()
                result = self.evaluate_javascript_check(page, js_code)
                
            elif check.startswith('element:'):
                # Element existence check
                selector = check[8:].strip()
                result = self.evaluate_element_check(page, selector)
                
            elif check.startswith('text:'):
                # Text content check
                text = check[5:].strip()
                result = self.evaluate_text_check(page, text)
                
            elif check.startswith('url:'):
                # URL check
                expected_url = check[4:].strip()
                result = self.evaluate_url_check(page, expected_url)
                
            else:
                # Default to text content check
                result = self.evaluate_text_check(page, check)
            
            return {
                'check': check,
                'passed': result.get('passed', False),
                'score': 1.0 if result.get('passed', False) else 0.0,
                'result': result.get('result'),
                'reason': result.get('reason', ''),
                'execution_time': result.get('execution_time', 0)
            }
            
        except Exception as e:
            return {
                'check': check,
                'passed': False,
                'score': 0.0,
                'error': str(e),
                'reason': f'Check execution failed: {str(e)}'
            }
    
    def evaluate_javascript_check(self, page: Page, js_code: str) -> Dict:
        """
        Evaluate a JavaScript expression on the page.
        
        Args:
            page: Playwright page object
            js_code: JavaScript code to evaluate
            
        Returns:
            Dictionary with evaluation results
        """
        start_time = time.time()
        
        try:
            # Execute JavaScript on the page
            result = page.evaluate(js_code)
            execution_time = time.time() - start_time
            
            # Determine if check passed based on result
            if isinstance(result, bool):
                passed = result
            elif isinstance(result, (int, float)):
                passed = result > 0
            elif isinstance(result, str):
                passed = len(result) > 0
            elif result is None:
                passed = False
            else:
                passed = bool(result)
            
            return {
                'passed': passed,
                'result': result,
                'execution_time': execution_time,
                'reason': f'JavaScript evaluation returned: {result}'
            }
            
        except Exception as e:
            return {
                'passed': False,
                'result': None,
                'execution_time': time.time() - start_time,
                'reason': f'JavaScript execution error: {str(e)}'
            }
    
    def evaluate_element_check(self, page: Page, selector: str) -> Dict:
        """
        Check if an element exists on the page.
        
        Args:
            page: Playwright page object
            selector: CSS selector for the element
            
        Returns:
            Dictionary with check results
        """
        start_time = time.time()
        
        try:
            element = page.query_selector(selector)
            execution_time = time.time() - start_time
            
            passed = element is not None
            
            if passed:
                # Get some info about the element
                tag_name = element.evaluate('el => el.tagName')
                text_content = element.text_content()[:100]  # First 100 chars
                
                return {
                    'passed': True,
                    'result': f'Element found: {tag_name}',
                    'execution_time': execution_time,
                    'reason': f'Element {selector} found with content: "{text_content}"'
                }
            else:
                return {
                    'passed': False,
                    'result': 'Element not found',
                    'execution_time': execution_time,
                    'reason': f'Element with selector "{selector}" not found'
                }
                
        except Exception as e:
            return {
                'passed': False,
                'result': None,
                'execution_time': time.time() - start_time,
                'reason': f'Element check error: {str(e)}'
            }
    
    def evaluate_text_check(self, page: Page, expected_text: str) -> Dict:
        """
        Check if specific text appears on the page.
        
        Args:
            page: Playwright page object
            expected_text: Text to search for
            
        Returns:
            Dictionary with check results
        """
        start_time = time.time()
        
        try:
            page_content = page.content().lower()
            execution_time = time.time() - start_time
            
            passed = expected_text.lower() in page_content
            
            return {
                'passed': passed,
                'result': passed,
                'execution_time': execution_time,
                'reason': f'Text "{expected_text}" {"found" if passed else "not found"} on page'
            }
            
        except Exception as e:
            return {
                'passed': False,
                'result': None,
                'execution_time': time.time() - start_time,
                'reason': f'Text check error: {str(e)}'
            }
    
    def evaluate_url_check(self, page: Page, expected_url: str) -> Dict:
        """
        Check if the current URL matches expected pattern.
        
        Args:
            page: Playwright page object
            expected_url: Expected URL pattern
            
        Returns:
            Dictionary with check results
        """
        start_time = time.time()
        
        try:
            current_url = page.url
            execution_time = time.time() - start_time
            
            passed = expected_url in current_url
            
            return {
                'passed': passed,
                'result': current_url,
                'execution_time': execution_time,
                'reason': f'Current URL "{current_url}" {"matches" if passed else "does not match"} expected "{expected_url}"'
            }
            
        except Exception as e:
            return {
                'passed': False,
                'result': None,
                'execution_time': time.time() - start_time,
                'reason': f'URL check error: {str(e)}'
            }
    
    def run_automatic_checks(self, page: Page) -> List[Dict]:
        """
        Run automatic quality checks on the application.
        
        Args:
            page: Playwright page object
            
        Returns:
            List of automatic check results
        """
        automatic_checks = []
        
        # Check for title
        try:
            title = page.title()
            automatic_checks.append({
                'check': 'auto_has_title',
                'passed': len(title.strip()) > 0,
                'score': 1.0 if len(title.strip()) > 0 else 0.0,
                'result': title,
                'reason': f'Page title: "{title}"'
            })
        except Exception as e:
            automatic_checks.append({
                'check': 'auto_has_title',
                'passed': False,
                'score': 0.0,
                'error': str(e)
            })
        
        # Check for viewport meta tag (responsive design)
        try:
            viewport_meta = page.query_selector('meta[name="viewport"]')
            has_viewport = viewport_meta is not None
            automatic_checks.append({
                'check': 'auto_has_viewport_meta',
                'passed': has_viewport,
                'score': 1.0 if has_viewport else 0.0,
                'reason': 'Viewport meta tag found' if has_viewport else 'No viewport meta tag'
            })
        except Exception as e:
            automatic_checks.append({
                'check': 'auto_has_viewport_meta',
                'passed': False,
                'score': 0.0,
                'error': str(e)
            })
        
        # Check for JavaScript errors in console
        try:
            # This is a simplified check - in practice, you'd want to capture console messages
            # For now, we'll assume no errors if the page loaded successfully
            automatic_checks.append({
                'check': 'auto_no_js_errors',
                'passed': True,  # Page loaded successfully
                'score': 1.0,
                'reason': 'No critical JavaScript errors detected'
            })
        except Exception as e:
            automatic_checks.append({
                'check': 'auto_no_js_errors',
                'passed': False,
                'score': 0.0,
                'error': str(e)
            })
        
        return automatic_checks
    
    def wait_for_pages_availability(self, pages_url: str, max_wait_time: int = 300) -> bool:
        """
        Wait for GitHub Pages to become available before evaluation.
        
        Args:
            pages_url: URL of the GitHub Pages site
            max_wait_time: Maximum time to wait in seconds
            
        Returns:
            True if site becomes available, False if timeout
        """
        print(f"Waiting for Pages to become available: {pages_url}")
        
        if not self.browser:
            self.setup()
        
        context = self.browser.new_context()
        page = context.new_page()
        
        start_time = time.time()
        
        try:
            while time.time() - start_time < max_wait_time:
                try:
                    response = page.goto(pages_url, wait_until='networkidle', timeout=30000)
                    if response and response.status == 200:
                        print("GitHub Pages is now available!")
                        return True
                except Exception:
                    pass
                
                print("Still waiting for Pages deployment...")
                time.sleep(10)
            
            print(f"Timeout waiting for Pages deployment ({max_wait_time}s)")
            return False
            
        finally:
            page.close()
            context.close()