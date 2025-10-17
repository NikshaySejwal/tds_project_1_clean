import hashlib
import json
import time
import requests
from typing import Dict, List, Optional
from datetime import datetime

class DeploymentProcessor:
    """
    Main class that orchestrates the complete deployment pipeline.
    Coordinates code generation, GitHub operations, and evaluation.
    """
    
    def __init__(self, github_manager, code_generator, evaluator, db_manager):
        """
        Initialize the deployment processor with required components.
        
        Args:
            github_manager: GitHubManager instance
            code_generator: CodeGenerator instance
            evaluator: AppEvaluator instance
            db_manager: DatabaseManager instance
        """
        self.github = github_manager
        self.generator = code_generator
        self.evaluator = evaluator
        self.db = db_manager
    
    def process_deployment(self, request_data: Dict) -> Dict:
        """
        Process a complete deployment request from brief to deployed application.
        
        Args:
            request_data: Dictionary containing deployment request details
            
        Returns:
            Dictionary with deployment results and status
        """
        print("=== Starting Deployment Process ===")
        
        # Extract and validate request data
        try:
            email = request_data['email']
            task = request_data['task']
            round_num = request_data['round']
            nonce = request_data['nonce']
            brief = request_data['brief']
            checks = request_data.get('checks', [])
            evaluation_url = request_data['evaluation_url']
            attachments = request_data.get('attachments', [])
            
            print(f"Processing deployment for {email}, task: {task}, round: {round_num}")
            
        except KeyError as e:
            return {
                'status': 'error',
                'error': f'Missing required field: {str(e)}'
            }
        
        # Store the task in database
        try:
            task_id = self.db.store_task({
                **request_data,
                'status_code': 200,  # We're processing it
                'endpoint': 'internal'
            })
            print(f"Task stored with ID: {task_id}")
        except Exception as e:
            print(f"Warning: Could not store task: {e}")
        
        deployment_start_time = time.time()
        
        try:
            # Step 1: Generate application code using LLM
            print("\n--- Step 1: Generating Application Code ---")
            code_generation_start = time.time()
            
            generated_code = self.generator.generate_app(brief, attachments, checks)
            
            code_generation_time = time.time() - code_generation_start
            print(f"Code generation completed in {code_generation_time:.2f} seconds")
            
            # Step 2: Create unique repository name
            print("\n--- Step 2: Preparing Repository ---")
            repo_name = self._generate_repo_name(task, brief)
            print(f"Repository name: {repo_name}")
            
            # Step 3: Create GitHub repository
            print("\n--- Step 3: Creating GitHub Repository ---")
            repo_creation_start = time.time()
            
            repo_url = self.github.create_repository(
                repo_name=repo_name,
                description=f"Auto-generated application for task: {task}"
            )
            
            repo_creation_time = time.time() - repo_creation_start
            print(f"Repository created in {repo_creation_time:.2f} seconds: {repo_url}")
            
            # Step 4: Prepare files for upload
            print("\n--- Step 4: Preparing Files ---")
            files = self._prepare_files(generated_code, brief, task)
            print(f"Prepared {len(files)} files for upload")
            
            # Step 5: Upload files to repository
            print("\n--- Step 5: Uploading Files ---")
            upload_start = time.time()
            
            commit_sha = self.github.upload_files(repo_name, files)
            
            upload_time = time.time() - upload_start
            print(f"Files uploaded in {upload_time:.2f} seconds, commit SHA: {commit_sha}")
            
            # Step 6: Enable GitHub Pages
            print("\n--- Step 6: Enabling GitHub Pages ---")
            pages_start = time.time()
            
            pages_url = self.github.enable_pages(repo_name)
            
            pages_time = time.time() - pages_start
            print(f"GitHub Pages enabled in {pages_time:.2f} seconds: {pages_url}")
            
            # Step 7: Store repository information
            print("\n--- Step 7: Storing Repository Information ---")
            repo_data = {
                'email': email,
                'task': task,
                'round': round_num,
                'nonce': nonce,
                'repo_url': repo_url,
                'commit_sha': commit_sha,
                'pages_url': pages_url
            }
            
            repo_id = self.db.store_repo_info(repo_data)
            print(f"Repository information stored with ID: {repo_id}")
            
            # Step 8: Notify evaluation endpoint
            print("\n--- Step 8: Notifying Evaluation Endpoint ---")
            notification_result = self._notify_evaluation_endpoint(evaluation_url, repo_data)
            
            if notification_result['success']:
                print("Evaluation endpoint notified successfully")
            else:
                print(f"Warning: Failed to notify evaluation endpoint: {notification_result['error']}")
            
            # Step 9: Wait for Pages deployment and perform evaluation
            print("\n--- Step 9: Performing Initial Evaluation ---")
            evaluation_results = self._perform_evaluation(pages_url, checks, repo_data)
            
            total_deployment_time = time.time() - deployment_start_time
            print(f"\n=== Deployment Complete ===")
            print(f"Total time: {total_deployment_time:.2f} seconds")
            
            return {
                'status': 'success',
                'repo_url': repo_url,
                'pages_url': pages_url,
                'commit_sha': commit_sha,
                'deployment_time': total_deployment_time,
                'evaluation_results': evaluation_results,
                'notification_result': notification_result
            }
            
        except Exception as e:
            error_message = f"Deployment failed: {str(e)}"
            print(f"ERROR: {error_message}")
            
            return {
                'status': 'error',
                'error': error_message,
                'deployment_time': time.time() - deployment_start_time
            }
    
    def _generate_repo_name(self, task: str, brief: str) -> str:
        """
        Generate a unique repository name based on task and brief.
        
        Args:
            task: Task identifier
            brief: Application brief
            
        Returns:
            Unique repository name
        """
        # Create a hash of the brief for uniqueness
        brief_hash = hashlib.md5(brief.encode()).hexdigest()[:8]
        
        # Clean task name for use in repository name
        clean_task = ''.join(c for c in task if c.isalnum() or c in '-_')
        
        # Combine with timestamp for additional uniqueness
        timestamp = int(time.time())
        
        repo_name = f"{clean_task}-{brief_hash}-{timestamp}"
        
        # Ensure it's not too long (GitHub limit is 100 chars)
        if len(repo_name) > 90:
            repo_name = repo_name[:90]
        
        return repo_name
    
    def _prepare_files(self, generated_code: Dict, brief: str, task: str) -> Dict[str, str]:
        """
        Prepare files for upload to GitHub repository.
        
        Args:
            generated_code: Dictionary with generated HTML, README, and LICENSE
            brief: Original application brief
            task: Task identifier
            
        Returns:
            Dictionary of filename -> content mappings
        """
        files = {}
        
        # Main application file
        files['index.html'] = generated_code['html']
        
        # Enhanced README with deployment information
        enhanced_readme = self._enhance_readme(generated_code['readme'], brief, task)
        files['README.md'] = enhanced_readme
        
        # License file
        files['LICENSE'] = generated_code['license']
        
        # Add deployment metadata
        metadata = {
            'generated_at': datetime.now().isoformat(),
            'task': task,
            'brief': brief,
            'generator': 'LLM Code Deployment System v1.0'
        }
        files['deployment-info.json'] = json.dumps(metadata, indent=2)
        
        return files
    
    def _enhance_readme(self, original_readme: str, brief: str, task: str) -> str:
        """
        Enhance the generated README with additional information.
        
        Args:
            original_readme: Original README content
            brief: Application brief
            task: Task identifier
            
        Returns:
            Enhanced README content
        """
        enhancement = f"""
## Deployment Information

**Task ID:** {task}
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
**Generator:** LLM Code Deployment System

**Original Brief:**
{brief}

---

"""
        
        return enhancement + original_readme
    
    def _notify_evaluation_endpoint(self, evaluation_url: str, repo_data: Dict) -> Dict:
        """
        Send notification to the evaluation endpoint.
        
        Args:
            evaluation_url: URL to send notification to
            repo_data: Repository data to send
            
        Returns:
            Dictionary with notification result
        """
        max_retries = 3
        retry_delays = [1, 2, 4]  # Exponential backoff
        
        for attempt in range(max_retries):
            try:
                print(f"Sending notification (attempt {attempt + 1}/{max_retries})...")
                
                response = requests.post(
                    evaluation_url,
                    json=repo_data,
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )
                
                if response.status_code == 200:
                    return {
                        'success': True,
                        'status_code': response.status_code,
                        'response': response.text[:200]  # First 200 chars
                    }
                else:
                    print(f"Notification failed with status {response.status_code}: {response.text}")
                    
                    if attempt < max_retries - 1:
                        delay = retry_delays[attempt]
                        print(f"Retrying in {delay} seconds...")
                        time.sleep(delay)
                    else:
                        return {
                            'success': False,
                            'error': f'HTTP {response.status_code}: {response.text}',
                            'status_code': response.status_code
                        }
                        
            except requests.exceptions.RequestException as e:
                print(f"Notification request failed: {e}")
                
                if attempt < max_retries - 1:
                    delay = retry_delays[attempt]
                    print(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    return {
                        'success': False,
                        'error': str(e)
                    }
        
        return {
            'success': False,
            'error': 'Max retries exceeded'
        }
    
    def _perform_evaluation(self, pages_url: str, checks: List[str], repo_data: Dict) -> List[Dict]:
        """
        Perform automated evaluation of the deployed application.
        
        Args:
            pages_url: URL of the deployed application
            checks: List of evaluation criteria
            repo_data: Repository information
            
        Returns:
            List of evaluation results
        """
        try:
            # Set up evaluator if not already done
            if not hasattr(self.evaluator, 'browser') or not self.evaluator.browser:
                self.evaluator.setup()
            
            # Wait for Pages to become available
            print("Waiting for GitHub Pages deployment...")
            pages_available = self.evaluator.wait_for_pages_availability(pages_url, max_wait_time=120)
            
            if not pages_available:
                print("Warning: GitHub Pages not available within timeout, proceeding anyway...")
            
            # Run evaluation
            print("Running automated evaluation...")
            evaluation_results = self.evaluator.evaluate_app(pages_url, checks)
            
            # Store evaluation results in database
            for result in evaluation_results:
                try:
                    self.db.store_evaluation_result({
                        **repo_data,
                        'check_name': result['check'],
                        'score': result.get('score', 0.0),
                        'reason': result.get('reason', ''),
                        'logs': json.dumps(result)
                    })
                except Exception as e:
                    print(f"Warning: Could not store evaluation result: {e}")
            
            # Calculate overall score
            total_checks = len(evaluation_results)
            passed_checks = sum(1 for r in evaluation_results if r.get('passed', False))
            overall_score = (passed_checks / total_checks) if total_checks > 0 else 0.0
            
            print(f"Evaluation complete: {passed_checks}/{total_checks} checks passed ({overall_score:.1%})")
            
            return evaluation_results
            
        except Exception as e:
            print(f"Evaluation failed: {e}")
            return [{
                'check': 'evaluation_error',
                'passed': False,
                'score': 0.0,
                'error': str(e)
            }]
    
    def process_revision(self, request_data: Dict) -> Dict:
        """
        Process a revision request (round 2+) to update an existing application.
        
        Args:
            request_data: Dictionary containing revision request details
            
        Returns:
            Dictionary with revision results and status
        """
        print("=== Starting Revision Process ===")
        
        # This is similar to process_deployment but for updates
        # Implementation would be similar but would update existing repo
        # For brevity, we'll use the same logic as initial deployment
        
        return self.process_deployment(request_data)