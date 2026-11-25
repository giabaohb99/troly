// Lưu phiên Zalo (cookie, imei, userAgent) mã hóa AES-256-GCM bằng ZALO_SESSION_KEY.
import { createCipheriv, createDecipheriv, randomBytes } from 'node:crypto'
import { mkdir, readFile, rename, rm, writeFile } from 'node:fs/promises'
import path from 'node:path'

const AAD = Buffer.from('troly-zalo-session-v1')

export function encrypt(key, plain) {
  const iv = randomBytes(12)
  const cipher = createCipheriv('aes-256-gcm', key, iv)
  cipher.setAAD(AAD)
  const body = Buffer.concat([cipher.update(plain, 'utf8'), cipher.final()])
  return Buffer.concat([iv, cipher.getAuthTag(), body])
}

export function decrypt(key, blob) {
  const iv = blob.subarray(0, 12)
  const tag = blob.subarray(12, 28)
  const decipher = createDecipheriv('aes-256-gcm', key, iv)
  decipher.setAAD(AAD)
  decipher.setAuthTag(tag)
  return Buffer.concat([decipher.update(blob.subarray(28)), decipher.final()]).toString('utf8')
}

export class SessionStore {
  constructor(dataDir, key) {
    this.file = path.join(dataDir, 'session.enc')
    this.key = key
  }

  async save(credentials) {
    await mkdir(path.dirname(this.file), { recursive: true })
    const tmp = this.file + '.tmp'
    await writeFile(tmp, encrypt(this.key, JSON.stringify(credentials)), { mode: 0o600 })
    await rename(tmp, this.file)
  }

  // Trả null khi chưa có phiên; tệp hỏng hoặc sai khóa thì ném lỗi để người gọi báo và đăng nhập lại.
  async load() {
    let blob
    try {
      blob = await readFile(this.file)
    } catch (err) {
      if (err.code === 'ENOENT') return null
      throw err
    }
    return JSON.parse(decrypt(this.key, blob))
  }

  async clear() {
    await rm(this.file, { force: true })
  }
}
