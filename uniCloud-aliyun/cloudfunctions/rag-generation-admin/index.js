// 仅在 HBuilderX 手动“上传并运行”；不添加 URL 化、定时器或微信页面入口。
exports.main = async function (event, context) {
  if (context?.SOURCE !== 'server') {
    return { errCode: 'RAG_GENERATION_FORBIDDEN', errMsg: '请在 HBuilderX 中上传并运行管理诊断云函数' }
  }
  try {
    const rag = uniCloud.importObject('rag')
    // 不转发 event，调用者不能替换固定 Query、Prompt 或模型配置。
    return await rag.testRagGeneration()
  } catch {
    return { errCode: 'RAG_GENERATION_CALL_FAILED', errMsg: 'RAG Generation 调用未完成，请检查 rag 部署与远程配置' }
  }
}
