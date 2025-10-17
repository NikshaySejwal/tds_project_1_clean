import os
import json
from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv
import sqlite3
from datetime import datetime

# Import our custom modules
from database import DatabaseManager
from llm_generator import CodeGenerator  
from github_integration import GitHubManager
from evaluator import AppEvaluator
from deployment_processor import DeploymentProcessor

# Load environment variables
load_dotenv()

# Initialize Flask application
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')

# Configuration from environment variables
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-here')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
DATABASE_URL = os.getenv('DATABASE_URL', 'deployment.db')

# Validate required environment variables
if not GITHUB_TOKEN:
    print("ERROR: GITHUB_TOKEN environment variable is required!")
    exit(1)

if not OPENAI_API_KEY:
    print("ERROR: OPENAI_API_KEY environment variable is required!")
    exit(1)

# Initialize components
print("Initializing application components...")

try:
    db_manager = DatabaseManager(DATABASE_URL)
    print("✓ Database manager initialized")
    
    code_generator = CodeGenerator(OPENAI_API_KEY)
    print("✓ Code generator initialized")
    
    github_manager = GitHubManager(GITHUB_TOKEN)
    print("✓ GitHub manager initialized")
    
    evaluator = AppEvaluator(headless=True)
    print("✓ Evaluator initialized")
    
    deployment_processor = DeploymentProcessor(
        github_manager=github_manager,
        code_generator=code_generator,
        evaluator=evaluator,
        db_manager=db_manager
    )
    print("✓ Deployment processor initialized")
    
except Exception as e:
    print(f"ERROR: Failed to initialize components: {e}")
    exit(1)

print("Application initialization complete!\n")

@app.route('/', methods=['GET'])
def home():
    """
    Home page with API information and status.
    """
    return jsonify({
        'service': 'LLM Code Deployment API',
        'version': '1.0.0',
        'status': 'running',
        'endpoints': {
            '/': 'Service information',
            '/api/deploy': 'POST - Deploy application from brief',
            '/api/status': 'GET - API status',
            '/dashboard': 'GET - Deployment dashboard',
            '/health': 'GET - Health check'
        },
        'documentation': 'Submit deployment requests to /api/deploy with proper JSON payload'
    })

