// 仅供 HBuilderX 开发者手动“上传并运行”；不配置 URL 化、定时器或前端入口。
exports.main = async function (event, context) {
  if (context?.SOURCE !== 'server') {
    return { errCode: 'ROBUSTNESS_FORBIDDEN', errMsg: '请在 HBuilderX 中上传并运行管理评测云函数' }
  }
  try {
    const rag = uniCloud.importObject('rag')
    // 不转发 event，固定评测集由云端资源决定。
    return await rag.evaluateRobustness()
  } catch {
    return { errCode: 'ROBUSTNESS_CALL_FAILED', errMsg: 'Robustness 评测未完整完成，请检查 rag 部署与远程配置' }
  }
}
