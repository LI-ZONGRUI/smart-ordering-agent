// 本地开发可在被 Git 忽略的 .env.development.local 中覆盖；正式环境必须使用 HTTPS 合法域名。
export const FRAMEWORK_AGENT_BASE_URL = import.meta.env.VITE_FRAMEWORK_AGENT_BASE_URL || ''
