const STORAGE_KEY = 'ordering_anonymous_client_id'

export function getClientId() {
  let clientId = uni.getStorageSync(STORAGE_KEY)
  if (typeof clientId === 'string' && /^anon-[a-z0-9-]{16,80}$/.test(clientId)) {
    return clientId
  }

  // 只用于开发阶段区分设备数据，不具备身份认证能力。
  clientId = `anon-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`
  uni.setStorageSync(STORAGE_KEY, clientId)
  return clientId
}
