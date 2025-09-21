<div align="center">
  <a href="https://v2.nonebot.dev/store"><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/nbp_logo.png" width="180" height="180" alt="NoneBotPluginLogo"></a>
  <br>
  <p><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/NoneBotPlugin.svg" width="240" alt="NoneBotPluginText"></p>
</div>

<div align="center">

# nonebot-plugin-savepic

_✨ 一个存取图片的插件 ✨_

</div>

## 📖 介绍

重写自 Fran 的 Savepic

### savepic

保存表情包

### randpic

抽取表情包

### mvpic

重命名表情包，或者修改表情包所属的群域

例如：

```
/mvpic -l name.jpg -g waaaaa.gif
```

就是把本群的 name.jpg 改成全局名为 waaaaa.gif 的表情包

同理

```
/mvpic -g waaaaa.gif -l waaaaa.gif
```

就是从全局移到本群（接收到命令的群）

### 直接发送文件名

发送文件名即可发送表情包

## ⚙️ 配置

在 nonebot2 项目的`.env`文件中添加下表中的必填配置

| 配置项 | 必填 | 默认值 | 说明 |
|:-----:|:----:|:----:|:----:|
| savepic_admin | 否 | 无 | 权限用户 |
| savepic_dir | 否 | savepic | 图片本地保存位置 |

## 🎉 使用

### 指令表

| 指令 | 权限 | 需要@ | 范围 | 说明 |
|:-----:|:----:|:----:|:----:|:----:|
| savepic | 群员 | 否 | 群聊 | 保存图片 |
| randpic | 群员 | 否 | 全部 | 随机图片 |
| mvpic | 管理员 | 否 | 群聊 | 重命名图片 |
