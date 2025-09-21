"""
Modelos de datos SQLite para SCIM 2.0
"""
from datetime import datetime
from typing import Dict, List, Optional, Any
import json
import uuid


class UserModel:
    """Modelo de datos para tabla users"""
    
    def __init__(self, 
                 id: str = None,
                 userName: str = None,
                 givenName: str = None,
                 familyName: str = None,
                 active: bool = True,
                 emails: List[str] = None,
                 dept: str = None,
                 riskScore: int = 0,
                 created: str = None,
                 lastModified: str = None):
        
        self.id = id or f"usr_{str(uuid.uuid4())[:8]}"
        self.userName = userName
        self.givenName = givenName
        self.familyName = familyName
        self.active = active
        self.emails = emails or []
        self.dept = dept
        self.riskScore = riskScore
        
        now = datetime.now().isoformat() + "Z"
        self.created = created or now
        self.lastModified = lastModified or now
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertir a diccionario para SQLite"""
        return {
            'id': self.id,
            'userName': self.userName,
            'givenName': self.givenName,
            'familyName': self.familyName,
            'active': int(self.active),
            'emails': json.dumps(self.emails),
            'dept': self.dept,
            'riskScore': self.riskScore,
            'created': self.created,
            'lastModified': self.lastModified
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserModel':
        """Crear instancia desde diccionario SQLite"""
        return cls(
            id=data['id'],
            userName=data['userName'],
            givenName=data['givenName'],
            familyName=data['familyName'],
            active=bool(data['active']),
            emails=json.loads(data['emails']) if data['emails'] else [],
            dept=data['dept'],
            riskScore=data['riskScore'],
            created=data['created'],
            lastModified=data['lastModified']
        )


class GroupModel:
    """Modelo de datos para tabla groups"""
    
    def __init__(self,
                 id: str = None,
                 displayName: str = None,
                 members: List[str] = None,
                 created: str = None,
                 lastModified: str = None):
        
        self.id = id or f"grp_{str(uuid.uuid4())[:8]}"
        self.displayName = displayName
        self.members = members or []
        
        now = datetime.now().isoformat() + "Z"
        self.created = created or now
        self.lastModified = lastModified or now
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertir a diccionario para SQLite"""
        return {
            'id': self.id,
            'displayName': self.displayName,
            'members': json.dumps(self.members),
            'created': self.created,
            'lastModified': self.lastModified
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GroupModel':
        """Crear instancia desde diccionario SQLite"""
        return cls(
            id=data['id'],
            displayName=data['displayName'],
            members=json.loads(data['members']) if data['members'] else [],
            created=data['created'],
            lastModified=data['lastModified']
        )


# DDL para tablas mejoradas SIN redundancia
CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    userName TEXT UNIQUE NOT NULL,
    givenName TEXT,
    familyName TEXT,
    active INTEGER DEFAULT 1,
    emails TEXT,  -- JSON array como texto
    dept TEXT,
    riskScore INTEGER DEFAULT 0,
    created TEXT NOT NULL,
    lastModified TEXT NOT NULL
)
"""

CREATE_GROUPS_TABLE = """
CREATE TABLE IF NOT EXISTS groups (
    id TEXT PRIMARY KEY,
    displayName TEXT UNIQUE NOT NULL,
    members TEXT,  -- JSON array con user IDs
    created TEXT NOT NULL,
    lastModified TEXT NOT NULL
)
"""

# Índices optimizados
CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_users_userName ON users(userName)",
    "CREATE INDEX IF NOT EXISTS idx_users_active ON users(active)",
    "CREATE INDEX IF NOT EXISTS idx_users_dept ON users(dept)",
    "CREATE INDEX IF NOT EXISTS idx_users_created ON users(created)",
    "CREATE INDEX IF NOT EXISTS idx_groups_displayName ON groups(displayName)",
    "CREATE INDEX IF NOT EXISTS idx_groups_created ON groups(created)"
]