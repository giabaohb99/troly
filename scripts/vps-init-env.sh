#!/usr/bin/env bash
# Tạo /opt/troly/.env lần đầu trên VPS (do scripts/vps-deploy.sh gọi khi chưa có .env). Không in giá trị bí mật.
# - Sinh mới: POSTGRES_PASSWORD, JWT_SECRET, TOKEN_ENCRYPTION_KEYS.
# - Chép (chỉ đọc) theo QĐ-31: R2_ACCOUNT_ID, R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY từ /opt/gamebar/.env;
#   R2_BUCKET đặt thành assistant. Không sửa tệp của Gamebar.
# - ANTHROPIC_API_KEY (QĐ-32, dùng chung khóa gym): đọc từ stdin nếu có (scripts/deploy.sh gửi nội dung
#   D:/giabao/keyapiclaude.txt qua SSH), không thì lấy từ /opt/gymcanhan/.env.
set -euo pipefail
cd /opt/troly
[ ! -e .env ] || { echo ".env đã có, không ghi đè."; exit 1; }

get_var() { # get_var <tệp> <tên>: in giá trị của dòng TÊN=..., rỗng nếu không có
  [ -r "$1" ] && sed -n "s/^$2=//p" "$1" | tail -1 | sed -e 's/^"//' -e 's/"$//' || true
}
rand() { head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c "$1"; }
fernet() { head -c 32 /dev/urandom | base64 | tr '+/' '-_'; }

ANTHROPIC_KEY=""
if [ ! -t 0 ]; then ANTHROPIC_KEY=$(tr -d '[:space:]' | sed 's/^ANTHROPIC_API_KEY=//'); fi
[ -n "$ANTHROPIC_KEY" ] || ANTHROPIC_KEY=$(get_var /opt/gymcanhan/.env ANTHROPIC_API_KEY)

PG_PASS=$(rand 32)
declare -A SET=(
  [ENV]=prod
  [PUBLIC_BASE_URL]=https://assistant.baohuynh.io.vn
  [POSTGRES_PASSWORD]="$PG_PASS"
  [DATABASE_URL]="postgresql+psycopg://troly:$PG_PASS@db:5432/troly"
  [JWT_SECRET]="$(rand 64)"
  [TOKEN_ENCRYPTION_KEYS]="v1:$(fernet)"
  [ZALO_SESSION_KEY]="$(head -c 32 /dev/urandom | base64)"
  [ZALO_BRIDGE_TOKEN]="$(rand 48)"
  [R2_BUCKET]=assistant
  [R2_ACCOUNT_ID]="$(get_var /opt/gamebar/.env R2_ACCOUNT_ID)"
  [R2_ENDPOINT]="$(get_var /opt/gamebar/.env R2_ENDPOINT)"
  [R2_ACCESS_KEY_ID]="$(get_var /opt/gamebar/.env R2_ACCESS_KEY_ID)"
  [R2_SECRET_ACCESS_KEY]="$(get_var /opt/gamebar/.env R2_SECRET_ACCESS_KEY)"
  [ANTHROPIC_API_KEY]="$ANTHROPIC_KEY"
)

umask 077
cp .env.example .env.new
for KEY in "${!SET[@]}"; do
  VAL="${SET[$KEY]}"
  ESC=$(printf '%s' "$VAL" | sed -e 's/[\/&|]/\\&/g')
  if grep -q "^$KEY=" .env.new; then
    sed -i "s|^$KEY=.*|$KEY=$ESC|" .env.new
  else
    printf '%s=%s\n' "$KEY" "$VAL" >> .env.new
  fi
done
mv .env.new .env
chmod 600 .env

MISSING=""
for KEY in R2_ENDPOINT R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY ANTHROPIC_API_KEY; do
  [ -n "${SET[$KEY]}" ] || MISSING="$MISSING $KEY"
done
echo "Đã tạo /opt/troly/.env (quyền 600)."
[ -z "$MISSING" ] || echo "Chưa có giá trị:$MISSING. Điền tay vào /opt/troly/.env rồi chạy lại deploy."
