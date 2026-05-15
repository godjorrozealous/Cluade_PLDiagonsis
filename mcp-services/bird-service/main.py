from datetime import datetime, timezone
from fastapi import FastAPI
from models import DiagnoseRequest, DiagnoseResponse

app = FastAPI(title="Bird Damage Diagnosis MCP Service")

@app.get("/health")
async def health():
    return {"status": "ok", "tool_name": "BirdDamageDiagnosisTool"}

@app.post("/diagnose")
async def diagnose(req: DiagnoseRequest) -> DiagnoseResponse:
    return DiagnoseResponse(
        tool_name="BirdDamageDiagnosisTool",
        raw_text=f"鸟害监测：线路 {req.line_name} 区段鸟类活动记录正常，"
                  f"无鸟粪闪络痕迹，绝缘子表面清洁。",
        structured_data={
            "fault_type": "鸟害故障",
            "confidence": 0.20,
            "evidence": [
                "无鸟粪闪络痕迹",
                "绝缘子表面清洁",
                "鸟类活动记录正常",
            ],
            "details": {"bird_activity": "normal", "contamination_level": "low"},
        },
        metadata={"source": "巡检记录", "data_quality": "real"},
        timestamp=datetime.now(timezone.utc),
    )

if __name__ == "__main__":
    import uvicorn, os
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8004)))
