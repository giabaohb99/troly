import { RichText } from '@/shared/components/rich-text'
import { splitTables } from '@/shared/utils/text-tables'

// Chữ trả lời: giữ xuống dòng, in đậm **...**, link và số điện thoại bấm được (QĐ-44); bảng Markdown vẽ thành bảng
// thật, rộng hơn khung thì kéo ngang. Không dựng HTML.
export function MessageText({ text }: { text: string }) {
  return (
    <>
      {splitTables(text).map((part, i) =>
        part.type === 'text' ? (
          <span key={i} className="block">
            <RichText text={part.value} />
          </span>
        ) : (
          <span key={i} className="my-2 block overflow-x-auto rounded-lg border">
            <table className="w-full border-collapse text-sm whitespace-normal">
              <thead className="bg-secondary">
                <tr>
                  {part.header.map((h, j) => (
                    <th key={j} className="border-b px-2.5 py-1.5 text-left font-semibold">
                      <RichText text={h} />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {part.rows.map((row, r) => (
                  <tr key={r} className="border-b last:border-b-0">
                    {row.map((cell, j) => (
                      <td key={j} className="px-2.5 py-1.5 align-top">
                        <RichText text={cell} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </span>
        ),
      )}
    </>
  )
}
