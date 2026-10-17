import { createApp } from 'vue'
import { ElIcon } from 'element-plus'
import 'element-plus/theme-chalk/base.css'
import 'element-plus/theme-chalk/el-icon.css'
import 'element-plus/theme-chalk/el-message.css'
import App from './App.vue'
import './styles.css'

createApp(App).component('ElIcon', ElIcon).mount('#app')
