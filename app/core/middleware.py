"""
Middleware para logging de requests
"""
import time
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.logger import log_request


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware para logging automático de requests"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        
        # Log del request
        log_request(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration=process_time,
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        
        return response