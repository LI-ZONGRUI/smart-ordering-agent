<template>
  <view class="menu-page">
    <view class="menu-header">
      <view class="header-title">点餐菜单</view>
      <text class="muted">挑选喜欢的菜品</text>
    </view>

    <view class="menu-body">
      <scroll-view scroll-y class="category-scroll">
        <view
          v-for="category in categories"
          :key="category.id"
          class="category-item"
          :class="{ active: selectedCategoryId === category.id }"
          @click="selectCategory(category.id)"
        >
          {{ category.name }}
        </view>
      </scroll-view>

      <scroll-view scroll-y class="dish-scroll" :scroll-into-view="`dish-top-${selectedCategoryId}`">
        <view v-if="loading" class="empty-state">正在加载菜品...</view>
        <view v-else-if="loadError" class="empty-state">
          <view>{{ loadError }}</view>
          <button size="mini" class="retry-button" @click="loadMenu">重试</button>
        </view>
        <template v-else>
          <!-- 切换分类时，让右侧列表滚回当前分类的标题。 -->
          <view v-if="selectedCategory" :id="`dish-top-${selectedCategoryId}`" class="category-heading">
            {{ selectedCategory.name }}
          </view>

          <view v-if="categories.length === 0" class="empty-state">暂无分类，请先初始化云数据库</view>
          <view v-else-if="visibleDishes.length === 0" class="empty-state">当前分类暂无菜品</view>

          <view
            v-for="dish in visibleDishes"
            :key="dish.id"
            class="dish-card"
            @click="openDetail(dish)"
          >
            <image class="dish-image" :src="dish.image" mode="aspectFill" />
            <view class="dish-info">
              <view class="dish-name">{{ dish.name }}</view>
              <view class="dish-description">{{ dish.description }}</view>
              <view class="dish-meta">月售 {{ dish.sales }} · {{ spicyText(dish.spicyLevel) }}</view>
              <view class="dish-bottom">
                <text class="price">¥{{ dish.price.toFixed(2) }}</text>
                <text v-if="dish.status === 'sold_out'" class="sold-out">已售罄</text>
                <button
                  v-else
                  size="mini"
                  class="add-button"
                  @click.stop="addToCart(dish)"
                >+</button>
              </view>
            </view>
          </view>
        </template>
      </scroll-view>
    </view>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { spicyLevelLabels } from '../../constants/dish'
import { getCategories, getDishes } from '../../services/menu'
import { useCartStore } from '../../stores/cart'

const cartStore = useCartStore()
const categories = ref([])
const dishes = ref([])
const selectedCategoryId = ref('')
const loading = ref(false)
const loadError = ref('')

const selectedCategory = computed(() =>
  categories.value.find((category) => category.id === selectedCategoryId.value)
)

const visibleDishes = computed(() => {
  // “推荐”按 recommended 标记筛选；其他分类按菜品的 categoryId 筛选。
  if (selectedCategoryId.value === 'recommended') {
    return dishes.value.filter((dish) => dish.recommended && dish.status === 'on_sale')
  }
  return dishes.value.filter((dish) => dish.categoryId === selectedCategoryId.value)
})

onShow(loadMenu)

async function loadMenu() {
  loading.value = true
  loadError.value = ''
  try {
    const [categoriesResult, dishesResult] = await Promise.all([getCategories(), getDishes()])

    categories.value = categoriesResult
    dishes.value = dishesResult

    cartStore.syncDishes(dishesResult)
    if (!categoriesResult.some((category) => category.id === selectedCategoryId.value)) {
      selectedCategoryId.value = categoriesResult[0]?.id || ''
    }
  } catch (error) {
    console.error('[menu] load failed:', error)
    loadError.value = error?.message || '云端菜单加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function selectCategory(categoryId) {
  selectedCategoryId.value = categoryId
}

function spicyText(level) {
  return spicyLevelLabels[level] || '辣度未标注'
}

function openDetail(dish) {
  // 详情页不是 TabBar 页面，因此使用 navigateTo，并只传递菜品 id。
  uni.navigateTo({ url: `/pages/dish-detail/index?id=${dish.id}` })
}

function addToCart(dish) {
  const added = cartStore.addDish(dish)
  uni.showToast({ title: added ? '已加入购物车' : '菜品已售罄', icon: 'none' })
}
</script>

<style scoped>
.menu-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f7f8f5;
}

.menu-header {
  box-sizing: border-box;
  flex-shrink: 0;
  height: 116rpx;
  padding: 16rpx 28rpx;
  background: #ffffff;
}

.header-title {
  font-size: 34rpx;
  font-weight: 700;
}

.menu-header .muted {
  font-size: 22rpx;
}

.menu-body {
  display: flex;
  flex: 1;
  min-height: 0;
}

.category-scroll {
  flex-shrink: 0;
  width: 174rpx;
  height: 100%;
  background: #eef1eb;
}

.category-item {
  box-sizing: border-box;
  min-height: 106rpx;
  padding: 34rpx 12rpx;
  border-left: 6rpx solid transparent;
  color: #617064;
  text-align: center;
  font-size: 26rpx;
}

.category-item.active {
  border-left-color: #2d8055;
  background: #ffffff;
  color: #2d8055;
  font-weight: 700;
}

.dish-scroll {
  box-sizing: border-box;
  flex: 1;
  min-width: 0;
  height: 100%;
  padding: 0 18rpx 24rpx;
}

.category-heading {
  padding: 26rpx 2rpx 18rpx;
  font-size: 30rpx;
  font-weight: 700;
}

.dish-card {
  display: flex;
  margin-bottom: 18rpx;
  padding: 18rpx;
  border-radius: 18rpx;
  background: #ffffff;
}

.dish-image {
  flex-shrink: 0;
  width: 152rpx;
  height: 152rpx;
  margin-right: 16rpx;
  border-radius: 14rpx;
  background: #f0eadf;
}

.dish-info {
  flex: 1;
  min-width: 0;
}

.dish-name {
  overflow: hidden;
  font-size: 27rpx;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dish-description {
  overflow: hidden;
  margin-top: 8rpx;
  color: #728075;
  font-size: 21rpx;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dish-meta {
  margin-top: 9rpx;
  color: #879388;
  font-size: 20rpx;
}

.dish-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12rpx;
}

.add-button {
  width: 52rpx;
  height: 52rpx;
  margin: 0;
  padding: 0;
  border-radius: 50%;
  background: #2d8055;
  color: #ffffff;
  line-height: 49rpx;
  font-size: 36rpx;
}

.add-button::after {
  border: none;
}

.sold-out {
  color: #a0aaa2;
  font-size: 22rpx;
}

.empty-state {
  padding: 48rpx 0;
  color: #879388;
  text-align: center;
}

.retry-button {
  margin-top: 22rpx;
}
</style>
