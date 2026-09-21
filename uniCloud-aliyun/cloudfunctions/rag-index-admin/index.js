// 仅作为 HBuilderX 手动“上传并运行”的管理入口；不配置 URL 化或定时触发器。
exports.main = async function (event, context) {
  // 检查平台上下文，不读取 event.clientInfo，客户端传参不能获得管理权限。
  if (context?.SOURCE !== 'server') {
    return { errCode: 'INDEX_FORBIDDEN', errMsg: '请在 HBuilderX 中手动上传并运行此管理云函数' }
  }
  try {
    const rag = uniCloud.importObject('rag')
    return await rag.buildKnowledgeIndex()
  } catch (error) {
    // SDK 可能把非零 errCode 转成异常。只提取索引器的安全统计，不透传原始异常。
    const counts = ['total', 'inserted', 'updated', 'skipped', 'failed', 'orphanCount']
    if (error?.errCode === 'INDEX_PARTIAL_FAILURE' &&
        counts.every(key => Number.isSafeInteger(error[key]) && error[key] >= 0)) {
      const result = { errCode: 'INDEX_PARTIAL_FAILURE', errMsg: '索引部分失败，请核查后重跑。' }
      for (const key of counts) result[key] = error[key]
      const validId = id => typeof id === 'string' && /^[a-zA-Z0-9_-]+$/.test(id)
      result.orphanScanComplete = error.orphanScanComplete === true
      result.orphanKnowledgeIds = Array.isArray(error.orphanKnowledgeIds) ? error.orphanKnowledgeIds.filter(validId) : []
      const codes = new Set(['INDEX_TIME_BUDGET', 'INDEX_WRITE_FAILED', 'INDEX_EMBEDDING_REQUEST_FAILED',
        'INDEX_EMBEDDING_HTTP_ERROR', 'INDEX_EMBEDDING_RESPONSE_INVALID', 'INDEX_EMBEDDING_INDEX_INVALID',
        'INDEX_EMBEDDING_VECTOR_INVALID', 'INDEX_EMBEDDING_FAILED'])
      result.failures = Array.isArray(error.failures) ? error.failures
        .filter(item => validId(item?.knowledgeId) && codes.has(item.code))
        .map(item => ({ knowledgeId: item.knowledgeId, code: item.code })) : []
      return result
    }
    return { errCode: 'INDEX_ADMIN_CALL_FAILED', errMsg: '未取得完整索引统计，不代表成功。请检查 rag 部署、变量及数据库；核查记录后重跑。' }
  }
}
