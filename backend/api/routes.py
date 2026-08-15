import os
import uuid
import asyncio
import networkx as nx
import requests as http_requests
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response, JSONResponse

from backend.schemas.graph import BuildRequest, BuildResponse, GraphStats
from backend.core.vk_client import VKClient
from backend.core.graph_builder import GraphBuilder
from backend.core import exporter

router = APIRouter(prefix="/api")

_sessions: dict[str, nx.Graph] = {}
_jobs: dict[str, dict] = {}
_executor = ThreadPoolExecutor(max_workers=2)


def _get_client() -> VKClient:
    token = os.getenv("VK_ACCESS_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="VK_ACCESS_TOKEN не настроен")
    return VKClient(token)


def _run_build(job_id: str, vk_id: str, deep: bool):
    try:
        client = VKClient(os.getenv("VK_ACCESS_TOKEN"))
        user = client.get_user(vk_id)
        builder = GraphBuilder(client)
        G = builder.build(user["id"], deep=deep)

        session_id = str(uuid.uuid4())
        _sessions[session_id] = G

        most_connected = max(G.nodes(), key=lambda n: G.degree(n))
        mc_data = G.nodes[most_connected]

        _jobs[job_id] = {
            "status": "done",
            "session_id": session_id,
            "stats": {
                "nodes": G.number_of_nodes(),
                "edges": G.number_of_edges(),
                "most_connected": mc_data.get("label", str(most_connected)),
                "most_connected_degree": G.degree(most_connected),
            },
        }
    except Exception as e:
        _jobs[job_id] = {"status": "error", "error": str(e)}


@router.post("/graph/build")
async def build_graph(body: BuildRequest):
    token = os.getenv("VK_ACCESS_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="VK_ACCESS_TOKEN не настроен")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "pending"}

    deep = body.mode == "friends_of_friends"
    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, _run_build, job_id, body.vk_id, deep)

    return {"job_id": job_id}


@router.get("/graph/status/{job_id}")
def get_job_status(job_id: str):
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return JSONResponse(content=job)


@router.get("/graph/{session_id}/data")
def get_graph_data(session_id: str):
    G = _sessions.get(session_id)
    if G is None:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    data = {
        "nodes": [{"id": n, **G.nodes[n], "degree": G.degree(n)} for n in G.nodes()],
        "edges": [{"source": u, "target": v} for u, v in G.edges()],
    }
    return JSONResponse(content=data)


@router.get("/export/{session_id}/{format}")
def export_graph(session_id: str, format: str):
    G = _sessions.get(session_id)
    if G is None:
        raise HTTPException(status_code=404, detail="Сессия не найдена — постройте граф заново")

    os.makedirs("exports", exist_ok=True)
    filename_base = f"vkgraph_{session_id[:8]}"

    if format == "json":
        path = exporter.export_json(G, f"{filename_base}.json")
        return FileResponse(path, media_type="application/octet-stream", filename=f"{filename_base}.json")
    elif format == "graphml":
        path = exporter.export_graphml(G, f"{filename_base}.graphml")
        return FileResponse(path, media_type="application/xml", filename=f"{filename_base}.graphml")
    elif format == "png":
        path = exporter.export_png(G, f"{filename_base}.png")
        return FileResponse(path, media_type="image/png", filename=f"{filename_base}.png")
    else:
        raise HTTPException(status_code=400, detail=f"Неизвестный формат: {format}")


@router.get("/avatar")
def proxy_avatar(url: str):
    if not url.startswith("https://") and not url.startswith("http://"):
        raise HTTPException(status_code=400, detail="Недопустимый URL")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            "Referer": "https://vk.com/",
            "Origin": "https://vk.com",
        }
        r = http_requests.get(url, timeout=10, headers=headers)
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail=f"VK вернул {r.status_code}")
        return Response(
            content=r.content,
            media_type=r.headers.get("content-type", "image/jpeg"),
            headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "public, max-age=86400"},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ошибка загрузки: {e}")
