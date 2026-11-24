import { useEffect, useState } from 'react'
import { api, type Citation } from './api'

type Page = { page: number; page_count: number; image: string; boxes: { x: number; y: number; w: number; h: number }[] }

export function PdfViewer({ source, token, lang, close }: { source: Citation; token: string; lang: 'ar' | 'en'; close: () => void }) {
  const [number, setNumber] = useState(source.page_number)
  const [page, setPage] = useState<Page>()
  const [error, setError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    setPage(undefined)
    setError('')
    const query = number === source.page_number ? '?chunk_id=' + source.chunk_id : ''
    api<Page>('/documents/' + source.document_id + '/pages/' + number + query, token, { signal: controller.signal })
      .then(result => { if (!controller.signal.aborted) setPage(result) })
      .catch(cause => { if (!controller.signal.aborted) setError(String(cause)) })
    return () => controller.abort()
  }, [number, source, token])
  const ar = lang === 'ar'
  return <section className="pdf-viewer" aria-label={ar ? 'عارض المستند' : 'PDF viewer'}>
    <header><strong>{source.filename}</strong><button onClick={close}>{ar ? 'إغلاق' : 'Close'}</button></header>
    <div className="pdf-controls">
      <button disabled={number <= 1 || !page} onClick={() => setNumber(n => n - 1)}>{ar ? 'السابق' : 'Previous'}</button>
      <span>{number} / {page?.page_count ?? '…'}</span>
      <button disabled={!page || number >= page.page_count} onClick={() => setNumber(n => n + 1)}>{ar ? 'التالي' : 'Next'}</button>
      <button onClick={() => setNumber(source.page_number)}>{ar ? 'المصدر' : 'Citation page'}</button>
    </div>
    {error && <p role="alert">{error}</p>}
    {!page && !error && <p>{ar ? 'جارٍ التحميل' : 'Loading page'}</p>}
    {page && <>
      <div className="pdf-sheet" dir="ltr">
        <img alt={(ar ? 'صفحة ' : 'Page ') + number} src={'data:image/png;base64,' + page.image}/>
        {page.boxes.map((b, i) => <span key={i} className="pdf-highlight" style={{ left: b.x * 100 + '%', top: b.y * 100 + '%', width: b.w * 100 + '%', height: b.h * 100 + '%' }}/>)}
      </div>
      {number === source.page_number && !page.boxes.length && <p>{ar ? 'تعذر تحديد موضع النص بدقة؛ تم فتح الصفحة دون تظليل.' : 'Exact text location unavailable; showing the source page without highlights.'}</p>}
    </>}
  </section>
}
