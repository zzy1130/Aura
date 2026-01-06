from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Aura Backend API", version="0.1.0")


class ResearchRequest(BaseModel):
    query: str
    vibe_style: str | None = None


@app.get("/")
async def root():
    return {"message": "Welcome to Aura API"}


@app.post("/research/plan")
async def create_research_plan(request: ResearchRequest):
    # Placeholder for Orchestrator Agent logic
    return {
        "status": "planned",
        "plan": ["Analyze query", "Search arXiv", "Draft LaTeX content"],
        "query": request.query,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
