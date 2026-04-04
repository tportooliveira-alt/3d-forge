from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import upload, convert, repair, process, chat, face3d, export, estimate, viewer, analyze, admin

app = FastAPI(
    title="3D FORGE API",
    description="Pipeline completo: foto/modelo 3D → conversão → reparo → exportação → estimativa de impressão",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api", tags=["Upload"])
app.include_router(convert.router, prefix="/api", tags=["Conversão"])
app.include_router(repair.router, prefix="/api", tags=["Reparo"])
app.include_router(export.router, prefix="/api", tags=["Export"])
app.include_router(analyze.router, prefix="/api", tags=["Análise"])
app.include_router(estimate.router, prefix="/api", tags=["Impressão 3D"])
app.include_router(process.router, prefix="/api", tags=["Orquestrador"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(face3d.router, prefix="/api", tags=["Face3D"])
app.include_router(viewer.router, prefix="/api", tags=["Viewer"])
app.include_router(admin.router, prefix="/api", tags=["Admin"])


@app.get("/")
async def root():
    return {
        "status": "online",
        "api": "3D FORGE",
        "version": "2.0.0",
        "rotas": {
            "upload": "POST /api/upload",
            "convert": "POST /api/convert",
            "repair": "POST /api/repair",
            "export": "POST /api/export?format=glb",
            "analyze": "POST /api/analyze",
            "estimate": "POST /api/estimate?printer=ender3&filament=pla",
            "face3d": "POST /api/face3d",
            "chat": "POST /api/chat",
            "viewer": "GET /api/view/{job_id}",
            "formats": "GET /api/formats",
            "printers": "GET /api/printers",
            "docs": "GET /docs",
        },
    }
