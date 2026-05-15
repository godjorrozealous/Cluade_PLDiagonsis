from datetime import datetime, timezone
from fastapi import FastAPI
from models import DiagnoseRequest, DiagnoseResponse

app = FastAPI(title="Wind Diagnosis MCP Service")

@app.get("/health")
async def health():
    return {"status": "ok", "tool_name": "WindDiagnosisTool"}

@app.post("/diagnose")
async def diagnose(req: DiagnoseRequest) -> DiagnoseResponse:
    return DiagnoseResponse(
        tool_name="WindDiagnosisTool",
        raw_text=f"风偏监测：线路 {req.line_name} 故障时段风速 18m/s，"
                  f"超过设计风速 15m/s，绝缘子串风偏角 12度，接近安全限值。",
        structured_data={
            "fault_type": "风偏放电",
            "confidence": 0.45,
            "evidence": [
                "风速 18m/s 超过设计值 15m/s",
                "绝缘子串风偏角 12度",
            ],
            "details": {"wind_speed_ms": 18, "design_speed_ms": 15, "deflection_deg": 12},
        },
        metadata={"source": "气象监测站", "data_quality": "real"},
        timestamp=datetime.now(timezone.utc),
    )

if __name__ == "__main__":
    import uvicorn, os
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8003)))
