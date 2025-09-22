"""
PolicyRepository - Gestión de políticas ABAC con cache y hot-reload
Minimalista y funcional
"""
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from app.models.abac import ABACPolicySet, ABACPolicy, PolicyValidationResult
from app.core.config import get_settings
from app.core.logger import get_logger
from app.core.policy_validator import PolicyValidator

logger = get_logger("policy_repository")

class PolicyRepositoryError(Exception):
    """Excepción base para errores del PolicyRepository"""
    pass

class PolicyRepository:
    """Repository singleton para gestión de políticas ABAC"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.settings = get_settings()
            self._policies: List[ABACPolicy] = []
            self._policy_set: Optional[ABACPolicySet] = None
            self._last_modified: Optional[datetime] = None
            
            # Check for environment override (useful for testing)
            self._policies_file_path = os.environ.get("POLICIES_PATH", self.settings.policies_path)
            
            # Cargar políticas al inicializar
            self._load_policies()
            
            PolicyRepository._initialized = True
            logger.info("PolicyRepository initialized", 
                       policies_file=self._policies_file_path,
                       policies_count=len(self._policies))
    
    def _load_policies(self) -> None:
        """Carga políticas desde archivo JSON"""
        try:
            policies_path = Path(self._policies_file_path)
            
            if not policies_path.exists():
                logger.warning("Policies file not found, using empty policy set", 
                             file_path=str(policies_path))
                self._policies = []
                self._policy_set = ABACPolicySet(policies=[], version="1.0")
                return
            
            # Leer archivo JSON
            with open(policies_path, 'r', encoding='utf-8') as f:
                policy_data = json.load(f)
            
            # Validar políticas
            validation_result = PolicyValidator.validate_policy_set(policy_data)
            
            if not validation_result.valid:
                error_msg = f"Invalid policies: {'; '.join(validation_result.errors)}"
                logger.error("Policy validation failed", 
                           errors=validation_result.errors,
                           warnings=validation_result.warnings)
                raise PolicyRepositoryError(error_msg)
            
            if validation_result.warnings:
                logger.warning("Policy validation warnings", 
                             warnings=validation_result.warnings)
            
            # Crear PolicySet
            self._policy_set = ABACPolicySet(**policy_data)
            self._policies = self._policy_set.policies
            
            # Ordenar por prioridad (menor número = mayor prioridad)
            self._policies.sort(key=lambda p: p.priority or 100)
            
            # Actualizar timestamp
            self._last_modified = datetime.fromtimestamp(policies_path.stat().st_mtime)
            
            logger.info("Policies loaded successfully", 
                       policies_count=len(self._policies),
                       last_modified=self._last_modified.isoformat(),
                       warnings_count=len(validation_result.warnings))
            
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in policies file: {e}"
            logger.error("JSON parsing failed", error=str(e), file_path=self._policies_file_path)
            raise PolicyRepositoryError(error_msg)
        except Exception as e:
            error_msg = f"Failed to load policies: {e}"
            logger.error("Policy loading failed", error=str(e), file_path=self._policies_file_path)
            raise PolicyRepositoryError(error_msg)
    
    def get_all_policies(self) -> List[ABACPolicy]:
        """
        Retorna todas las políticas ordenadas por prioridad
        Verifica hot-reload automáticamente
        
        Returns:
            Lista de políticas ordenadas por prioridad
        """
        # Verificar si necesita hot-reload
        if self._should_reload():
            logger.info("Hot-reloading policies due to file changes")
            self._load_policies()
        
        return self._policies.copy()
    
    def get_policy_by_id(self, rule_id: str) -> Optional[ABACPolicy]:
        """
        Busca una política específica por ruleId
        
        Args:
            rule_id: Identificador de la regla
            
        Returns:
            Política encontrada o None
        """
        policies = self.get_all_policies()  # Incluye hot-reload check
        
        for policy in policies:
            if policy.ruleId == rule_id:
                logger.debug("Policy found", rule_id=rule_id)
                return policy
        
        logger.debug("Policy not found", rule_id=rule_id)
        return None
    
    def get_policies_by_effect(self, effect: str) -> List[ABACPolicy]:
        """
        Filtra políticas por efecto (Permit, Deny, Challenge)
        
        Args:
            effect: Efecto a filtrar
            
        Returns:
            Lista de políticas con el efecto especificado
        """
        policies = self.get_all_policies()
        filtered = [p for p in policies if p.effect.value == effect]
        
        logger.debug("Policies filtered by effect", 
                    effect=effect, 
                    count=len(filtered),
                    total=len(policies))
        
        return filtered
    
    def get_policy_set_metadata(self) -> Dict[str, Any]:
        """
        Retorna metadatos del conjunto de políticas
        
        Returns:
            Diccionario con metadatos
        """
        self.get_all_policies()  # Trigger hot-reload check
        
        return {
            "version": self._policy_set.version if self._policy_set else "unknown",
            "description": self._policy_set.description if self._policy_set else "",
            "policies_count": len(self._policies),
            "last_modified": self._last_modified.isoformat() if self._last_modified else None,
            "file_path": self._policies_file_path,
            "effects_distribution": self._get_effects_distribution()
        }
    
    def reload_policies(self) -> PolicyValidationResult:
        """
        Fuerza la recarga de políticas desde archivo
        
        Returns:
            Resultado de la validación de políticas
        """
        logger.info("Manual policy reload requested")
        
        try:
            old_count = len(self._policies)
            self._load_policies()
            new_count = len(self._policies)
            
            logger.info("Manual policy reload completed", 
                       old_count=old_count, 
                       new_count=new_count)
            
            return PolicyValidationResult(
                valid=True,
                errors=[],
                warnings=[],
                policies_count=new_count
            )
            
        except PolicyRepositoryError as e:
            logger.error("Manual policy reload failed", error=str(e))
            return PolicyValidationResult(
                valid=False,
                errors=[str(e)],
                warnings=[],
                policies_count=len(self._policies)
            )
    
    def validate_current_policies(self) -> PolicyValidationResult:
        """
        Valida las políticas actualmente cargadas
        
        Returns:
            Resultado de validación
        """
        if not self._policy_set:
            return PolicyValidationResult(
                valid=False,
                errors=["No policies loaded"],
                warnings=[],
                policies_count=0
            )
        
        policy_data = self._policy_set.model_dump()
        return PolicyValidator.validate_policy_set(policy_data)
    
    def _should_reload(self) -> bool:
        """
        Verifica si el archivo de políticas ha cambiado y necesita recarga
        
        Returns:
            True si necesita recarga, False caso contrario
        """
        try:
            policies_path = Path(self._policies_file_path)
            
            if not policies_path.exists():
                return False
            
            file_modified = datetime.fromtimestamp(policies_path.stat().st_mtime)
            
            # Si no tenemos timestamp previo o el archivo es más nuevo
            needs_reload = (
                self._last_modified is None or 
                file_modified > self._last_modified
            )
            
            if needs_reload:
                logger.debug("Policy file changed", 
                           current_modified=self._last_modified.isoformat() if self._last_modified else None,
                           file_modified=file_modified.isoformat())
            
            return needs_reload
            
        except Exception as e:
            logger.warning("Error checking policy file modification time", error=str(e))
            return False
    
    def _get_effects_distribution(self) -> Dict[str, int]:
        """Calcula la distribución de efectos en las políticas"""
        distribution = {"Permit": 0, "Deny": 0, "Challenge": 0}
        
        for policy in self._policies:
            effect = policy.effect.value
            if effect in distribution:
                distribution[effect] += 1
        
        return distribution

# Instancia singleton global
_policy_repository = None

def get_policy_repository() -> PolicyRepository:
    """Factory function para obtener la instancia del PolicyRepository"""
    global _policy_repository
    if _policy_repository is None:
        _policy_repository = PolicyRepository()
    return _policy_repository