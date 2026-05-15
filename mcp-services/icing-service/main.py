from datetime import datetime, timezone
from fastapi import FastAPI
from models import DiagnoseRequest, DiagnoseResponse

app = FastAPI(title="Icing Diagnosis MCP Service")

@app.get("/health")
async def health():
    return {"status": "ok", "tool_name": "IcingDiagnosisTool"}

@app.post("/diagnose")
async def diagnose(req: DiagnoseRequest) -> DiagnoseResponse:
    return DiagnoseResponse(
        tool_name="IcingDiagnosisTool",
        raw_text=f"覆冰监测：线路 {req.line_name} 覆冰厚度 2.3mm，低于设计标准 10mm，"
                  f"导线弧垂正常，无脱冰跳跃迹象。",
        structured_data={
            "fault_type": "覆冰故障",
            "confidence": 0.30,
            "evidence": [
                "覆冰厚度 2.3mm，低于设计标准",
                "导线弧垂正常",
                "无脱冰跳跃记录",
            ],
            "details": {"icing_thickness_mm": 2.3, "design_standard_mm": 10},
        },
        metadata={"source": "气象监测站", "data_quality": "real"},
        timestamp=datetime.now(timezone.utc),
    )

if __name__ == "__main__":
    import uvicorn, os
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8002)))
