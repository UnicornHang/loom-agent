import { ConfigProvider, App as AntApp } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import 'antd/dist/reset.css'
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN} theme={{ token: { colorPrimary: "#506ba8", borderRadius: 8, fontFamily: "DM Sans, Noto Sans SC, sans-serif" } }}><AntApp><App /></AntApp></ConfigProvider>
  </React.StrictMode>,
)

