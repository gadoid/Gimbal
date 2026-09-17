import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './styles/theme.css'
import './styles/composer.css'
import './styles/tailwind.css'

import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
