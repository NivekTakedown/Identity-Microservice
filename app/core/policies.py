"""
Policies Manager singleton para gestión de políticas ABAC en JSON
"""
import json
import threading
from typing import Dict, List, Any, Optional
from pathlib import Path
from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger("policies")


class PoliciesManager:
    """Singleton Policies Manager para archivos JSON"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.settings = get_settings()
            self.policies_path = self.settings.policies_path
            self._policies_cache: Dict[str, Dict[str, Any]] = {}
            self._ensure_policies_file_exists()
            self._load_policies()
            self.initialized = True
    
    def _ensure_policies_file_exists(self):
        """Crear archivo de políticas inicial si no existe"""
        policies_file = Path(self.policies_path)
        policies_file.parent.mkdir(parents=True, exist_ok=True)
        
        if not policies_file.exists():
            initial_policies = {
                "policies": [
                    {
                        "ruleId": "HR-Payroll-01",
                        "effect": "Permit",
                        "description": "HR department can access payroll on trusted devices",
                        "conditions": {
                            "subject.dept": {"eq": "HR"},
                            "resource.type": {"eq": "payroll"},
                            "context.deviceTrusted": {"eq": True}
                        }
                    },
                    {
                        "ruleId": "Risk-StepUp-01",
                        "effect": "Challenge",
                        "description": "High risk users or non-approved geo require step-up",
                        "conditions": {
                            "OR": [
                                {"subject.riskScore": {"gte": 70}},
                                {"context.geo": {"not_in": ["CL", "CO"]}}
                            ]
                        }
                    },
                    {
                        "ruleId": "Admins-NonProd-01",
                        "effect": "Permit",
                        "description": "Admins can access non-prod, challenge for prod",
                        "conditions": {
                            "subject.groups": {"contains": "ADMINS"},
                            "resource.env": {"ne": "prod"}
                        }
                    }
                ]
            }
            
            with open(policies_file, 'w') as f:
                json.dump(initial_policies, f, indent=2)
            
            logger.info("Initial policies file created", path=str(policies_file))
    
    def _load_policies(self):
        """Cargar políticas desde archivo JSON"""
        try:
            with open(self.policies_path, 'r') as f:
                data = json.load(f)
            
            # Validar estructura básica
            if 'policies' not in data or not isinstance(data['policies'], list):
                raise ValueError("Invalid policies file structure")
            
            # Cargar en cache indexado por ruleId
            self._policies_cache.clear()
            for policy in data['policies']:
                if 'ruleId' not in policy:
                    logger.warning("Policy without ruleId found, skipping")
                    continue
                
                self._policies_cache[policy['ruleId']] = policy
            
            logger.info("Policies loaded", count=len(self._policies_cache))
            
        except Exception as e:
            logger.error("Failed to load policies", error=str(e))
            self._policies_cache = {}
    
    def get_all_policies(self) -> List[Dict[str, Any]]:
        """Obtener todas las políticas"""
        return list(self._policies_cache.values())
    
    def get_policy_by_id(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """Obtener política específica por ID"""
        return self._policies_cache.get(rule_id)
    
    def reload_policies(self):
        """Recargar políticas desde archivo (hot-reload)"""
        logger.info("Reloading policies")
        self._load_policies()
    
    def validate_policy(self, policy: Dict[str, Any]) -> bool:
        """Validar estructura básica de una política"""
        required_fields = ['ruleId', 'effect', 'conditions']
        valid_effects = ['Permit', 'Deny', 'Challenge']
        
        # Verificar campos requeridos
        for field in required_fields:
            if field not in policy:
                return False
        
        # Verificar effect válido
        if policy['effect'] not in valid_effects:
            return False
        
        # Verificar que conditions es un dict
        if not isinstance(policy['conditions'], dict):
            return False
        
        return True
    
    def add_policy(self, policy: Dict[str, Any]) -> bool:
        """Agregar nueva política (en memoria)"""
        if not self.validate_policy(policy):
            return False
        
        self._policies_cache[policy['ruleId']] = policy
        logger.info("Policy added", rule_id=policy['ruleId'])
        return True


def get_policies() -> PoliciesManager:
    """Función helper para obtener instancia del PoliciesManager"""
    return PoliciesManager()