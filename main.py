"""
Microservicio de Identidades Digitales
Punto de entrada principal
"""
from fastapi import FastAPI

app = FastAPI(
    title="Identity Microservice",
    description="Microservicio de Identidades Digitales - SCIM 2.0, OAuth2 y ABAC",
    version="0.1.0"
)

@app.get("/")
async def root():
    return {"message": "Identity Microservice - Ready"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "identity-microservice"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)