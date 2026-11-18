from html import escape
from typing import Literal

from fastapi import APIRouter, Depends, Header, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_device, get_current_user, get_device_or_user
from app.core.config import get_settings
from app.core.context import DeviceContext, UserContext
from app.core.db import get_session
from app.core.errors import ok
from app.core.ratelimit import limiter
from app.modules.device import service

router = APIRouter()
public_router = APIRouter()


class DeviceIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    manufacturer: str | None = Field(default=None, max_length=80)
    model: str | None = Field(default=None, max_length=80)
    os_version: str | None = Field(default=None, max_length=40)
    app_version_code: int | None = None
    app_version_name: str | None = Field(default=None, max_length=40)


class DevicePatch(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class HeartbeatIn(BaseModel):
    app_version_code: int | None = None
    app_version_name: str | None = Field(default=None, max_length=40)
    manufacturer: str | None = Field(default=None, max_length=80)
    default_sms_package: str | None = Field(default=None, max_length=200)
    notification_access: bool | None = None
    listener_connected: bool | None = None
    notifications_enabled: bool | None = None
    exact_alarm_allowed: bool | None = None
    battery_optimization_ignored: bool | None = None
    queue_size: int | None = Field(default=None, ge=0)
    otp_blocked_today: int | None = Field(default=None, ge=0)


class ListenedAppIn(BaseModel):
    package_name: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_.]+$")
    label: str = Field(min_length=1, max_length=80)
    purpose: Literal["expense", "inbox"]
    parser: Literal["vcb", "tcb", "momo", "zalo", "telegram", "messenger", "sms", "generic"]
    enabled: bool = True


class ListenedAppPatch(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=80)
    purpose: Literal["expense", "inbox"] | None = None
    parser: Literal["vcb", "tcb", "momo", "zalo", "telegram", "messenger", "sms", "generic"] | None = None
    enabled: bool | None = None


class EventsIn(BaseModel):
    # Từng sự kiện kiểm riêng ở service để một sự kiện hỏng không làm hỏng cả lô.
    events: list = Field(min_length=1, max_length=50)


