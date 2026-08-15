import networkx as nx
from backend.core.vk_client import VKClient


class GraphBuilder:
    def __init__(self, client: VKClient):
        self._client = client

    def build(self, user_id: int, deep: bool) -> nx.Graph:
        G = nx.Graph()

        # Корневой пользователь
        root = self._client.get_user(str(user_id))
        root_label = f"{root['first_name']} {root['last_name']}"
        G.add_node(user_id, label=root_label, photo=root.get("photo_50", ""), root=True)

        # Друзья root
        friends = self._client.get_friends(user_id)
        friend_ids: list[int] = []

        for f in friends:
            if f.get("is_closed") and f.get("id") == 0:
                continue
            fid = f["id"]
            label = f"{f.get('first_name', '')} {f.get('last_name', '')}".strip()
            G.add_node(fid, label=label, photo=f.get("photo_50", ""), root=False)
            G.add_edge(user_id, fid)
            friend_ids.append(fid)

        # Связи между друзьями
        mutual = self._client.get_mutual_friends(user_id, friend_ids)
        friend_set = set(friend_ids)

        for fid, common in mutual.items():
            for cid in common:
                if cid in friend_set and not G.has_edge(fid, cid):
                    G.add_edge(fid, cid)

        if not deep:
            return G

        # Режим friends of friends — берём топ-10 друзей по количеству общих связей
        # Сортируем по степени в текущем графе (кто больше всего связан с другими друзьями)
        top_friends = sorted(friend_ids, key=lambda fid: G.degree(fid), reverse=True)[:10]

        fof_seen: set[int] = set(friend_ids) | {user_id}

        for fid in top_friends:
            fof_list = self._client.get_friends(fid)
            fof_ids = []

            for f in fof_list:
                if f.get("is_closed") and f.get("id") == 0:
                    continue
                fof_id = f["id"]
                if fof_id in fof_seen:
                    continue
                label = f"{f.get('first_name', '')} {f.get('last_name', '')}".strip()
                G.add_node(fof_id, label=label, photo=f.get("photo_50", ""), root=False)
                G.add_edge(fid, fof_id)
                fof_ids.append(fof_id)
                fof_seen.add(fof_id)

            if fof_ids:
                mutual_fof = self._client.get_mutual_friends(fid, fof_ids)
                for fof_id, common in mutual_fof.items():
                    for cid in common:
                        if cid in fof_seen and not G.has_edge(fof_id, cid):
                            G.add_edge(fof_id, cid)

        return G
