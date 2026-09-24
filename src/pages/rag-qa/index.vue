<template>
  <view class="page">
    <view class="title">菜单问答</view>
    <view class="intro muted">问问菜品口味、配料和介绍，每次回答一个问题。</view>
    <view class="card">
      <textarea v-model="query" class="question-input" :maxlength="-1" :disabled="loading"
        placeholder="例如：有什么比较清爽的？" />
      <view class="counter muted">{{ queryLength }}/200</view>
      <view class="examples">
        <button v-for="example in examples" :key="example" class="example-chip" size="mini"
          :disabled="loading" @click="fillExample(example)">{{ example }}</button>
      </view>
      <button class="primary-button" :disabled="loading" :loading="loading" @click="submit">
        {{ loading ? '查询中...' : '提问' }}
      </button>
    </view>

    <view v-if="loading" class="card muted">正在查找菜单信息，请稍候。</view>
    <view v-if="errorMessage" class="card">
      <view class="error-text">{{ errorMessage }}</view>
      <button class="retry-button" :disabled="loading" @click="submit">重新提问</button>
    </view>
    <template v-if="result">
      <view class="card">
        <view class="section-title">回答</view>
        <!-- true 和 false 都展示服务器原文；正常拒答不是技术错误。 -->
        <text class="answer-text">{{ result.answer }}</text>
      </view>
      <view v-if="result.answerable && result.evidence.length" class="card">
        <view class="section-title">依据</view>
        <view v-for="(item, index) in result.evidence" :key="index" class="evidence-item">
          <view class="evidence-title">{{ item.title }}</view>
          <text class="evidence-text muted">{{ item.text }}</text>
        </view>
      </view>
      <view v-if="relatedDishes.length || dishesError" class="card">
        <view class="section-title">相关菜品</view>
        <view v-if="dishesError" class="muted">{{ dishesError }}</view>
        <view v-for="dish in relatedDishes" :key="dish.id" class="dish-row" @click="goToDetail(dish)">
          <image :src="dish.image" class="dish-image" mode="aspectFill" />
          <view class="dish-info">
            <view class="dish-name">{{ dish.name }}</view>
            <view class="price">¥{{ dish.price.toFixed(2) }}</view>
            <view class="muted">{{ dish.status === 'on_sale' ? '在售' : '售罄' }}</view>
            <view class="detail-link">查看详情</view>
          </view>
        </view>
      </view>
    </template>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { answerMenuQuestion } from '../../services/rag'
import { getDishes } from '../../services/menu'

const query = ref('')
const loading = ref(false)
const result = ref(null)
const errorMessage = ref('')
const relatedDishes = ref([])
const dishesError = ref('')
const queryLength = computed(() => Array.from(query.value).length)
const examples = ['有什么比较清爽的？', '我想吃牛肉', '有什么饮料？', '拍黄瓜是什么口感？']

function fillExample(example) {
  if (!loading.value) query.value = example // 只填文本，不自动消耗云端请求。
}

async function submit() {
  if (loading.value) return
  errorMessage.value = ''
  result.value = null
  relatedDishes.value = []
  dishesError.value = ''
  loading.value = true
  try {
    result.value = await answerMenuQuestion(query.value)
    if (result.value.answerable && result.value.dishIds.length) {
      let menuTimer
      try {
        // 价格和状态只取现有菜单服务的实时数据，不能从回答或依据里提取。
        const dishes = await Promise.race([
          getDishes(),
          new Promise((resolve, reject) => {
            menuTimer = setTimeout(() => reject(new Error('timeout')), 15000)
          })
        ])
        relatedDishes.value = [...new Set(result.value.dishIds)]
          .map(id => dishes.find(dish => dish.id === id))
          .filter(dish => dish && typeof dish.name === 'string' &&
            typeof dish.price === 'number' && Number.isFinite(dish.price) && dish.price >= 0 &&
            ['on_sale', 'sold_out'].includes(dish.status))
      } catch {
        // 菜单刷新失败不抹掉已经成功取得的回答。
        dishesError.value = '相关菜品暂时加载失败，可稍后重新提问。'
      } finally {
        clearTimeout(menuTimer)
      }
    }
  } catch (error) {
    result.value = null
    errorMessage.value = error.message // service 仅抛出固定友好文案。
  } finally {
    loading.value = false
  }
}

function goToDetail(dish) {
  uni.navigateTo({ url: `/pages/dish-detail/index?id=${encodeURIComponent(dish.id)}` })
}
</script>

<style scoped>
.intro { margin: 16rpx 0 28rpx; }
.question-input { box-sizing: border-box; width: 100%; height: 180rpx; line-height: 1.6; }
.counter { text-align: right; margin: 12rpx 0; }
.examples { display: flex; flex-wrap: wrap; gap: 12rpx; margin-bottom: 24rpx; }
.example-chip { margin: 0; color: #2d8055; background: #eef5ef; font-size: 24rpx; }
.answer-text, .evidence-text { display: block; white-space: pre-wrap; line-height: 1.8; overflow-wrap: anywhere; }
.evidence-item + .evidence-item { margin-top: 24rpx; }
.evidence-title { margin-bottom: 8rpx; font-weight: 600; }
.error-text { color: #a63e2b; }
.retry-button { margin-top: 20rpx; }
.dish-row { display: flex; gap: 20rpx; padding: 20rpx 0; }
.dish-image { width: 140rpx; height: 140rpx; border-radius: 16rpx; flex-shrink: 0; }
.dish-info { flex: 1; min-width: 0; line-height: 1.6; }
.dish-name { font-weight: 600; }
.detail-link { color: #2d8055; font-size: 24rpx; }
</style>
