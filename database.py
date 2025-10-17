import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional

class DatabaseManager:
    """
    Handles all database operations for the deployment system.
    Uses SQLite for simplicity and portability.
    """
    
    def __init__(self, db_path: str = "deployment.db"):
        """
        Initialize database manager with database file path.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """
        Create database tables if they don't exist.
        This sets up the schema for tracking deployments and evaluations.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Tasks table: stores incoming deployment requests
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    email TEXT NOT NULL,
                    task TEXT NOT NULL,
                    round INTEGER NOT NULL,
                    nonce TEXT NOT NULL,
                    brief TEXT NOT NULL,
                    attachments TEXT,  -- JSON string of attachments
                    checks TEXT,       -- JSON string of check requirements
                    evaluation_url TEXT NOT NULL,
                    endpoint TEXT,
                    status_code INTEGER,
                    secret TEXT
                )
            ''')
            
            # Repositories table: stores created repository information
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS repos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    email TEXT NOT NULL,
                    task TEXT NOT NULL,
                    round INTEGER NOT NULL,
                    nonce TEXT NOT NULL,
                    repo_url TEXT NOT NULL,
                    commit_sha TEXT NOT NULL,
                    pages_url TEXT NOT NULL
                )
            ''')
            
            # Results table: stores evaluation results
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    email TEXT NOT NULL,
                    task TEXT NOT NULL,
                    round INTEGER NOT NULL,
                    repo_url TEXT NOT NULL,
                    commit_sha TEXT NOT NULL,
                    pages_url TEXT NOT NULL,
                    check_name TEXT NOT NULL,
                    score REAL NOT NULL,
                    reason TEXT,
                    logs TEXT
                )
            ''')
            
            conn.commit()
            print("Database initialized successfully")
    
    def store_task(self, task_data: Dict) -> int:
        """
        Store a new task request in the database.
        
        Args:
            task_data: Dictionary containing task information
            
        Returns:
            ID of the inserted task record
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO tasks (
                    timestamp, email, task, round, nonce, brief,
                    attachments, checks, evaluation_url, endpoint, status_code, secret
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now().isoformat(),
                task_data['email'],
                task_data['task'],
                task_data['round'],
                task_data['nonce'],
                task_data['brief'],
                json.dumps(task_data.get('attachments', [])),
                json.dumps(task_data.get('checks', [])),
                task_data['evaluation_url'],
                task_data.get('endpoint'),
                task_data.get('status_code'),
                task_data.get('secret')
            ))
            
            return cursor.lastrowid
    
    def store_repo_info(self, repo_data: Dict) -> int:
        """
        Store repository information after successful deployment.
        
        Args:
            repo_data: Dictionary containing repository details
            
        Returns:
            ID of the inserted repository record
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO repos (
                    timestamp, email, task, round, nonce,
                    repo_url, commit_sha, pages_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now().isoformat(),
                repo_data['email'],
                repo_data['task'],
                repo_data['round'],
                repo_data['nonce'],
                repo_data['repo_url'],
                repo_data['commit_sha'],
                repo_data['pages_url']
            ))
            
            return cursor.lastrowid
    
    def store_evaluation_result(self, result_data: Dict) -> int:
        """
        Store evaluation results from automated testing.
        
        Args:
            result_data: Dictionary containing evaluation results
            
        Returns:
            ID of the inserted result record
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO results (
                    timestamp, email, task, round, repo_url, commit_sha,
                    pages_url, check_name, score, reason, logs
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now().isoformat(),
                result_data['email'],
                result_data['task'],
                result_data['round'],
                result_data['repo_url'],
                result_data['commit_sha'],
                result_data['pages_url'],
                result_data['check_name'],
                result_data['score'],
                result_data.get('reason'),
                result_data.get('logs')
            ))
            
            return cursor.lastrowid
    
    def get_repo_by_task(self, email: str, task: str, round_num: int) -> Optional[Dict]:
        """
        Retrieve repository information for a specific task.
        
        Args:
            email: Student email
            task: Task identifier
            round_num: Round number
            
        Returns:
            Dictionary with repository info or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM repos 
                WHERE email = ? AND task = ? AND round = ?
                ORDER BY timestamp DESC LIMIT 1
            ''', (email, task, round_num))
            
            row = cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            return None
    
    def get_recent_deployments(self, limit: int = 50) -> List[Dict]:
        """
        Get recent deployments for dashboard display.
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List of deployment records
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM repos 
                ORDER BY timestamp DESC LIMIT ?
            ''', (limit,))
            
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]