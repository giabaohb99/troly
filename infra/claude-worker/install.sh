#!/usr/bin/env bash
# Cài trình chạy Claude Code lên VPS (QĐ-60). Chạy bằng root, gọi lại được nhiều lần (không đè khóa đã có).
# Cần sẵn: /tmp/claude-worker/{runner.py,claude-worker.service}; tùy chọn /tmp/claude-worker/oauth.env chứa
# CLAUDE_CODE_OAUTH_TOKEN=... (tạo bằng `claude setup-token` trên máy đại ca). Không in khóa ra màn hình.
set -euo pipefail
SRC=/tmp/claude-worker

# Người dùng claude: toàn quyền (sudo không mật khẩu, docker) theo lệnh của đại ca.
if ! id claude >/dev/null 2>&1; then
  useradd -m -s /bin/bash claude
fi
usermod -aG docker claude
echo 'claude ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/claude-worker
chmod 440 /etc/sudoers.d/claude-worker
visudo -cf /etc/sudoers.d/claude-worker >/dev/null

# Node từ kho Ubuntu, rồi Claude Code từ npm.
if ! command -v npm >/dev/null 2>&1; then
  DEBIAN_FRONTEND=noninteractive apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nodejs npm >/dev/null
fi
npm install -g @anthropic-ai/claude-code >/dev/null 2>&1
echo "Claude Code: $(claude --version 2>/dev/null || echo 'chưa chạy được')"

# Thư mục làm việc và lối tắt tới các app.
sudo -u claude mkdir -p /home/claude/work
for app in troly gymcanhan gamebar; do
  [ -e "/home/claude/work/$app" ] || ln -s "/opt/$app" "/home/claude/work/$app"
done
sudo -u claude git config --global user.name "Claude tren VPS" || true
sudo -u claude git config --global user.email "claude-worker@localhost" || true

# Khóa nội bộ api <-> trình chạy: sinh một lần, ghi vào .env của troly và tệp env của trình chạy.
install -d -m 750 -o root -g claude /etc/claude-worker
ENV=/etc/claude-worker/env
touch "$ENV"; chown root:claude "$ENV"; chmod 640 "$ENV"
if ! grep -qE '^CLAUDE_WORKER_TOKEN=.+' /opt/troly/.env; then
  sed -i '/^CLAUDE_WORKER_TOKEN=/d' /opt/troly/.env
  printf 'CLAUDE_WORKER_TOKEN=%s\n' "$(head -c 36 /dev/urandom | base64 -w0 | tr '+/' '-_')" >> /opt/troly/.env
fi
WTOKEN=$(grep -E '^CLAUDE_WORKER_TOKEN=' /opt/troly/.env | tail -1 | cut -d= -f2-)
grep -vE '^(CLAUDE_WORKER_TOKEN|TROLY_API)=' "$ENV" > "$ENV.tmp" || true
printf 'TROLY_API=http://127.0.0.1:8200/api/v1\nCLAUDE_WORKER_TOKEN=%s\n' "$WTOKEN" >> "$ENV.tmp"
if [ -f "$SRC/oauth.env" ]; then
  grep -vE '^CLAUDE_CODE_OAUTH_TOKEN=' "$ENV.tmp" > "$ENV.tmp2" || true
  grep -E '^CLAUDE_CODE_OAUTH_TOKEN=.+' "$SRC/oauth.env" | tail -1 >> "$ENV.tmp2"
  mv "$ENV.tmp2" "$ENV.tmp"
  shred -u "$SRC/oauth.env" 2>/dev/null || rm -f "$SRC/oauth.env"
  echo "Đã nạp token gói đăng ký."
fi
mv "$ENV.tmp" "$ENV"; chown root:claude "$ENV"; chmod 640 "$ENV"
unset WTOKEN

install -d -m 755 /opt/claude-worker
install -m 755 "$SRC/runner.py" /opt/claude-worker/runner.py
install -m 644 "$SRC/claude-worker.service" /etc/systemd/system/claude-worker.service
systemctl daemon-reload
systemctl enable --now claude-worker >/dev/null 2>&1
systemctl restart claude-worker
echo "claude-worker: $(systemctl is-active claude-worker)"
