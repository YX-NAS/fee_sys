<template>
  <el-container class="layout-container">
    <!-- 侧边栏 -->
    <el-aside :width="collapsed ? '64px' : '220px'" class="sidebar">
      <div class="logo" @click="collapsed = !collapsed">
        <el-icon size="22"><Money /></el-icon>
        <span v-if="!collapsed" class="logo-text">费用管理系统</span>
      </div>
      <el-menu
        :default-active="route.path"
        router
        :collapse="collapsed"
        background-color="#001529"
        text-color="#ffffffa0"
        active-text-color="#ffffff"
      >
        <el-menu-item index="/dashboard">
          <el-icon><DataAnalysis /></el-icon>
          <template #title>概览</template>
        </el-menu-item>
        <el-menu-item index="/accounts">
          <el-icon><UserFilled /></el-icon>
          <template #title>账号管理</template>
        </el-menu-item>
        <el-menu-item index="/transactions">
          <el-icon><Tickets /></el-icon>
          <template #title>费用流水</template>
        </el-menu-item>
        <el-menu-item index="/alerts">
          <el-icon><Bell /></el-icon>
          <template #title>提醒中心</template>
        </el-menu-item>
        <el-menu-item index="/analytics">
          <el-icon><TrendCharts /></el-icon>
          <template #title>费用分析</template>
        </el-menu-item>
        <el-menu-item index="/budgets">
          <el-icon><Wallet /></el-icon>
          <template #title>预算管理</template>
        </el-menu-item>
        <el-menu-item v-if="auth.isAdmin" index="/users">
          <el-icon><Setting /></el-icon>
          <template #title>用户管理</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- 主内容区 -->
    <el-container direction="vertical">
      <el-header class="header">
        <div class="header-left">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item>{{ currentTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-badge :value="notifStore.unreadCount || undefined" :max="99" class="notif-badge">
            <el-icon size="20" class="notif-icon" @click="showNotifDrawer = true"><Bell /></el-icon>
          </el-badge>
          <el-dropdown @command="handleCmd">
            <span class="user-info">
              <el-icon><Avatar /></el-icon>
              {{ auth.user?.username }}
              <el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>

  <!-- 通知抽屉 -->
  <el-drawer v-model="showNotifDrawer" title="站内通知" size="380px" direction="rtl">
    <NotificationPanel @close="showNotifDrawer = false" />
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notification'
import NotificationPanel from '@/components/NotificationPanel.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const notifStore = useNotificationStore()
const collapsed = ref(false)
const showNotifDrawer = ref(false)

const titleMap: Record<string, string> = {
  '/dashboard': '概览',
  '/accounts': '账号管理',
  '/transactions': '费用流水',
  '/alerts': '提醒中心',
  '/analytics': '费用分析',
  '/budgets': '预算管理',
  '/users': '用户管理',
}
const currentTitle = computed(() => titleMap[route.path] || '')

async function handleCmd(cmd: string) {
  if (cmd === 'logout') {
    auth.logout()
    router.push('/login')
  }
}

onMounted(() => {
  notifStore.fetchUnreadCount()
  // 每分钟刷新未读数
  setInterval(() => notifStore.fetchUnreadCount(), 60000)
})
</script>

<style scoped>
.layout-container { height: 100vh; }
.sidebar { background: #001529; transition: width 0.3s; overflow: hidden; }
.logo {
  height: 56px; display: flex; align-items: center; gap: 10px;
  padding: 0 20px; cursor: pointer; color: #fff; font-size: 16px; font-weight: bold;
}
.logo-text { white-space: nowrap; }
.header {
  background: #fff; display: flex; align-items: center; justify-content: space-between;
  padding: 0 20px; box-shadow: 0 1px 4px rgba(0,0,0,.08);
}
.header-right { display: flex; align-items: center; gap: 16px; }
.user-info { cursor: pointer; display: flex; align-items: center; gap: 4px; }
.notif-icon { cursor: pointer; color: #606266; }
.main-content { background: #f5f7fa; }
</style>
