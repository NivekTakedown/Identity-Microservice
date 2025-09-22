"""
Inicialización de singletons y datos iniciales
"""
from app.core.database import get_db
from app.core.policies import get_policies
from app.core.logger import get_logger
from app.models.database import UserModel, GroupModel

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
    
    # 1. Crear usuarios PRIMERO (SIN groups_list)
    initial_users = [
        UserModel(
            id='usr_jdoe',
            userName='jdoe',
            givenName='John',
            familyName='Doe',
            active=True,
            emails=['john.doe@company.com'],
            dept='HR',
            riskScore=20
        ),
        UserModel(
            id='usr_agonzalez',
            userName='agonzalez',
            givenName='Ana',
            familyName='González',
            active=True,
            emails=['ana.gonzalez@company.com'],
            dept='Finance',
            riskScore=30
        ),
        UserModel(
            id='usr_mrios',
            userName='mrios',
            givenName='Miguel',
            familyName='Ríos',
            active=False,
            emails=['miguel.rios@company.com'],
            dept='IT',
            riskScore=15
        )
    ]
    
    # Insertar usuarios usando parámetros (protección SQL injection)
    insert_user_query = """
        INSERT INTO users 
        (id, userName, givenName, familyName, active, emails, dept, riskScore, created, lastModified)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    for user in initial_users:
        user_data = user.to_dict()
        db.execute_insert(insert_user_query, (
            user_data['id'], user_data['userName'], user_data['givenName'], 
            user_data['familyName'], user_data['active'], user_data['emails'], 
            user_data['dept'], user_data['riskScore'], user_data['created'], 
            user_data['lastModified']
        ))
    
    # 2. Crear grupos DESPUÉS con membresías consistentes
    initial_groups = [
        GroupModel(
            id='grp_hr_readers',
            displayName='HR_READERS',
            members=['usr_jdoe']  # Asignación directa y consistente
        ),
        GroupModel(
            id='grp_fin_approvers',
            displayName='FIN_APPROVERS',
            members=['usr_agonzalez']
        ),
        GroupModel(
            id='grp_admins',
            displayName='ADMINS',
            members=['usr_mrios']
        )
    ]
    
    # Insertar grupos con membresías correctas
    insert_group_query = """
        INSERT INTO groups 
        (id, displayName, members, created, lastModified)
        VALUES (?, ?, ?, ?, ?)
    """
    
    for group in initial_groups:
        group_data = group.to_dict()
        db.execute_insert(insert_group_query, (
            group_data['id'], group_data['displayName'], group_data['members'],
            group_data['created'], group_data['lastModified']
        ))
    
    logger.info("Initial data seeded", 
                users_created=len(initial_users), 
                groups_created=len(initial_groups))