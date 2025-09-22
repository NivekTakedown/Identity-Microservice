"""
Tests para AuthzService
"""
import pytest
import os
import tempfile
import json
from pathlib import Path

from app.services.authz_service import AuthzService
from app.models.abac import ABACRequest, Subject, Resource, Context, DecisionType
from app.repositories.policy_repository import PolicyRepository

def create_test_policies():
    """Crea políticas de prueba"""
    policies = {
        "version": "1.0",
        "policies": [
            {
                "ruleId": "HR-PERMIT-01",
                "effect": "Permit",
                "description": "HR can access payroll",
                "priority": 10,
                "conditions": {
                    "AND": [
                        {"subject.dept": {"eq": "HR"}},
                        {"resource.type": {"eq": "payroll"}}
                    ]
                }
            },
            {
                "ruleId": "HIGH-RISK-CHALLENGE",
                "effect": "Challenge", 
                "description": "High risk users need step-up",
                "priority": 5,
                "conditions": {
                    "subject.riskScore": {"gte": 70}
                }
            }
        ]
    }
    
    temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
    json.dump(policies, temp_file, indent=2)
    temp_file.close()
    return temp_file.name

@pytest.fixture(autouse=True)
def setup_policies():
    """Setup políticas para tests"""
    # Reset singleton
    PolicyRepository._instance = None
    PolicyRepository._initialized = False
    
    # Crear archivo de políticas temporales
    policies_file = create_test_policies()
    os.environ["POLICIES_PATH"] = policies_file
    
    yield
    
    # Cleanup
    Path(policies_file).unlink()
    PolicyRepository._instance = None
    PolicyRepository._initialized = False

def test_evaluate_authorization():
    """Test evaluación de autorización básica"""
    authz_service = AuthzService()
    
    request = ABACRequest(
        subject=Subject(dept="HR", riskScore=20),
        resource=Resource(type="payroll"),
        context=Context(geo="CL")
    )
    
    response = authz_service.evaluate_authorization(request, correlation_id="test-001")
    
    assert response.decision == DecisionType.PERMIT
    assert len(response.reasons) > 0

def test_cache_functionality():
    """Test funcionalidad de cache"""
    authz_service = AuthzService()
    
    request = ABACRequest(
        subject=Subject(dept="HR", riskScore=20),
        resource=Resource(type="payroll"),
        context=Context(geo="CL")
    )
    
    # Primera evaluación (sin cache)
    response1 = authz_service.evaluate_authorization(request)
    
    # Segunda evaluación (debería usar cache)
    response2 = authz_service.evaluate_authorization(request)
    
    # Verificar que las respuestas son iguales
    assert response1.decision == response2.decision
    assert response1.reasons == response2.reasons

def test_get_applicable_policies():
    """Test obtención de políticas aplicables"""
    authz_service = AuthzService()
    
    request = ABACRequest(
        subject=Subject(dept="HR", riskScore=20),
        resource=Resource(type="payroll"),
        context=Context(geo="CL")
    )
    
    result = authz_service.get_applicable_policies(request)
    
    assert "total_policies" in result
    assert "applicable_policies" in result
    assert "non_applicable_policies" in result
    assert result["total_policies"] == 2

def test_validate_policies():
    """Test validación de políticas"""
    authz_service = AuthzService()
    
    result = authz_service.validate_policies()
    
    assert "validation" in result
    assert "metadata" in result
    assert "timestamp" in result

def test_get_metrics():
    """Test obtención de métricas"""
    authz_service = AuthzService()
    
    metrics = authz_service.get_metrics()
    
    assert "policies" in metrics
    assert "cache" in metrics
    assert "service" in metrics
    assert metrics["service"]["status"] == "healthy"

def test_challenge_decision():
    """Test decisión Challenge con logging detallado"""
    authz_service = AuthzService()
    
    request = ABACRequest(
        subject=Subject(dept="IT", riskScore=80),  # High risk
        resource=Resource(type="data"),
        context=Context(geo="US")  # Non-approved geo
    )
    
    response = authz_service.evaluate_authorization(request, correlation_id="test-challenge")
    
    assert response.decision == DecisionType.CHALLENGE
    # Verificar que se agregó correlation_id a obligations
    assert any("correlation_id: test-challenge" in str(obligation) 
              for obligation in (response.obligations or []))

def test_reload_policies():
    """Test recarga de políticas"""
    authz_service = AuthzService()
    
    # Ejecutar request para llenar cache
    request = ABACRequest(
        subject=Subject(dept="HR", riskScore=20),
        resource=Resource(type="payroll"),
        context=Context(geo="CL")
    )
    authz_service.evaluate_authorization(request)
    
    # Verificar que cache tiene entradas
    assert len(authz_service._decision_cache) > 0
    
    # Recargar políticas
    result = authz_service.reload_policies()
    
    assert result["cache_cleared"] == True
    assert "reload_result" in result
    assert len(authz_service._decision_cache) == 0  # Cache debe estar limpio