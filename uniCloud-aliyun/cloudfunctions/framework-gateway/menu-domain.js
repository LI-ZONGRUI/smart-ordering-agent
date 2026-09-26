// HBuilderX部署时由公共模块依赖提供；Node本地测试使用源码回退。不要在Gateway复制查询逻辑。
try {
  module.exports = require('menu-read-domain')
} catch (error) {
  if (error?.code !== 'MODULE_NOT_FOUND' || !String(error.message).includes("'menu-read-domain'")) throw error
  module.exports = require('../common/menu-read-domain')
}
