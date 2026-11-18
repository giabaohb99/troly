// Khung tối thiểu (việc 0-06): gọi /api/health để thấy giao diện nối được máy chủ.
const box = document.getElementById('app')

fetch('/api/health')
  .then((res) => res.json())
  .then((body) => {
    box.textContent = `Trợ lý: máy chủ ${body.data.status}`
  })
  .catch(() => {
    box.textContent = 'Trợ lý: chưa nối được máy chủ'
  })
