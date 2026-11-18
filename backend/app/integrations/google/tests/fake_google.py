"""Máy chủ Google giả trong bộ nhớ, cắm vào httpx.MockTransport (70 mục 3.6).

Hành vi bám tài liệu Google: syncToken và 410, If-Match và 412, id đặt sẵn và 409, events.instances,
watch, Tasks `updatedMin`/`showDeleted`, điểm token với invalid_grant. Không gọi mạng thật.
"""

import base64
import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs

import httpx

CLIENT_ID = "client-test.apps.googleusercontent.com"


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(at: datetime) -> str:
    return at.isoformat().replace("+00:00", "Z")


def _id_token(sub: str, email: str, aud: str = CLIENT_ID) -> str:
    def part(obj: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()

    return f"{part({'alg': 'RS256'})}.{part({'sub': sub, 'email': email, 'aud': aud, 'iss': 'https://accounts.google.com'})}.sig"


def _err(status: int, reason: str = "", message: str = "") -> httpx.Response:
    return httpx.Response(
        status, json={"error": {"code": status, "message": message, "errors": [{"reason": reason}]}}
    )


class FakeGoogle:
    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.forced: list[httpx.Response] = []  # trả lần lượt trước mọi xử lý
        # OAuth
        self.codes: dict[str, dict] = {}
        self.refresh_tokens: dict[str, str] = {}  # refresh -> sub
        self.access_tokens: dict[str, datetime] = {}
        self.revoked: list[str] = []
        self.granted_scope = ""
        # Calendar
        self.seq = 0
        self.events: dict[str, dict] = {}
        self.min_valid_token = 0
        self.channels: dict[str, dict] = {}
        self.stopped: list[str] = []
        self.default_reminders: list[dict] = [{"method": "popup", "minutes": 30}]
        # Drive
        self.drive_files: dict[str, dict] = {}
        self.permissions: list[dict] = []
        self.upload_sessions: dict[str, dict] = {}
        # Tasks
        self.lists: dict[str, dict] = {}
        self.tasks: dict[str, dict[str, dict]] = {}

    # ---------- tiện ích cho bài kiểm ----------

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def issue_code(
        self, sub: str = "sub-1", email: str = "dai.ca@gmail.com", scope: str | None = None
    ) -> str:
        code = f"code-{uuid.uuid4().hex[:8]}"
        self.codes[code] = {"sub": sub, "email": email, "scope": scope}
        return code

    def new_access(self, ttl: int = 3600) -> str:
        token = f"at-{uuid.uuid4().hex[:10]}"
        self.access_tokens[token] = _now() + timedelta(seconds=ttl)
        return token

    def put_event(self, event: dict) -> dict:
        """Thêm hoặc sửa sự kiện như người dùng sửa trên Google Calendar."""
        self.seq += 1
        current = self.events.get(event["id"], {})
        merged = {**current, **event, "_seq": self.seq, "etag": f'"e{self.seq}"', "updated": _iso(_now())}
        merged.setdefault("status", "confirmed")
        self.events[event["id"]] = merged
        return merged

    def cancel_event(self, event_id: str) -> None:
        self.put_event({"id": event_id, "status": "cancelled"})

    def expire_sync_tokens(self) -> None:
        self.min_valid_token = self.seq + 1

    def put_task(self, list_id: str, task: dict) -> dict:
        current = self.tasks[list_id].get(task["id"], {})
        merged = {
            **current,
            **task,
            "etag": f'"t{uuid.uuid4().hex[:6]}"',
            "updated": _iso(_now() + timedelta(seconds=1)),
        }
        self.tasks[list_id][task["id"]] = merged
        return merged

    def calls(self, method: str, pattern: str) -> list[httpx.Request]:
        return [
            r for r in self.requests if r.method == method and re.search(pattern, r.url.host + r.url.path)
        ]

    # ---------- bộ định tuyến ----------

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.forced:
            return self.forced.pop(0)
        url = request.url
        path = url.path
        if url.host == "oauth2.googleapis.com":
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            if path == "/token":
                return self._token(form)
            if path == "/revoke":
                self.revoked.append(form.get("token", ""))
                self.refresh_tokens.pop(form.get("token", ""), None)
                return httpx.Response(200, json={})
        auth = request.headers.get("authorization", "").removeprefix("Bearer ")
        expires = self.access_tokens.get(auth)
        if expires is None or expires < _now():
            return _err(401, "authError")
        if url.host == "www.googleapis.com" and (
            path.startswith("/drive/v3") or path.startswith("/upload/drive/v3")
        ):
            return self._drive(request, path)
        if url.host == "www.googleapis.com" and path.startswith("/calendar/v3"):
            return self._calendar(request, path.removeprefix("/calendar/v3"))
        if url.host == "tasks.googleapis.com":
            return self._tasks(request, path.removeprefix("/tasks/v1"))
        return _err(404, "notFound")

    def _token(self, form: dict) -> httpx.Response:
        if form.get("grant_type") == "authorization_code":
            info = self.codes.pop(form.get("code", ""), None)
            if info is None or not form.get("code_verifier"):
                return httpx.Response(400, json={"error": "invalid_grant"})
            refresh = f"rt-{uuid.uuid4().hex[:10]}"
            self.refresh_tokens[refresh] = info["sub"]
            scope = info["scope"] if info["scope"] is not None else self.granted_scope
            return httpx.Response(
                200,
                json={
                    "access_token": self.new_access(),
                    "expires_in": 3599,
                    "refresh_token": refresh,
                    "scope": scope,
                    "id_token": _id_token(info["sub"], info["email"]),
                    "token_type": "Bearer",
                },
            )
        if form.get("grant_type") == "refresh_token":
            if form.get("refresh_token") not in self.refresh_tokens:
                return httpx.Response(
                    400,
                    json={
                        "error": "invalid_grant",
                        "error_description": "Token has been expired or revoked.",
                    },
                )
            return httpx.Response(200, json={"access_token": self.new_access(), "expires_in": 3599})
        return httpx.Response(400, json={"error": "unsupported_grant_type"})

    # ---------- Calendar ----------

    def _calendar(self, request: httpx.Request, path: str) -> httpx.Response:
        method = request.method
        if path == "/channels/stop" and method == "POST":
            body = json.loads(request.content)
            self.stopped.append(body["id"])
            self.channels.pop(body["id"], None)
            return httpx.Response(204)
        if path.startswith("/users/me/calendarList/") and method == "GET":
            return httpx.Response(200, json={"defaultReminders": self.default_reminders})
        m = re.fullmatch(r"/calendars/([^/]+)/events(?:/([^/]+))?(?:/(instances|watch))?", path)
        if not m:
            return _err(404, "notFound")
        _, event_id, sub = m.groups()
        if event_id == "watch" and sub is None:
            event_id, sub = None, "watch"
        params = dict(request.url.params)
        if sub == "watch":
            body = json.loads(request.content)
            expiration = int((_now() + timedelta(days=7)).timestamp() * 1000)
            self.channels[body["id"]] = {
                **body,
                "resourceId": f"res-{body['id'][:6]}",
                "expiration": expiration,
            }
            return httpx.Response(
                200,
                json={"id": body["id"], "resourceId": f"res-{body['id'][:6]}", "expiration": str(expiration)},
            )
        if sub == "instances":
            return self._instances(event_id, params)
        if event_id is None and method == "GET":
            return self._list(params)
        if event_id is None and method == "POST":
            body = json.loads(request.content)
            new_id = body.get("id") or uuid.uuid4().hex
            if new_id in self.events:
                return _err(409, "duplicate", "The requested identifier already exists.")
            body["id"] = new_id
            body["organizer"] = {"self": True}
            self._conference(body, params)
            return httpx.Response(200, json=self._public(self.put_event(body)))
        event = self.events.get(event_id)
        if event is None or (event.get("status") == "cancelled" and method != "GET"):
            return _err(404, "notFound")
        if_match = request.headers.get("if-match")
        if if_match and if_match != event["etag"]:
            return _err(412, "conditionNotMet", "Precondition Failed")
        if method == "GET":
            return httpx.Response(200, json=self._public(event))
        if method == "PATCH":
            body = json.loads(request.content)
            self._conference(body, params)
            return httpx.Response(200, json=self._public(self.put_event({**body, "id": event_id})))
        if method == "DELETE":
            self.cancel_event(event_id)
            return httpx.Response(204)
        return _err(405, "methodNotAllowed")

    def _conference(self, body: dict, params: dict) -> None:
        """Như Google: chỉ tạo Meet khi có conferenceDataVersion=1, không thì bỏ qua conferenceData."""
        request = (body.get("conferenceData") or {}).get("createRequest")
        if not request:
            return
        if params.get("conferenceDataVersion") != "1":
            body.pop("conferenceData")
            return
        code = request["requestId"][-3:].rjust(3, "x")
        uri = f"https://meet.google.com/abc-defg-{code}"
        body["conferenceData"] = {
            "createRequest": {**request, "status": {"statusCode": "success"}},
            "entryPoints": [{"entryPointType": "video", "uri": uri}],
        }
        body["hangoutLink"] = uri

    @staticmethod
    def _public(event: dict) -> dict:
        return {k: v for k, v in event.items() if not k.startswith("_")}

    def _list(self, params: dict) -> httpx.Response:
        if "syncToken" in params and any(
            k in params for k in ("timeMin", "timeMax", "orderBy", "q", "updatedMin")
        ):
            return _err(400, "invalid")
        if "syncToken" in params:
            since = int(params["syncToken"].removeprefix("tok-"))
            if since < self.min_valid_token:
                return _err(410, "fullSyncRequired", "Sync token is no longer valid")
            items = [e for e in self.events.values() if e["_seq"] > since]
        else:
            items = [
                e
                for e in self.events.values()
                if e.get("status") != "cancelled" or params.get("showDeleted") == "true"
            ]
        items.sort(key=lambda e: e["_seq"])
        start = int(params.get("pageToken", "0"))
        size = int(params.get("maxResults", "250"))
        page = items[start : start + size]
        body: dict = {"items": [self._public(e) for e in page]}
        if start + size < len(items):
            body["nextPageToken"] = str(start + size)
        else:
            body["nextSyncToken"] = f"tok-{self.seq}"
        return httpx.Response(200, json=body)

    def _instances(self, master_id: str, params: dict) -> httpx.Response:
        if master_id not in self.events:
            return _err(404, "notFound")
        at = params["timeMin"]
        start = datetime.fromisoformat(at.replace("Z", "+00:00")) + timedelta(minutes=1)
        stamp = start.strftime("%Y%m%dT%H%M%SZ")
        inst_id = f"{master_id}_{stamp}"
        if inst_id not in self.events:
            self.put_event(
                {
                    "id": inst_id,
                    "recurringEventId": master_id,
                    "originalStartTime": {"dateTime": _iso(start)},
                    "start": {"dateTime": _iso(start)},
                    "end": {"dateTime": _iso(start + timedelta(hours=1))},
                    "summary": self.events[master_id].get("summary"),
                }
            )
        return httpx.Response(200, json={"items": [self._public(self.events[inst_id])]})

    # ---------- Drive ----------

    def _new_drive_file(self, meta: dict, size: int) -> dict:
        fid = f"drv-{uuid.uuid4().hex[:8]}"
        item = {
            "id": fid,
            "name": meta.get("name"),
            "mimeType": meta.get("mimeType"),
            "parents": meta.get("parents", []),
            "size": size,
            "webViewLink": f"https://drive.google.com/file/d/{fid}/view",
        }
        self.drive_files[fid] = item
        return item

    @staticmethod
    def _fields(item: dict, params: dict) -> dict:
        wanted = [f for f in params.get("fields", "id").split(",") if f]
        return {k: item[k] for k in wanted if k in item}

    def _drive(self, request: httpx.Request, path: str) -> httpx.Response:
        method = request.method
        params = dict(request.url.params)
        if path == "/upload/drive/v3/files" and params.get("uploadType") == "multipart":
            raw = request.content
            boundary = request.headers["content-type"].split("boundary=")[1]
            parts = raw.split(f"--{boundary}".encode())
            meta = json.loads(parts[1].split(b"\r\n\r\n", 1)[1].strip())
            data = parts[2].split(b"\r\n\r\n", 1)[1][: -len(b"\r\n")]
            return httpx.Response(200, json=self._fields(self._new_drive_file(meta, len(data)), params))
        if path == "/upload/drive/v3/files" and params.get("uploadType") == "resumable" and method == "POST":
            sid = uuid.uuid4().hex[:8]
            self.upload_sessions[sid] = {"meta": json.loads(request.content), "params": params}
            location = (
                f"https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&upload_id={sid}"
            )
            return httpx.Response(200, headers={"Location": location})
        if path == "/upload/drive/v3/files" and method == "PUT":
            sess = self.upload_sessions.pop(params["upload_id"])
            item = self._new_drive_file(sess["meta"], len(request.content))
            return httpx.Response(200, json=self._fields(item, sess["params"]))
        if path == "/drive/v3/files" and method == "POST":
            return httpx.Response(
                200, json=self._fields(self._new_drive_file(json.loads(request.content), 0), params)
            )
        parts = path.removeprefix("/drive/v3/files/").split("/")
        item = self.drive_files.get(parts[0])
        if item is None:
            return _err(404, "notFound")
        if len(parts) == 1 and method == "GET":
            return httpx.Response(200, json=self._fields(item, params))
        if len(parts) == 2 and parts[1] == "permissions" and method == "POST":
            body = json.loads(request.content)
            self.permissions.append({"file_id": item["id"], **body, "params": params})
            return httpx.Response(200, json={"id": f"perm-{len(self.permissions)}"})
        return _err(405, "methodNotAllowed")

    # ---------- Tasks ----------

    def _tasks(self, request: httpx.Request, path: str) -> httpx.Response:
        method = request.method
        if path == "/users/@me/lists" and method == "POST":
            body = json.loads(request.content)
            list_id = f"list-{uuid.uuid4().hex[:6]}"
            self.lists[list_id] = {"id": list_id, "title": body["title"]}
            self.tasks[list_id] = {}
            return httpx.Response(200, json=self.lists[list_id])
        m = re.fullmatch(r"/lists/([^/]+)/tasks(?:/([^/]+))?", path)
        if not m or m.group(1) not in self.tasks:
            return _err(404, "notFound")
        list_id, task_id = m.groups()
        bucket = self.tasks[list_id]
        if task_id is None and method == "GET":
            params = dict(request.url.params)
            items = list(bucket.values())
            if "updatedMin" in params:
                since = datetime.fromisoformat(params["updatedMin"].replace("Z", "+00:00"))
                items = [
                    t for t in items if datetime.fromisoformat(t["updated"].replace("Z", "+00:00")) >= since
                ]
            if params.get("showDeleted") != "true":
                items = [t for t in items if not t.get("deleted")]
            return httpx.Response(200, json={"items": items})
        if task_id is None and method == "POST":
            body = json.loads(request.content)
            new_id = f"task-{uuid.uuid4().hex[:6]}"
            return httpx.Response(200, json=self.put_task(list_id, {**body, "id": new_id}))
        task = bucket.get(task_id)
        if task is None or task.get("deleted"):
            return _err(404, "notFound")
        if method == "PATCH":
            body = json.loads(request.content)
            return httpx.Response(200, json=self.put_task(list_id, {**body, "id": task_id}))
        if method == "DELETE":
            self.put_task(list_id, {"id": task_id, "deleted": True})
            return httpx.Response(204)
        return _err(405, "methodNotAllowed")
