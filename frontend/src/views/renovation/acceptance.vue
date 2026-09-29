<template>
  <RenovationListPage
    mode="acceptance"
    title="改造项目投运验收"
    desc="仅验收岗可填写投运验收结论；已投运项目对其余岗位一律只读，验收结论不可再改。跨部门共同责任人可共享查看。"
    empty-text="当前没有实施中、待验收或已投运的改造项目"
    :options="['实施中', '待验收', '已投运']"
  />
</template>

<script setup lang="ts">
import RenovationListPage from './RenovationListPage.vue'
</script>
