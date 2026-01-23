"""
storage.py: Data persistence for Hybrid Energy Profiler.

Provides:
- SQLite-based storage for process snapshots
- Historical data retrieval
- Data retention management
- Trend analysis
"""
import sqlite3
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from energymon.config import get_config
from energymon.logger import get_logger

config = get_config()
logger = get_logger('energymon.storage')


class MetricsStorage:
    """SQLite-based storage for process metrics."""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize metrics storage.
        
        Args:
            db_path: Path to SQLite database (uses config if None)
        """
        if db_path is None:
            db_path = config.get('storage', 'db_path', default='data/metrics.db')
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        logger.info(f"Initialized metrics storage at {self.db_path}")
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        
        # Main snapshots table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS process_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                pid INTEGER NOT NULL,
                name TEXT NOT NULL,
                cpu_percent REAL,
                memory_mb REAL,
                io_read INTEGER,
                io_write INTEGER,
                context_switches INTEGER,
                syscalls INTEGER,
                energy_score REAL,
                classification TEXT,
                data_source TEXT,
                username TEXT,
                parent_pid INTEGER,
                num_threads INTEGER,
                status TEXT,
                metadata TEXT,
                UNIQUE(timestamp, pid)
            )
        ''')
        
        # Create indexes for performance
        conn.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON process_snapshots(timestamp)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_pid ON process_snapshots(pid)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_name ON process_snapshots(name)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_energy ON process_snapshots(energy_score)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_classification ON process_snapshots(classification)')
        
        conn.commit()
        conn.close()
        logger.debug("Database schema initialized")
    
    def save_snapshot(self, processes: List[Dict[str, Any]]) -> int:
        """
        Save current process state to database.
        
        Args:
            processes: List of process dictionaries with energy data
        
        Returns:
            Number of processes saved
        """
        if not processes:
            logger.warning("No processes to save")
            return 0
        
        conn = sqlite3.connect(self.db_path)
        timestamp = datetime.now()
        saved_count = 0
        
        try:
            for proc in processes:
                # Prepare metadata
                metadata = {
                    'cmdline': proc.get('cmdline', ''),
                    'exe': proc.get('exe', ''),
                    'cwd': proc.get('cwd', ''),
                    'nice': proc.get('nice', 0),
                    'num_fds': proc.get('num_fds', 0),
                    'user_time': proc.get('user_time', 0),
                    'system_time': proc.get('system_time', 0),
                    'memory_vms': proc.get('memory_vms', 0),
                    'memory_shared': proc.get('memory_shared', 0)
                }
                
                conn.execute('''
                    INSERT OR REPLACE INTO process_snapshots 
                    (timestamp, pid, name, cpu_percent, memory_mb, io_read, io_write,
                     context_switches, syscalls, energy_score, classification, data_source,
                     username, parent_pid, num_threads, status, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    timestamp,
                    proc.get('pid', 0),
                    proc.get('name', 'unknown'),
                    proc.get('cpu_percent', 0),
                    proc.get('memory_mb', 0),
                    proc.get('io_read', 0),
                    proc.get('io_write', 0),
                    proc.get('context_switches', 0),
                    proc.get('syscalls', 0),
                    proc.get('energy_score', 0),
                    proc.get('classification', 'Unknown'),
                    proc.get('data_source', 'unknown'),
                    proc.get('username', 'N/A'),
                    proc.get('parent_pid', 0),
                    proc.get('num_threads', 1),
                    proc.get('status', 'unknown'),
                    json.dumps(metadata)
                ))
                saved_count += 1
            
            conn.commit()
            logger.debug(f"Saved snapshot: {saved_count} processes at {timestamp}")
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to save snapshot: {e}", exc_info=True)
            raise
        finally:
            conn.close()
        
        return saved_count
    
    def get_history(self, pid: Optional[int] = None, 
                   name: Optional[str] = None,
                   hours: int = 24,
                   limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Retrieve historical data.
        
        Args:
            pid: Filter by process ID
            name: Filter by process name (substring match)
            hours: Number of hours to look back
            limit: Maximum number of records to return
        
        Returns:
            List of historical records
        """
        conn = sqlite3.connect(self.db_path)
        since = datetime.now() - timedelta(hours=hours)
        
        query = 'SELECT * FROM process_snapshots WHERE timestamp >= ?'
        params = [since]
        
        if pid:
            query += ' AND pid = ?'
            params.append(pid)
        if name:
            query += ' AND name LIKE ?'
            params.append(f'%{name}%')
        
        query += ' ORDER BY timestamp DESC LIMIT ?'
        params.append(limit)
        
        try:
            cursor = conn.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            # Parse metadata JSON
            for result in results:
                if result.get('metadata'):
                    try:
                        result['metadata'] = json.loads(result['metadata'])
                    except json.JSONDecodeError:
                        result['metadata'] = {}
            
            logger.debug(f"Retrieved {len(results)} historical records")
            return results
        except Exception as e:
            logger.error(f"Failed to retrieve history: {e}", exc_info=True)
            return []
        finally:
            conn.close()
    
    def get_trends(self, name: str, hours: int = 24) -> List[Dict[str, float]]:
        """
        Get energy trend for a specific process.
        
        Args:
            name: Process name
            hours: Number of hours to look back
        
        Returns:
            List of {timestamp, energy_score} dictionaries
        """
        history = self.get_history(name=name, hours=hours)
        
        trends = []
        for record in history:
            trends.append({
                'timestamp': record['timestamp'],
                'energy_score': record.get('energy_score', 0),
                'cpu_percent': record.get('cpu_percent', 0),
                'memory_mb': record.get('memory_mb', 0)
            })
        
        return trends
    
    def get_top_processes(self, hours: int = 1, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get top energy-consuming processes over time period.
        
        Args:
            hours: Number of hours to analyze
            limit: Number of top processes to return
        
        Returns:
            List of processes with average energy scores
        """
        conn = sqlite3.connect(self.db_path)
        since = datetime.now() - timedelta(hours=hours)
        
        query = '''
            SELECT 
                pid,
                name,
                AVG(energy_score) as avg_energy,
                MAX(energy_score) as max_energy,
                COUNT(*) as sample_count,
                AVG(cpu_percent) as avg_cpu,
                AVG(memory_mb) as avg_memory
            FROM process_snapshots
            WHERE timestamp >= ?
            GROUP BY pid, name
            ORDER BY avg_energy DESC
            LIMIT ?
        '''
        
        try:
            cursor = conn.execute(query, (since, limit))
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            logger.debug(f"Retrieved top {len(results)} processes")
            return results
        except Exception as e:
            logger.error(f"Failed to get top processes: {e}", exc_info=True)
            return []
        finally:
            conn.close()
    
    def cleanup_old_data(self, days: Optional[int] = None) -> int:
        """
        Remove data older than specified days.
        
        Args:
            days: Number of days to retain (uses config if None)
        
        Returns:
            Number of records deleted
        """
        if days is None:
            days = config.get('storage', 'retention_days', default=30)
        
        conn = sqlite3.connect(self.db_path)
        cutoff = datetime.now() - timedelta(days=days)
        
        try:
            cursor = conn.execute('SELECT COUNT(*) FROM process_snapshots WHERE timestamp < ?', (cutoff,))
            count = cursor.fetchone()[0]
            
            conn.execute('DELETE FROM process_snapshots WHERE timestamp < ?', (cutoff,))
            conn.commit()
            
            # Vacuum to reclaim space
            conn.execute('VACUUM')
            conn.commit()
            
            logger.info(f"Cleaned up {count} old records (older than {days} days)")
            return count
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to cleanup old data: {e}", exc_info=True)
            return 0
        finally:
            conn.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        conn = sqlite3.connect(self.db_path)
        
        try:
            # Total records
            cursor = conn.execute('SELECT COUNT(*) FROM process_snapshots')
            total_records = cursor.fetchone()[0]
            
            # Oldest record
            cursor = conn.execute('SELECT MIN(timestamp) FROM process_snapshots')
            oldest = cursor.fetchone()[0]
            
            # Newest record
            cursor = conn.execute('SELECT MAX(timestamp) FROM process_snapshots')
            newest = cursor.fetchone()[0]
            
            # Database size
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
            
            stats = {
                'total_records': total_records,
                'oldest_record': oldest,
                'newest_record': newest,
                'database_size_mb': db_size / (1024 * 1024),
                'database_path': str(self.db_path)
            }
            
            return stats
        except Exception as e:
            logger.error(f"Failed to get stats: {e}", exc_info=True)
            return {}
        finally:
            conn.close()


# Global storage instance
_storage_instance: Optional[MetricsStorage] = None

def get_storage() -> Optional[MetricsStorage]:
    """
    Get global storage instance (if storage is enabled).
    
    Returns:
        MetricsStorage instance or None if disabled
    """
    global _storage_instance
    
    if not config.get('storage', 'enabled', default=True):
        return None
    
    if _storage_instance is None:
        _storage_instance = MetricsStorage()
    
    return _storage_instance
