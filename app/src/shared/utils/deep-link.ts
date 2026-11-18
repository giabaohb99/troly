// Đường dẫn sâu troly://<đường dẫn> sang đường dẫn trong app. troly://chat/<id>?tin=<id> (notice chat_done của máy
// chủ, QĐ-41) đổi sang màn chat /?phien=<id>&tin=<id>; còn lại giữ nguyên.
export function deepLinkToRoute(path: string): string {
  const chat = path.match(/^chat\/(\d+)\/?(?:\?(.*))?$/)
  if (chat) return `/?phien=${chat[1]}${chat[2] ? `&${chat[2]}` : ''}`
  return `/${path}`
}
