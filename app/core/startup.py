"""
Inicialización de singletons y datos iniciales
"""
from app.core.database import get_db
from app.core.policies import get_policies
from app.core.logger import get_logger

logger = get_logger("startup")


def initialize_singletons():
    """Inicializar todos los singletons"""
    logger.info("Initializing singletons")
    
    # Inicializar Database Manager
    db = get_db()
    logger.info("Database Manager initialized", db_path=db.db_path)
    
    # Inicializar Policies Manager
    policies = get_policies()
    policy_count = len(policies.get_all_policies())
    logger.info("Policies Manager initialized", policies_count=policy_count)
    
    logger.info("All singletons initialized successfully")


def seed_initial_data():
    """Cargar datos iniciales según requerimientos"""
    db = get_db()
    
    # Verificar si ya hay datos
    existing_users = db.execute_query("SELECT COUNT(*) as count FROM users")
    if existing_users[0]['count'] > 0:
        logger.info("Initial data already exists, skipping seed")
        return
    
    # Datos iniciales según requerimientos
    initial_users = [
        {
            'id': 'usr_jdoe',
            'userName': 'jdoe',
            'givenName': 'John',
            'familyName': 'Doe',
            'active': 1,
            'emails': '["john.doe@company.com"]',
            'groups_list': '["HR_READERS"]',
            'dept': 'HR',
            'riskScore': 20,
            'created': '2024-01-01T00:00:00Z',
            'lastModified': '2024-01-01T00:00:00Z'
        },
        {
            'id': 'usr_agonzalez',
            'userName': 'agonzalez',
            'givenName': 'Ana',
            'familyName': 'González',
            'active': 1,
            'emails': '["ana.gonzalez@company.com"]',
            'groups_list': '["FIN_APPROVERS"]',
            'dept': 'Finance',
            'riskScore': 30,
            'created': '2024-01-01T00:00:00Z',
            'lastModified': '2024-01-01T00:00:00Z'
        },
        {
            'id': 'usr_mrios',
            'userName': 'mrios',
            'givenName': 'Miguel',
            'familyName': 'Ríos',
            'active': 0,
            'emails': '["miguel.rios@company.com"]',
            'groups_list': '["ADMINS"]',
            'dept': 'IT',
            'riskScore': 15,
            'created': '2024-01-01T00:00:00Z',
            'lastModified': '2024-01-01T00:00:00Z'
        }
    ]
    
    # Insertar usuarios usando parámetros (protección SQL injection)
    insert_query = """
        INSERT INTO users 
        (id, userName, givenName, familyName, active, emails, groups_list, dept, riskScore, created, lastModified)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    for user in initial_users:
        db.execute_insert(insert_query, (
            user['id'], user['userName'], user['givenName'], user['familyName'],
            user['active'], user['emails'], user['groups_list'], user['dept'],
            user['riskScore'], user['created'], user['lastModified']
        ))
    
    logger.info("Initial data seeded", users_created=len(initial_users))