import { marked } from 'marked'

marked.setOptions({
  breaks: true,
  gfm: true,
})

export function renderMarkdown(raw: string): string {
  return marked.parse(raw) as string
}
