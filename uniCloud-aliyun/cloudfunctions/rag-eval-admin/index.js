// 开发者手动“上传并运行”的只读评测入口，不添加 URL 化、定时器或微信页面入口。
exports.main = async function (event, context) {
  if (context?.SOURCE !== 'server') {
    return { errCode: 'EVAL_FORBIDDEN', errMsg: '请在 HBuilderX 中上传并运行管理评测云函数' }
  }
  try {
    const rag = uniCloud.importObject('rag')
    return await rag.evaluateRetrieval()
  } catch (error) {
    const knownCodes = ['EVAL_FORBIDDEN', 'EVAL_DATASET_INVALID', 'EVAL_CORPUS_MISMATCH', 'EVAL_LABELS_INVALID',
      'EVAL_RESULT_INVALID', 'EVAL_EMBEDDING_FAILED', 'EVAL_EMBEDDING_INVALID', 'EVAL_FAILED']
    return { errCode: knownCodes.includes(error?.errCode) ? error.errCode : 'EVAL_CALL_FAILED',
      errMsg: '评测未完整完成，请检查 rag 部署、固定数据集、知识库和远程环境变量；不要将其视为成功结果' }
  }
}