@router.get("/devices/listened-apps")
def list_listened_apps(
    user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok({"items": service.list_listened_apps(session, user.user_id)})


@router.post("/devices/listened-apps", status_code=201)
def create_listened_app(
    body: ListenedAppIn,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.create_listened_app(session, user.user_id, body.model_dump()))


@router.patch("/devices/listened-apps/{app_id}")
def update_listened_app(
    app_id: int,
    body: ListenedAppPatch,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.update_listened_app(session, user.user_id, app_id, body.model_dump(exclude_unset=True)))


@router.delete("/devices/listened-apps/{app_id}")
def delete_listened_app(
    app_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    service.delete_listened_app(session, user.user_id, app_id)
    return ok(None)


@router.post("/device/events")
def post_events(
    body: EventsIn,
    device: DeviceContext = Depends(get_current_device),
    session: Session = Depends(get_session),
) -> dict:
    limiter.hit(
        f"device_events:{device.device_id}", get_settings().rate_device_events_per_min, 60, len(body.events)
    )
    return ok(service.ingest_events(session, device, body.events))


@router.get("/device/config")
def get_config(
    response: Response,
    if_none_match: str | None = Header(default=None),
    device: DeviceContext = Depends(get_current_device),
    session: Session = Depends(get_session),
):
    config = service.device_config(session, device.user_id)
    etag = f'"{config["revision"]}"'
    if if_none_match and if_none_match.removeprefix("W/").strip() == etag:
        return Response(status_code=304, headers={"ETag": etag})
    response.headers["ETag"] = etag
    return ok(config)


@router.get("/devices")
def list_devices(
    user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok({"items": service.list_devices(session, user.user_id)})


@router.post("/devices", status_code=201)
def register_device(
    body: DeviceIn, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.register(session, user.user_id, body.model_dump()))


@router.patch("/devices/{device_id}")
def rename_device(
    device_id: int,
    body: DevicePatch,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.rename(session, user.user_id, device_id, body.name))


@router.delete("/devices/{device_id}")
def revoke_device(
    device_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    service.revoke(session, user.user_id, device_id)
    return ok(None)


@router.post("/device/heartbeat")
def post_heartbeat(
    body: HeartbeatIn,
    device: DeviceContext = Depends(get_current_device),
    session: Session = Depends(get_session),
) -> dict:
    return ok(
        service.heartbeat(session, device.user_id, device.device_id, body.model_dump(exclude_unset=True))
    )


@router.get("/device/release")
def get_release(
    current_version_code: int | None = None, _: UserContext = Depends(get_device_or_user)
) -> dict:
    return ok(service.release_info(current_version_code))


_PAGE = """<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:640px;margin:2rem auto;padding:0 1rem;line-height:1.6;
background:#111;color:#eee}}a{{color:#7cc4ff}}code{{word-break:break-all}}</style></head><body>{body}</body></html>"""


@public_router.get("/chinh-sach-rieng-tu", response_class=HTMLResponse)
def privacy_page() -> str:
    body = """<h1>Chính sách riêng tư của Trợ lý</h1>
<p>Trợ lý là app cá nhân của một người dùng. Dữ liệu chỉ phục vụ chính người dùng đó.</p>
<h2>Dữ liệu thu</h2><ul><li>Tin chat với trợ lý, ghi chú, hồ sơ cá nhân do người dùng nhập.</li>
<li>Khoản chi nhập tay hoặc đọc từ thông báo ngân hàng (chỉ số tiền và 4 số cuối tài khoản, không lưu số dư).</li>
<li>Tin nhắn hiện trên thông báo của các app người dùng chọn; tin chứa mã OTP bị bỏ ngay trên điện thoại.</li>
<li>Lịch, việc, thư, danh bạ của tài khoản Google khi người dùng tự kết nối.</li></ul>
<h2>Gửi tới đâu</h2><ul><li>Anthropic (Claude API) để trả lời khi người dùng hỏi.</li>
<li>Google khi đồng bộ lịch, việc, thư theo quyền người dùng cấp.</li>
<li>Cloudflare (R2) để lưu tệp và bản sao lưu, bucket riêng tư.</li></ul>
<h2>Giữ bao lâu</h2><ul><li>Tin nhắn của người khác: 180 ngày.</li><li>Lịch sử chat: 365 ngày.</li>
<li>Bản sao lưu: 5 bản gần nhất.</li></ul>
<p>Muốn xóa dữ liệu hoặc ngắt kết nối Google, dùng màn Cài đặt trong app.</p>"""
    return _PAGE.format(title="Chính sách riêng tư", body=body)


@public_router.get("/tai-app", response_class=HTMLResponse)
def download_page() -> str:
    info = service.release_info(None)
    latest = info["latest"]
    if latest is None:
        body = "<h1>Tải app Trợ lý</h1><p>Chưa có bản phát hành.</p>"
    else:
        body = f"""<h1>Tải app Trợ lý {escape(str(latest["version_name"]))}</h1>
<p><a href="{escape(latest["download_url"])}">Tải tệp APK</a> (liên kết sống 5 phút, tải lại trang nếu hết hạn).</p>
<p>SHA-256: <code>{escape(str(latest["sha256"]))}</code></p>
<h2>Cài trên Galaxy S25+</h2><ol>
<li>Mở tệp vừa tải, cho phép trình duyệt <em>Cài ứng dụng không rõ nguồn gốc</em>, rồi bấm Cài đặt.</li>
<li>Vào Cài đặt &gt; Ứng dụng &gt; Trợ lý &gt; menu ba chấm &gt; <em>Cho phép cài đặt bị hạn chế</em>.</li>
<li>Cài đặt &gt; Pin và chăm sóc thiết bị &gt; Pin &gt; Giới hạn sử dụng nền &gt; <em>Ứng dụng không bao giờ ngủ</em>
&gt; thêm Trợ lý.</li>
<li>Nếu máy chặn cài từ nguồn ngoài, cài bằng <code>adb install</code> từ máy tính.</li></ol>"""
    return _PAGE.format(title="Tải app Trợ lý", body=body)
