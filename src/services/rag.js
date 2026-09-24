const UNAVAILABLE = '暂时无法获取回答，请稍后重试。'

export async function answerMenuQuestion(query) {
  // 前端校验只改善输入体验；服务端仍会独立校验。
  if (typeof query !== 'string' || !query.trim()) throw new Error('请输入问题')
  const text = query.trim()
  if (Array.from(text).length > 200) throw new Error('问题请控制在 200 字以内')
  let timer
  try {
    const rag = uniCloud.importObject('rag', { customUI: true })
    // 有限等待，不打印 SDK 原始异常；超时后的旧请求结果不会重新写入页面。
    const response = await Promise.race([
      rag.answer(text),
      new Promise((resolve, reject) => {
        timer = setTimeout(() => reject(new Error('timeout')), 60000)
      })
    ])
    if (response?.errCode === 'RAG_QUERY_INVALID') {
      const error = new Error('invalid query')
      error.errCode = 'RAG_QUERY_INVALID'
      throw error
    }
    if (response?.errCode !== 0 || typeof response.answerable !== 'boolean' ||
        typeof response.answer !== 'string' || !Array.isArray(response.dishIds) ||
        !response.dishIds.every(id => typeof id === 'string') ||
        !Array.isArray(response.usedKnowledgeIds) || !response.usedKnowledgeIds.every(id => typeof id === 'string') ||
        !Array.isArray(response.evidence) || response.evidence.some(e => !e ||
          typeof e.title !== 'string' || typeof e.text !== 'string')) throw new Error('invalid response')
    // 只取页面需要的字段，不把完整云端响应、诊断分数或向量带入页面。
    return { answerable: response.answerable, answer: response.answer,
      dishIds: response.dishIds, usedKnowledgeIds: response.usedKnowledgeIds,
      evidence: response.evidence.map(({ title, text }) => ({ title, text })) }
  } catch (error) {
    if (error?.errCode === 'RAG_QUERY_INVALID') throw new Error('问题格式不正确，请重新输入')
    throw new Error(UNAVAILABLE)
  } finally {
    clearTimeout(timer)
  }
}
