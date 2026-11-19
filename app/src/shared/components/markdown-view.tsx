import { Fragment, type ReactNode } from 'react'
import { openWebLink } from '@/shared/components/rich-text'
import { parseInline, parseMarkdown } from '@/shared/utils/markdown'

function Inline({ text }: { text: string }): ReactNode {
  return parseInline(text).map((t, i) => {
    if (t.type === 'strong') return <strong key={i}>{t.value}</strong>
    if (t.type === 'em') return <em key={i}>{t.value}</em>
    if (t.type === 'code')
      return (
        <code key={i} className="rounded bg-secondary px-1 py-0.5 text-[0.9em]">
          {t.value}
        </code>
      )
    if (t.type === 'link')
      return (
        <a
          key={i}
          href={t.href}
          onClick={(e) => {
            if (t.href.startsWith('http')) {
              e.preventDefault()
              openWebLink(t.href)
            }
          }}
          className="text-primary underline underline-offset-2"
        >
          {t.value}
        </a>
      )
    return <Fragment key={i}>{t.value}</Fragment>
  })
}

const HEADING = ['text-2xl', 'text-xl', 'text-lg', 'text-base', 'text-sm', 'text-sm']

// Tệp .md hiện dạng Markdown trong app (QĐ-44). Vẽ từ khối đã tách, không dùng HTML.
export function MarkdownView({ source }: { source: string }) {
  return (
    <div className="flex flex-col gap-3 text-[15px] leading-relaxed break-words">
      {parseMarkdown(source).map((block, i) => {
        switch (block.type) {
          case 'heading':
            return (
              <p key={i} role="heading" aria-level={block.level} className={`${HEADING[block.level - 1]} font-bold`}>
                <Inline text={block.text} />
              </p>
            )
          case 'paragraph':
            return (
              <p key={i} className="whitespace-pre-wrap">
                <Inline text={block.text} />
              </p>
            )
          case 'list': {
            const Tag = block.ordered ? 'ol' : 'ul'
            return (
              <Tag key={i} className={block.ordered ? 'list-decimal pl-6' : 'list-disc pl-6'}>
                {block.items.map((item, j) => (
                  <li key={j}>
                    <Inline text={item} />
                  </li>
                ))}
              </Tag>
            )
          }
          case 'quote':
            return (
              <blockquote key={i} className="border-l-4 border-primary/40 pl-3 whitespace-pre-wrap text-muted-foreground">
                <Inline text={block.text} />
              </blockquote>
            )
          case 'code':
            return (
              <pre key={i} className="overflow-x-auto rounded-xl bg-secondary p-3 text-sm">
                <code>{block.text}</code>
              </pre>
            )
          case 'hr':
            return <hr key={i} />
        }
      })}
    </div>
  )
}
