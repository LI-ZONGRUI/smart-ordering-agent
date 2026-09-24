// 固定12条管理评测；不配置URL化、定时器或微信页面入口。
exports.main = async function (event, context) {
  if (context?.SOURCE !== 'server') {
    return { errCode: 'ANSWER_EVAL_FORBIDDEN', errMsg: '请在 HBuilderX 上传并运行管理评测云函数' }
  }
  try {
    const rag = uniCloud.importObject('rag')
    // 不转发 event，不能通过参数替换评测集或标签。
    return await rag.evaluateAnswers()
  } catch {
    return { errCode: 'ANSWER_EVAL_CALL_FAILED', errMsg: 'Answer 评测未完整完成，请检查部署与云函数日志' }
  }
}
