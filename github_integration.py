import requests
import base64
import json
import time
from typing import Dict, List, Optional

class GitHubManager:
    """
    Handles all GitHub API operations including repository creation,
    file uploads, and GitHub Pages deployment.
    """
    
    def __init__(self, token: str):
        """
        Initialize GitHub manager with personal access token.
        
        Args:
            token: GitHub Personal Access Token with appropriate permissions
        """
        self.token = token
        self.headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'LLM-Code-Deployment/1.0'
        }
        self.base_url = 'https://api.github.com'
        self._username = None  # Cache username
    
    def get_username(self) -> str:
        """
        Get the authenticated user's GitHub username.
        Caches the result to avoid repeated API calls.
        
        Returns:
            GitHub username string
        """
        if self._username:
            return self._username
        
        url = f'{self.base_url}/user'
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            self._username = response.json()['login']
            return self._username
        else:
            raise Exception(f'Failed to get username: {response.status_code} - {response.text}')
    
    def create_repository(self, repo_name: str, description: str = "") -> str:
        """
        Create a new public GitHub repository.
        
        Args:
            repo_name: Name for the new repository
            description: Optional description for the repository
            
        Returns:
            URL of the created repository
        """
        url = f'{self.base_url}/user/repos'
        
        # Repository configuration
        data = {
            'name': repo_name,
            'description': description or f"Generated application: {repo_name}",
            'private': False,  # Must be public for GitHub Pages
            'auto_init': True,  # Initialize with README
            'has_issues': True,
            'has_projects': False,
            'has_wiki': False
        }
        
        response = self._make_api_request('POST', url, data)
        
        if response.status_code == 201:
            repo_data = response.json()
            print(f"Repository created successfully: {repo_data['html_url']}")
            
            # Wait a moment for repository to be fully initialized
            time.sleep(2)
            
            return repo_data['html_url']
        elif response.status_code == 422:
            # Repository might already exist
            existing_repo = self._get_repository(repo_name)
            if existing_repo:
                print(f"Repository already exists: {existing_repo['html_url']}")
                return existing_repo['html_url']
            else:
                raise Exception(f'Repository creation failed: {response.text}')
        else:
            raise Exception(f'Failed to create repository: {response.status_code} - {response.text}')
    
    def _get_repository(self, repo_name: str) -> Optional[Dict]:
        """
        Get information about an existing repository.
        
        Args:
            repo_name: Name of the repository
            
        Returns:
            Repository information dictionary or None if not found
        """
        username = self.get_username()
        url = f'{self.base_url}/repos/{username}/{repo_name}'
        
        response = self._make_api_request('GET', url)
        
        if response.status_code == 200:
            return response.json()
        return None
    
    def upload_files(self, repo_name: str, files: Dict[str, str]) -> str:
        """
        Upload multiple files to a GitHub repository.
        
        Args:
            repo_name: Name of the target repository
            files: Dictionary of filename -> content mappings
            
        Returns:
            SHA hash of the latest commit
        """
        username = self.get_username()
        latest_sha = None
        
        # First, get the current commit SHA to ensure we're working with latest
        try:
            ref_url = f'{self.base_url}/repos/{username}/{repo_name}/git/refs/heads/main'
            ref_response = self._make_api_request('GET', ref_url)
            if ref_response.status_code == 200:
                current_sha = ref_response.json()['object']['sha']
                print(f"Current HEAD SHA: {current_sha}")
        except Exception as e:
            print(f"Warning: Could not get current SHA: {e}")
        
        # Upload each file
        for file_path, content in files.items():
            print(f"Uploading {file_path}...")
            
            # Check if file already exists to get its SHA for updates
            file_sha = self._get_file_sha(repo_name, file_path)
            
            url = f'{self.base_url}/repos/{username}/{repo_name}/contents/{file_path}'
            
            # Prepare file data
            file_data = {
                'message': f'Add/Update {file_path}',
                'content': base64.b64encode(content.encode('utf-8')).decode('ascii')
            }
            
            # Include SHA if file exists (for updates)
            if file_sha:
                file_data['sha'] = file_sha
                print(f"Updating existing file {file_path}")
            else:
                print(f"Creating new file {file_path}")
            
            response = self._make_api_request('PUT', url, file_data)
            
            if response.status_code in [200, 201]:
                result = response.json()
                latest_sha = result['commit']['sha']
                print(f"Successfully uploaded {file_path}, commit SHA: {latest_sha}")
            else:
                raise Exception(f'Failed to upload {file_path}: {response.status_code} - {response.text}')
            
            # Small delay between uploads to respect rate limits
            time.sleep(0.5)
        
        return latest_sha
    
    def _get_file_sha(self, repo_name: str, file_path: str) -> Optional[str]:
        """
        Get the SHA of an existing file in the repository.
        
        Args:
            repo_name: Repository name
            file_path: Path to the file
            
        Returns:
            File SHA if exists, None otherwise
        """
        username = self.get_username()
        url = f'{self.base_url}/repos/{username}/{repo_name}/contents/{file_path}'
        
        response = self._make_api_request('GET', url)
        
        if response.status_code == 200:
            return response.json()['sha']
        return None
    
    def enable_pages(self, repo_name: str) -> str:
        """
        Enable GitHub Pages for a repository.
        
        Args:
            repo_name: Name of the repository
            
        Returns:
            URL where the site will be available
        """
        username = self.get_username()
        url = f'{self.base_url}/repos/{username}/{repo_name}/pages'
        
        # GitHub Pages configuration
        pages_config = {
            'source': {
                'branch': 'main',
                'path': '/'
            }
        }
        
        response = self._make_api_request('POST', url, pages_config)
        
        if response.status_code == 201:
            pages_data = response.json()
            pages_url = pages_data['html_url']
            print(f"GitHub Pages enabled: {pages_url}")
            return pages_url
        elif response.status_code == 409:
            # Pages might already be enabled
            print("GitHub Pages already enabled for this repository")
            # Construct the expected URL
            pages_url = f'https://{username}.github.io/{repo_name}/'
            return pages_url
        else:
            # Try to get existing pages info
            get_response = self._make_api_request('GET', url)
            if get_response.status_code == 200:
                pages_url = get_response.json()['html_url']
                print(f"GitHub Pages already exists: {pages_url}")
                return pages_url
            else:
                raise Exception(f'Failed to enable GitHub Pages: {response.status_code} - {response.text}')
    
    def _make_api_request(self, method: str, url: str, data: Dict = None) -> requests.Response:
        """
        Make a GitHub API request with proper error handling and rate limiting.
        
        Args:
            method: HTTP method (GET, POST, PUT, etc.)
            url: API endpoint URL
            data: Request payload for POST/PUT requests
            
        Returns:
            Response object
        """
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                if method.upper() == 'GET':
                    response = requests.get(url, headers=self.headers, timeout=30)
                elif method.upper() == 'POST':
                    response = requests.post(url, headers=self.headers, json=data, timeout=30)
                elif method.upper() == 'PUT':
                    response = requests.put(url, headers=self.headers, json=data, timeout=30)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                # Check for rate limiting
                if response.status_code == 403 and 'rate limit' in response.text.lower():
                    reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                    current_time = int(time.time())
                    wait_time = reset_time - current_time + 10  # Add 10 second buffer
                    
                    if wait_time > 0 and wait_time < 3600:  # Don't wait more than 1 hour
                        print(f"Rate limit exceeded. Waiting {wait_time} seconds...")
                        time.sleep(wait_time)
                        continue
                
                # Return response for caller to handle status codes
                return response
                
            except requests.exceptions.RequestException as e:
                print(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                else:
                    raise Exception(f"API request failed after {max_retries} attempts: {e}")
        
        # This shouldn't be reached, but just in case
        raise Exception("Unexpected error in API request")
    
    def verify_pages_deployment(self, pages_url: str, max_wait_time: int = 300) -> bool:
        """
        Verify that GitHub Pages deployment is successful by checking if the site is accessible.
        
        Args:
            pages_url: URL of the GitHub Pages site
            max_wait_time: Maximum time to wait in seconds
            
        Returns:
            True if site is accessible, False otherwise
        """
        print(f"Verifying Pages deployment: {pages_url}")
        
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            try:
                response = requests.get(pages_url, timeout=10)
                if response.status_code == 200:
                    print("GitHub Pages deployment verified successfully!")
                    return True
                elif response.status_code == 404:
                    print("Site not yet available, waiting...")
                else:
                    print(f"Unexpected response code: {response.status_code}")
            except requests.exceptions.RequestException as e:
                print(f"Connection error: {e}")
            
            time.sleep(10)  # Wait 10 seconds before retrying
        
        print(f"Pages verification timed out after {max_wait_time} seconds")
        return False