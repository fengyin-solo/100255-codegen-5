<template>
  <RenovationListPage
    mode="proposal"
    title="改造项目立项单"
    desc="立项人只能修改本人提交的改造项目；审核岗可通过或退回（退回必须写明理由）。批复后预算锁定，投运后整单只读。"
    empty-text="当前没有编制中、待审核或已退回的改造项目"
    :options="['编制中', '待审核', '已退回', '已批复']"
  />
</template>

<script setup lang="ts">
import RenovationListPage from './RenovationListPage.vue'
</script>
