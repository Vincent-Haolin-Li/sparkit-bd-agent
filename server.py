import asyncio
import json
import os
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from searcher import search_targets
from researcher import research_target
from scorer import score_target
from emailer import draft_email

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.get("/run")
async def run_pipeline(brief: str = "", n: int = 5):
    if not brief:
        return {"error": "brief required"}

    def send(event: str, data: dict):
        return f"data: {json.dumps({'event': event, 'data': data})}\n\n"

    async def event_stream():
        try:
            # Step 1: Search
            yield send("searching", {"brief": brief})
            await asyncio.sleep(0)

            search_result = search_targets(brief, n=n)
            candidates = search_result.get("data", [])
            yield send("search_done", {
                "count": len(candidates),
                "candidates": [{"title": c["title"], "url": c["url"]} for c in candidates]
            })
            await asyncio.sleep(0)

            # Step 2-4: Research, Score, Email for ALL candidates (no skipping)
            assembled = []
            for i, candidate in enumerate(candidates):
                title = candidate["title"]
                url = candidate["url"]
                snippet = candidate["snippet"]

                print(f"[DEBUG] Processing {i+1}: {title}")

                # Research
                yield send("researching", {"index": i + 1, "title": title, "url": url})
                await asyncio.sleep(0)

                research = await asyncio.to_thread(research_target, title, url, snippet)
                profile = research["data"]
                research_steps = research.get("steps", [])

                print(f"[DEBUG] Research done: name={profile.get('name')}")

                # Skip if no valid name extracted
                if not profile.get("name") or profile.get("name") == title or len(profile.get("name", "")) < 3:
                    yield send("research_skipped", {
                        "index": i + 1,
                        "reason": "无法提取有效机构信息",
                        "steps": research_steps
                    })
                    await asyncio.sleep(0)
                    continue

                yield send("research_done", {
                    "index": i + 1,
                    "name": profile.get("name"),
                    "what_they_do": profile.get("what_they_do"),
                    "url": url,
                    "steps": research_steps
                })
                await asyncio.sleep(0)

                # Score
                yield send("scoring", {"index": i + 1, "name": profile.get("name")})
                await asyncio.sleep(0)

                scoring = await asyncio.to_thread(score_target, profile)
                print(f"[DEBUG] Score: {scoring['score']}")

                scoring_steps = scoring.get("steps", [])
                yield send("score_done", {
                    "index": i + 1,
                    "score": scoring["score"],
                    "fashion_tech_fit": scoring["fashion_tech_fit"],
                    "creator_fit": scoring["creator_fit"],
                    "sustainability_fit": scoring["sustainability_fit"],
                    "rationale": scoring.get("rationale", ""),
                    "reasoning_steps": scoring.get("reasoning_steps", []),
                    "steps": scoring_steps
                })
                await asyncio.sleep(0)

                # Email
                yield send("emailing", {"index": i + 1, "name": profile.get("name")})
                await asyncio.sleep(0)

                email = await asyncio.to_thread(draft_email, profile, scoring)
                yield send("email_done", {
                    "index": i + 1,
                    "name": profile.get("name"),
                    "subject": email["subject"],
                    "word_count": email["word_count"]
                })
                await asyncio.sleep(0)

                # Keep ALL targets
                assembled.append({
                    "profile": profile,
                    "scoring": scoring,
                    "outreach": email
                })
                print(f"[DEBUG] Added to assembled, total: {len(assembled)}")

            # Finalize
            assembled.sort(key=lambda x: x["scoring"]["score"], reverse=True)
            targets = [{"rank": i + 1, **item} for i, item in enumerate(assembled)]
            scores = [t["scoring"]["score"] for t in targets]

            result = {
                "brief": brief,
                "generated_at": datetime.now().isoformat(),
                "targets": targets,
                "summary": {
                    "total_targets": len(targets),
                    "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
                    "top_target": targets[0]["profile"].get("name", "") if targets else ""
                }
            }

            # Save
            os.makedirs("output", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = f"output/pipeline_{timestamp}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            yield send("done", {"result": result, "saved_to": out_path})

        except Exception as e:
            yield send("error", {"message": str(e)})

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
