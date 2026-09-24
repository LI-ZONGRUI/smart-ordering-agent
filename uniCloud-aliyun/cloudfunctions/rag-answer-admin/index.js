// 仅供 HBuilderX 上传并运行，不配置 URL 化、定时器或前端入口。
exports.main = async function (event, context) {
  if (context?.SOURCE !== 'server') {
    return { errCode: 'RAG_ANSWER_FORBIDDEN', errMsg: '请通过 HBuilderX 执行管理测试' }
  }
  try {
    const rag = uniCloud.importObject('rag')
    // 只转发 query；校验由正式接口统一完成，不接受环境变量或 Prompt 覆盖。
    return await rag.answer(event?.query)
  } catch {
    return { errCode: 'RAG_ANSWER_CALL_FAILED', errMsg: 'RAG 调用未完成，请检查部署与配置' }
  }
}
