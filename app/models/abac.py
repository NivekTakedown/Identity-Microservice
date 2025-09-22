"""
Modelos Pydantic para ABAC (Attribute-Based Access Control)
Schema de políticas y evaluación
"""
from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, List, Optional, Union, Literal
from enum import Enum

class DecisionType(str, Enum):
    """Tipos de decisión ABAC"""
    PERMIT = "Permit"
    DENY = "Deny"
    CHALLENGE = "Challenge"

class OperatorType(str, Enum):
    """Operadores soportados en condiciones"""
    EQ = "eq"           # igual
    NE = "ne"           # no igual
    GT = "gt"           # mayor que
    GTE = "gte"         # mayor o igual
    LT = "lt"           # menor que
    LTE = "lte"         # menor o igual
    IN = "in"           # en lista
    NOT_IN = "not_in"   # no en lista
    CONTAINS = "contains"  # contiene (para arrays)
    NOT_CONTAINS = "not_contains"  # no contiene

class Condition(BaseModel):
    """Condición individual de una política"""
    # Estructura dinámica: {"attribute.path": {"operator": value}}
    # Ejemplo: {"subject.dept": {"eq": "HR"}}
    pass

class PolicyConditions(BaseModel):
    """
    Condiciones de una política con soporte para operadores lógicos
    """
    # Puede ser una condición simple o compuesta con AND/OR
    model_config = {"extra": "allow"}  # Permite campos dinámicos
    
    def model_dump(self, **kwargs):
        """Serialización personalizada"""
        return super().model_dump(**kwargs)

class ABACPolicy(BaseModel):
    """Política ABAC completa"""
    ruleId: str = Field(..., description="Identificador único de la regla")
    effect: DecisionType = Field(..., description="Efecto de la política")
    description: str = Field(..., description="Descripción legible de la política")
    conditions: Dict[str, Any] = Field(..., description="Condiciones para evaluar")
    priority: Optional[int] = Field(default=100, description="Prioridad de evaluación (menor = más prioritario)")
    
    @field_validator('ruleId')
    @classmethod
    def validate_rule_id(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("ruleId no puede estar vacío")
        return v.strip()
    
    @field_validator('conditions')
    @classmethod
    def validate_conditions(cls, v):
        if not v:
            raise ValueError("conditions no puede estar vacío")
        return v

class ABACPolicySet(BaseModel):
    """Conjunto de políticas ABAC"""
    policies: List[ABACPolicy] = Field(..., description="Lista de políticas")
    version: Optional[str] = Field(default="1.0", description="Versión del conjunto de políticas")
    description: Optional[str] = Field(default="", description="Descripción del conjunto")
    
    @field_validator('policies')
    @classmethod
    def validate_policies_unique(cls, v):
        rule_ids = [p.ruleId for p in v]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("Los ruleId deben ser únicos")
        return v

class Subject(BaseModel):
    """Atributos del sujeto (usuario)"""
    dept: Optional[str] = Field(None, description="Departamento del usuario")
    groups: Optional[List[str]] = Field(default_factory=list, description="Grupos del usuario")
    riskScore: Optional[int] = Field(None, ge=0, le=100, description="Score de riesgo 0-100")
    role: Optional[str] = Field(None, description="Rol del usuario")
    clearanceLevel: Optional[str] = Field(None, description="Nivel de autorización")

class Resource(BaseModel):
    """Atributos del recurso"""
    type: Optional[str] = Field(None, description="Tipo de recurso")
    env: Optional[str] = Field(None, description="Ambiente (dev, test, prod)")
    classification: Optional[str] = Field(None, description="Clasificación de seguridad")
    owner: Optional[str] = Field(None, description="Propietario del recurso")
    sensitivity: Optional[str] = Field(None, description="Nivel de sensibilidad")

class Context(BaseModel):
    """Contexto de la solicitud"""
    geo: Optional[str] = Field(None, description="Código de país (ISO 3166-1)")
    deviceTrusted: Optional[bool] = Field(None, description="Si el dispositivo es confiable")
    timeOfDay: Optional[str] = Field(None, description="Hora del día (HH:MM)")
    dayOfWeek: Optional[str] = Field(None, description="Día de la semana")
    ipAddress: Optional[str] = Field(None, description="Dirección IP del cliente")
    userAgent: Optional[str] = Field(None, description="User agent del cliente")
    
    @field_validator('timeOfDay')
    @classmethod
    def validate_time_format(cls, v):
        if v is not None:
            import re
            if not re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', v):
                raise ValueError("timeOfDay debe estar en formato HH:MM")
        return v

class ABACRequest(BaseModel):
    """Solicitud de evaluación ABAC"""
    subject: Subject = Field(..., description="Atributos del sujeto")
    resource: Resource = Field(..., description="Atributos del recurso")
    context: Context = Field(..., description="Contexto de la solicitud")
    action: Optional[str] = Field(default="access", description="Acción solicitada")

class ABACResponse(BaseModel):
    """Respuesta de evaluación ABAC"""
    decision: DecisionType = Field(..., description="Decisión final")
    reasons: List[str] = Field(..., description="Reglas que llevaron a la decisión")
    advice: Optional[List[str]] = Field(default_factory=list, description="Consejos adicionales")
    obligations: Optional[List[str]] = Field(default_factory=list, description="Obligaciones a cumplir")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "decision": "Permit",
                    "reasons": ["ruleId: HR-Payroll-01"],
                    "advice": [],
                    "obligations": []
                },
                {
                    "decision": "Challenge", 
                    "reasons": ["ruleId: Risk-StepUp-01"],
                    "advice": ["Require MFA authentication"],
                    "obligations": ["Log high-risk access attempt"]
                },
                {
                    "decision": "Deny",
                    "reasons": ["No applicable policies found"],
                    "advice": ["Contact administrator"],
                    "obligations": []
                }
            ]
        }
    }

class PolicyValidationResult(BaseModel):
    """Resultado de validación de políticas"""
    valid: bool = Field(..., description="Si las políticas son válidas")
    errors: List[str] = Field(default_factory=list, description="Errores encontrados")
    warnings: List[str] = Field(default_factory=list, description="Advertencias")
    policies_count: int = Field(..., description="Número de políticas validadas")