@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint for monitoring.
    """
    try:
        # Test database connection
        db_manager.get_recent_deployments(limit=1)
        
        # Test GitHub API (lightweight call)
        github_username = github_manager.get_username()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': 'connected',
            'github_api': f'connected as {github_username}',
            'components': {
                'database': 'ok',
                'llm_generator': 'ok',
                'github_manager': 'ok',
                'evaluator': 'ok'
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }), 500

@app.route('/api/status', methods=['GET'])
def api_status():
    """
    Get API status and recent deployment statistics.
    """
    try:
        recent_deployments = db_manager.get_recent_deployments(limit=10)
        
        # Calculate some basic statistics
        total_deployments = len(recent_deployments)
        
        return jsonify({
            'status': 'operational',
            'timestamp': datetime.now().isoformat(),
            'statistics': {
                'recent_deployments': total_deployments,
                'github_username': github_manager.get_username()
            },
            'recent_activity': recent_deployments
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/api/deploy', methods=['POST'])
def deploy_application():
    """
    Main deployment endpoint.
    Accepts JSON requests and orchestrates the complete deployment process.
    """
    print(f"\n=== New Deployment Request ===")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Client IP: {request.remote_addr}")
    
    try:
        # Parse JSON request
        if not request.is_json:
            return jsonify({
                'error': 'Content-Type must be application/json'
            }), 400
        
        try:
            request_data = request.get_json(force=False, silent=False)
        except Exception:
            return jsonify({
        'error': 'Invalid JSON format'
    }), 400

        if request_data is None:
            return jsonify({
        'error': 'No JSON data provided'
    }), 400

        
        # Validate secret
        provided_secret = request_data.get('secret')
        if provided_secret != SECRET_KEY:
            print(f"Authentication failed: invalid secret")
            return jsonify({
                'error': 'Invalid secret'
            }), 403
        
        # Validate required fields
        required_fields = ['email', 'task', 'round', 'nonce', 'brief', 'evaluation_url']
        missing_fields = [field for field in required_fields if field not in request_data]
        
        if missing_fields:
            return jsonify({
                'error': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400
        
        print(f"Request validated for email: {request_data['email']}")
        print(f"Task: {request_data['task']}")
        print(f"Round: {request_data['round']}")
        print(f"Brief: {request_data['brief'][:100]}...")  # First 100 characters
        
        # Process deployment
        result = deployment_processor.process_deployment(request_data)
        
        if result['status'] == 'success':
            print(f"Deployment successful!")
            print(f"Repository: {result['repo_url']}")
            print(f"Pages URL: {result['pages_url']}")
            
            return jsonify(result), 200
        else:
            print(f"Deployment failed: {result['error']}")
            return jsonify(result), 500
            
    except json.JSONDecodeError:
        return jsonify({
            'error': 'Invalid JSON format'
        }), 400
    except Exception as e:
        print(f"Deployment error: {str(e)}")
        return jsonify({
            'error': f'Internal server error: {str(e)}'
        }), 500

@app.route('/dashboard', methods=['GET'])
def dashboard():
    """
    Simple dashboard to view recent deployments and their status.
    """
    try:
        recent_deployments = db_manager.get_recent_deployments(limit=20)
        
        # Create a simple HTML dashboard
        dashboard_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>LLM Code Deployment Dashboard</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                table { border-collapse: collapse; width: 100%; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
                .status-success { color: green; font-weight: bold; }
                .status-error { color: red; font-weight: bold; }
                .url-link { color: blue; text-decoration: underline; }
                .header { background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>LLM Code Deployment Dashboard</h1>
                <p>Last updated: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>
                <p>Total deployments: """ + str(len(recent_deployments)) + """</p>
            </div>
            
            <h2>Recent Deployments</h2>
            <table>
                <thead>
                    <tr>
                        <th>Timestamp</th>
                        <th>Email</th>
                        <th>Task</th>
                        <th>Round</th>
                        <th>Repository</th>
                        <th>Pages URL</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        # Add deployment rows
        for dep in recent_deployments:
            dashboard_html += f"""
                    <tr>
                        <td>{dep.get('timestamp', 'N/A')}</td>
                        <td>{dep.get('email', 'N/A')}</td>
                        <td>{dep.get('task', 'N/A')}</td>
                        <td>{dep.get('round', 'N/A')}</td>
                        <td><a href="{dep.get('repo_url', '#')}" class="url-link" target="_blank">Repository</a></td>
                        <td><a href="{dep.get('pages_url', '#')}" class="url-link" target="_blank">Live Site</a></td>
                    </tr>
            """
        
        dashboard_html += """
                </tbody>
            </table>
        </body>
        </html>
        """
        
        return dashboard_html
        
    except Exception as e:
        return f"Dashboard error: {str(e)}", 500

@app.errorhandler(404)
def not_found(error):
    """
    Handle 404 errors with helpful information.
    """
    return jsonify({
        'error': 'Not found',
        'message': 'The requested endpoint does not exist',
        'available_endpoints': [
            '/ - Home page',
            '/api/deploy - Deployment endpoint',
            '/dashboard - Deployment dashboard',
            '/health - Health check'
        ]
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """
    Handle 500 errors.
    """
    return jsonify({
        'error': 'Internal server error',
        'message': 'An unexpected error occurred'
    }), 500

# Cleanup function for graceful shutdown
def cleanup():
    """
    Clean up resources when the application shuts down.
    """
    try:
        if evaluator and hasattr(evaluator, 'playwright') and evaluator.playwright:
            evaluator.teardown()
            print("Playwright resources cleaned up")
    except Exception as e:
        print(f"Cleanup error: {e}")

# Register cleanup function
import atexit
atexit.register(cleanup)

if __name__ == '__main__':
    # Development server
    print("Starting development server...")
    print("API will be available at: http://localhost:8000")
    print("Dashboard available at: http://localhost:8000/dashboard")
    print("\nPress Ctrl+C to stop the server")
    
    try:
        app.run(
            host='0.0.0.0', 
            port=8000, 
            debug=True,  # Enable debug mode for development
            threaded=True  # Enable threading for concurrent requests
        )
    except KeyboardInterrupt:
        print("\nServer shutting down...")
        cleanup()