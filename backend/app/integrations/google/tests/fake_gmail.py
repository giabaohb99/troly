"""Gmail giả cho bài kiểm: hộp thư, lịch sử (historyId), luồng thư, nháp. Đủ hành vi mà gmail.py dựa vào."""

import base64
import json
import re
import time
import uuid

import httpx


def err(status: int, reason: str = "", message: str = "") -> httpx.Response:
    return httpx.Response(
        status, json={"error": {"code": status, "message": message, "errors": [{"reason": reason}]}}
    )


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


class FakeGmail:
    def __init__(self):
        self.messages: dict[str, dict] = {}
        self.drafts: dict[str, dict] = {}
        self.history: list[tuple[int, str]] = []  # (historyId, message_id) thêm vào INBOX
        self.history_id = 1000
        self.min_history = 0  # startHistoryId nhỏ hơn số này thì 404 như Gmail
        self.sent: list[dict] = []

    # ---------- tiện ích bài kiểm ----------

    def add_mail(
        self,
        *,
        subject: str = "Chào",
        sender: str = "Lan <lan@example.com>",
        to: str = "dai.ca@gmail.com",
        text: str = "Nội dung thư",
        labels: tuple[str, ...] = ("INBOX", "CATEGORY_PERSONAL"),
        thread_id: str | None = None,
        html: str | None = None,
        at_ms: int = 1795000000000,
        message_id_header: str | None = None,
    ) -> str:
        mid = f"m{uuid.uuid4().hex[:10]}"
        self.history_id += 1
        self.messages[mid] = {
            "id": mid,
            "threadId": thread_id or f"t{mid[1:]}",
            "labelIds": list(labels),
            "snippet": text[:100],
            "internalDate": str(at_ms),
            "historyId": str(self.history_id),
            "headers": {
                "From": sender,
                "To": to,
                "Subject": subject,
                "Date": "Thu, 19 Nov 2026 08:00:00 +0700",
                "Message-ID": message_id_header or f"<{mid}@mail.example.com>",
            },
            "text": text,
            "html": html,
        }
        if "INBOX" in labels:
            self.history.append((self.history_id, mid))
        return mid

    def edit_draft(self, draft_id: str, body: str) -> None:
        """Giả người dùng sửa nháp trên web Gmail."""
        raw = base64.urlsafe_b64decode(self.drafts[draft_id]["raw"] + "==").decode()
        head, _, _ = raw.partition("\n\n")
        self.drafts[draft_id]["raw"] = base64.urlsafe_b64encode(f"{head}\n\n{body}\n".encode()).decode()

    def draft_text(self, draft_id: str) -> str:
        return base64.urlsafe_b64decode(self.drafts[draft_id]["raw"] + "==").decode()

    # ---------- định tuyến ----------

    def handle(self, request: httpx.Request, path: str) -> httpx.Response:
        path = path.removeprefix("/gmail/v1/users/me")
        method = request.method
        params = request.url.params
        if path == "/profile":
            return httpx.Response(
                200, json={"emailAddress": "dai.ca@gmail.com", "historyId": str(self.history_id)}
            )
        if path == "/history":
            return self._history(params)
        if path == "/messages" and method == "GET":
            return self._list(params)
        if m := re.fullmatch(r"/messages/([^/]+)", path):
            item = self.messages.get(m.group(1))
            if item is None:
                return err(404, "notFound")
            return httpx.Response(200, json=self._public(item, params.get("format", "full"), params))
        if m := re.fullmatch(r"/threads/([^/]+)", path):
            items = [x for x in self.messages.values() if x["threadId"] == m.group(1)]
            if not items:
                return err(404, "notFound")
            fmt = params.get("format", "full")
            return httpx.Response(
                200, json={"id": m.group(1), "messages": [self._public(x, fmt, params) for x in items]}
            )
        if path == "/drafts" and method == "POST":
            body = json.loads(request.content)
            did = f"r{uuid.uuid4().hex[:8]}"
            self.drafts[did] = {**body["message"], "message_id": f"m{uuid.uuid4().hex[:10]}"}
            return httpx.Response(200, json=self._draft(did))
        if path == "/drafts/send" and method == "POST":
            did = json.loads(request.content)["id"]
            draft = self.drafts.pop(did, None)
            if draft is None:
                return err(404, "notFound")
            self.sent.append(draft)
            tid = draft.get("threadId") or f"t{uuid.uuid4().hex[:8]}"
            return httpx.Response(
                200, json={"id": draft["message_id"], "threadId": tid, "labelIds": ["SENT"]}
            )
        if m := re.fullmatch(r"/drafts/([^/]+)", path):
            did = m.group(1)
            if did not in self.drafts:
                return err(404, "notFound")
            if method == "GET":
                d = self._draft(did)
                d["message"]["raw"] = self.drafts[did]["raw"]
                return httpx.Response(200, json=d)
            if method == "PUT":
                body = json.loads(request.content)
                self.drafts[did].update(body["message"])
                return httpx.Response(200, json=self._draft(did))
            if method == "DELETE":
                del self.drafts[did]
                return httpx.Response(204)
        return err(404, "notFound")

    def _draft(self, did: str) -> dict:
        d = self.drafts[did]
        return {
            "id": did,
            "message": {"id": d["message_id"], "threadId": d.get("threadId") or d["message_id"]},
        }

    def _public(self, item: dict, fmt: str, params) -> dict:
        out = {k: item[k] for k in ("id", "threadId", "labelIds", "snippet", "internalDate", "historyId")}
        headers = [{"name": k, "value": v} for k, v in item["headers"].items()]
        if fmt == "metadata":
            wanted = {h.lower() for h in params.get_list("metadataHeaders")}
            out["payload"] = {"headers": [h for h in headers if h["name"].lower() in wanted]}
            return out
        parts = [{"mimeType": "text/plain", "body": {"data": _b64(item["text"])}}]
        if item.get("html"):
            parts = [{"mimeType": "text/html", "body": {"data": _b64(item["html"])}}]
        out["payload"] = {"mimeType": "multipart/alternative", "headers": headers, "parts": parts}
        return out

    def _list(self, params) -> httpx.Response:
        q = params.get("q", "")
        items = sorted(self.messages.values(), key=lambda x: int(x["internalDate"]), reverse=True)
        if "in:inbox" in q:
            items = [x for x in items if "INBOX" in x["labelIds"]]
        if m := re.search(r"newer_than:(\d+)d", q):
            floor = (time.time() - int(m.group(1)) * 86400) * 1000
            items = [x for x in items if int(x["internalDate"]) > floor]
        if m := re.search(r"after:(\d+)", q):
            items = [x for x in items if int(x["internalDate"]) // 1000 > int(m.group(1))]
        if "-in:spam" in q:
            items = [x for x in items if not {"SPAM", "TRASH"} & set(x["labelIds"])]
        if m := re.search(r"\{(.*)\}", q):  # nhóm HOẶC của Gmail: from:x subject:"y"
            terms = re.findall(r'(from|subject):("[^"]+"|\S+)', m.group(1))

            def hit(x: dict) -> bool:
                for field, value in terms:
                    value = value.strip('"').lower()
                    header = x["headers"]["From" if field == "from" else "Subject"].lower()
                    if value in header:
                        return True
                return False

            items = [x for x in items if hit(x)]
            q = q.replace(m.group(0), "")
        words = [w for w in q.split() if ":" not in w]
        for w in words:
            items = [x for x in items if w.lower() in (x["headers"]["Subject"] + x["text"]).lower()]
        for w in re.findall(r"from:(\S+)", q):
            items = [x for x in items if w.lower() in x["headers"]["From"].lower()]
        start = int(params.get("pageToken", "0"))
        size = int(params.get("maxResults", "100"))
        page = items[start : start + size]
        body: dict = {"messages": [{"id": x["id"], "threadId": x["threadId"]} for x in page]}
        if start + size < len(items):
            body["nextPageToken"] = str(start + size)
        return httpx.Response(200, json=body)

    def _history(self, params) -> httpx.Response:
        start = int(params["startHistoryId"])
        if start < self.min_history:
            return err(404, "notFound", "Requested entity was not found.")
        added = [(h, mid) for h, mid in self.history if h > start]
        history = [{"id": str(h), "messagesAdded": [{"message": {"id": mid}}]} for h, mid in added]
        return httpx.Response(200, json={"history": history, "historyId": str(self.history_id)})
