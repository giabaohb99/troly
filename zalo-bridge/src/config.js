// Đọc cấu hình từ biến môi trường (docs/50-ha-tang mục 3.15).

export function loadConfig(env = process.env) {
  const sessionKey = Buffer.from(env.ZALO_SESSION_KEY || '', 'base64')
  if (sessionKey.length !== 32) {
    throw new Error('ZALO_SESSION_KEY phải là 32 byte mã base64.')
  }
  if (!env.ZALO_BRIDGE_TOKEN || env.ZALO_BRIDGE_TOKEN.length < 24) {
    throw new Error('ZALO_BRIDGE_TOKEN phải có từ 24 ký tự.')
  }
  const r2Host = hostOf(env.R2_ENDPOINT)
  return {
    port: Number(env.PORT || 3000),
    dataDir: env.ZALO_DATA_DIR || '/data',
    sessionKey,
    token: env.ZALO_BRIDGE_TOKEN,
    eventsUrl: env.ZALO_EVENTS_URL || 'http://api:8000/api/v1/internal/zalo/events',
    sendPerMinute: Number(env.ZALO_SEND_PER_MINUTE || 20),
    sendQueueMax: 5,
    attachmentHosts: (env.ZALO_ATTACHMENT_HOSTS || r2Host || '')
      .split(',').map((h) => h.trim().toLowerCase()).filter(Boolean),
    userAgent: env.ZALO_USER_AGENT ||
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    logLevel: env.LOG_LEVEL || 'INFO',
  }
}

function hostOf(url) {
  try {
    return url ? new URL(url).hostname : ''
  } catch {
    return ''
  }
}
