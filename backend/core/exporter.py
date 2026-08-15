import json
import os
import networkx as nx
import plotly.graph_objects as go
import numpy as np


EXPORTS_DIR = "exports"


def _get_3d_positions(G: nx.Graph) -> dict:
    pos_2d = nx.spring_layout(G, seed=42, k=0.5)
    pos_3d = {}
    for node, (x, y) in pos_2d.items():
        # добавляем третью ось на основе степени узла
        z = np.log1p(G.degree(node)) * 0.3 + np.random.uniform(-0.1, 0.1)
        pos_3d[node] = (x, y, z)
    return pos_3d


def build_plotly_figure(G: nx.Graph) -> go.Figure:
    pos = _get_3d_positions(G)

    edge_x, edge_y, edge_z = [], [], []
    for u, v in G.edges():
        x0, y0, z0 = pos[u]
        x1, y1, z1 = pos[v]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]
        edge_z += [z0, z1, None]

    edge_trace = go.Scatter3d(
        x=edge_x, y=edge_y, z=edge_z,
        mode="lines",
        line=dict(color="rgba(100,100,255,0.3)", width=1),
        hoverinfo="none",
        name="",
    )

    node_x, node_y, node_z, node_text, node_size, node_color = [], [], [], [], [], []
    for node in G.nodes():
        x, y, z = pos[node]
        data = G.nodes[node]
        degree = G.degree(node)
        node_x.append(x)
        node_y.append(y)
        node_z.append(z)
        node_text.append(f"{data.get('label', str(node))}<br>Связей: {degree}")
        node_size.append(max(5, min(20, 5 + degree * 1.5)))
        node_color.append(degree)

    node_trace = go.Scatter3d(
        x=node_x, y=node_y, z=node_z,
        mode="markers",
        marker=dict(
            size=node_size,
            color=node_color,
            colorscale="Plasma",
            showscale=True,
            colorbar=dict(title="Связи", thickness=15),
            line=dict(width=0.5, color="white"),
        ),
        text=node_text,
        hoverinfo="text",
        name="",
    )

    fig = go.Figure(
        data=[edge_trace, node_trace],
        layout=go.Layout(
            showlegend=False,
            hovermode="closest",
            paper_bgcolor="#0d0d1a",
            scene=dict(
                bgcolor="#0d0d1a",
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                zaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            ),
            margin=dict(l=0, r=0, t=0, b=0),
        ),
    )
    return fig


def export_json(G: nx.Graph, filename: str) -> str:
    data = {
        "nodes": [
            {"id": n, **G.nodes[n], "degree": G.degree(n)}
            for n in G.nodes()
        ],
        "edges": [{"source": u, "target": v} for u, v in G.edges()],
        "stats": {
            "nodes": G.number_of_nodes(),
            "edges": G.number_of_edges(),
        },
    }
    path = os.path.join(EXPORTS_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def export_graphml(G: nx.Graph, filename: str) -> str:
    path = os.path.join(EXPORTS_DIR, filename)
    nx.write_graphml(G, path)
    return path


def export_png(G: nx.Graph, filename: str) -> str:
    fig = build_plotly_figure(G)
    path = os.path.join(EXPORTS_DIR, filename)
    fig.write_html(path.replace(".png", ".html"))
    # fallback: сохраняем как HTML если kaleido не работает
    try:
        import kaleido
        fig.write_image(path, width=1920, height=1080)
    except Exception:
        path = path.replace(".png", ".html")
    return path