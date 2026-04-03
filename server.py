import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from bd_agent import BD_GRAPH

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI()
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def sse_message(event: str, data: dict) -> str:
    return f"data: {json.dumps({'event': event, 'data': data}, ensure_ascii=False)}\n\n"


@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/run")
async def run_pipeline(brief: str = "", n: int = 5, n_targets: int | None = None):
    if not brief.strip():
        return {"error": "brief required"}

    target_count = n_targets if n_targets is not None else n

    async def event_stream():
        yield sse_message("searching", {"brief": brief, "n": target_count})
        try:
            async for chunk in BD_GRAPH.astream(
                {"brief": brief, "n": target_count},
                stream_mode="updates",
                config={"recursion_limit": 200},
            ):
                for node_output in chunk.values():
                    for event in node_output.get("events", []):
                        yield sse_message(event["event"], event["data"])
        except Exception as exc:
            yield sse_message("error", {"message": str(exc)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
