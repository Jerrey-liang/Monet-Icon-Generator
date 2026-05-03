<div align="center">

# HyperOS桌面莫奈图标生成器

简体中文&nbsp;&nbsp;|&nbsp;&nbsp;[English (Trans. by ChatGPT)](/README_en.md)

</div>

## 📖 脚本说明

### 功能实现

- [x] 支持开启 深色模式切换图标样式
- [x] 支持选择 `圆角矩形` 与 `圆形` 图标
- [x] 支持 `日历图标` 显示真实日期
- [x] 支持一键打包 `icons`，并生成 `面具模块` 或 `mtz主题包`

### 功能优化
- [x] 进度条显示处理进度
- [x] 通过 ADB 获取当前 Monet 颜色配置
- [x] 预览颜色配置
- [x] 颜色配置有效性校验、一定程度自动修复
- [x] 使用 `theme_fallback.xml` 优化成品包文件体积
- [x] `name_mapping_by_MrBocchi.json` 修复与补充了一些图标（你也可以自行补充）

### 弊端

`icons` 图标包并不支持动态莫奈取色 `@android:color/system_accent1_*`，所以需要在生成前通过 ADB 获取当前莫奈颜色配置（方法在后文会给出），并且推荐 **每次更换壁纸后重新执行【功能1】并重新生成/应用相关文件**。

## 🖼️ 预览

### 脚本界面总览

<img src="docs/overview.png" alt="Overview" width="50%">

### 成品预览

<img src="docs/preview.jpg" alt="Preview">

## 🛠️ 使用说明

### 0. 基础准备

  - 手机端需解锁 Bootloader 并获取 root 权限

  - 电脑端需安装 [Android SDK Platform Tools](https://developer.android.com/tools/releases/platform-tools)，并确保 `adb` 可在 PowerShell 中直接运行

  - 手机端需开启 USB 调试，连接电脑后允许调试授权

  - 脚本运行需 Python 环境，并已安装 Pillow 库

```
pip install Pillow
```

### 1. 获取手机当前 Monet 颜色配置

运行脚本后选择 `功能1`，脚本会通过 ADB 读取手机当前的 `system_accent1_*` 颜色，并自动写入 `colors.json`。

如果获取失败，请先在 PowerShell 中执行：

```
adb devices
```

确认设备状态为 `device` 后，再重新执行 `功能1`。

`功能1` 内部使用的 ADB 查询逻辑等价于下面这段 PowerShell：

```powershell
$tones = @(0, 10, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000)

foreach ($t in $tones) {
    $name = "system_accent1_$t"
    $value = adb shell cmd overlay lookup android "android:color/$name"
    $value = $value.Trim()
    Write-Output "$name = $value"
}
```

### 2. 运行脚本

```
python main.py
```
按照功能名称指示，逐个执行 `功能1~4`。/ `功能5、6` 为可选步骤。

### 3. 图标包的使用

`功能1~4` 执行结束后，根目录会生成 `icons` 文件。

你有三种选择：

1. 【推荐】直接使用

   (1) 这里需要你先应用一个随机主题（不应用主题此方法貌似不会生效）

   (2) 然后使用 [MT管理器](https://mt2.cn/) 将 `icons` 复制至手机的 `/data/system/theme/` 目录

   (3) 赋予 `icons` 完整 **读取权限**（在属性面板中）

   (4) 重启桌面（可以直接使用 MT管理器，在安装包提取界面重启；或者使用 [Hyperceiler](https://github.com/Xposed-Modules-Repo/com.sevtinge.hyperceiler) 一键重启）

2. 使用 `功能5` 打包成面具模块

   (1) 在 `Magisk` 或 `其他root管理器` 中直接刷入。

      - 刷入 `KernelSU` 如果没效果，在 `超级用户` 界面内找到 `系统桌面 com.miui.home` 的 `App Profile` 内，（**不用** 授权超级用户权限），在下方切换成 `自定义`，并且关闭 `卸载模块`。重启桌面。

   (2) 刷入后重启手机。

3. 使用 `功能6` 打包成 mtz 主题包

   使用主题破解模块，导入并应用主题。

## 🧩 工作原理

HyperOS 的图标包本质是一个无后缀名、名为 `icons` 的压缩文件。

- 默认的 `icons` 位于 `/system/media/theme/default/` 目录下
- 当前在使用的主题的 `icons` 存放于 `/data/system/theme/` 目录下
- mtz 主题包内，`icons` 存放于 mtz 根目录

### 1. `自动切换深色模式` 功能原理

`自动切换深色模式` 功能，即：跟随系统深色/浅色模式自动切换深浅图标。

文件目录结构：
```
icons/
  ├─ transform_config.xml
  └─ fancy_icons/
      ├─ com.tencent.mm/
      │   ├─ iconBg_0.png
      │   ├─ iconBg_1.png
      │   └─ manifest.xml   // 用于提供图标切换功能
      ├─ com.coolapk.market/
      │   ├─ iconBg_0.png
      │   ├─ iconBg_1.png
      │   └─ manifest.xml
      └─ ...
```
方案由 [酷安@阿尼亚超爱吃花生](http://www.coolapk.com/u/10895092) 收集

### 2. `theme_fallback.xml` 原理

为了优化最终 `icons` 图标包的文件体积，在关闭 `自动切换深色模式` 功能情况下¹，本项目使用了 `theme_fallback.xml` 映射图标文件。多个应用使用相同图标时，仅需存放一份图标文件。

此时的文件目录结构：
```
icons/
  ├─ theme_fallback.xml
  ├─ transform_config.xml
  └─ res/
      └─ drawable-xxhdpi/
            ├─ wechat.png
            ├─ coolapk.png
            └─ ...
```

图片的实际名称即为 Lawnicons 项目中图标的原始文件名。

`theme_fallback.xml` 文件内部结构：
```
<?xml version='1.0' encoding='utf-8' standalone='yes'?>
<MIUI_Theme_Values>
  <drawable name="com.tencent.mm.png">wechat.png</drawable>
  <drawable name="com.coolapk.market.png">coolapk.png</drawable>
  <drawable name="com.example.c001apk.png">coolapk.png</drawable>
  ...
</MIUI_Theme_Values>
```

注¹：开启 `自动切换深色模式` 功能时，没法使用 `theme_fallback.xml`。

### 3. 图标 Monet 取色原理

在 Android 12+ 系统中，`@android:color/` 下提供了一整套 `system_accent*` 与 `system_neutral*` 动态取色资源，系统会根据壁纸自动生成并切换。

本项目在绘制图标前景与背景时，使用了其中的 `accent1` 系列：

- 浅色模式：前景 `accent1_700`，背景 `accent1_100`
- 深色模式：前景 `accent1_200`，背景 `accent1_700`

### 4. `Lawnicons` 更新同步

脚本启动时会自动检查 [Lawnicons 发行版](https://github.com/LawnchairLauncher/lawnicons/releases) 的最新稳定版。

当检测到本地 `lawnicons_assets/version.json` 记录的版本低于最新稳定版时，脚本会自动完成以下流程：

1. 下载最新稳定版 APK 与对应源码包。
2. 从 APK 的 `resources.arsc` 与二进制 XML 中还原 `appfilter_plain.xml`。
3. 从源码包的 `svgs` 目录生成 215px 透明 PNG 图标，并打包为 `drawable.zip`。
4. 校验 `appfilter_plain.xml` 中引用的 drawable 名称是否都能在 `drawable.zip` 中找到。
5. 校验通过后，备份旧资源到 `lawnicons_assets/backup/`，再替换：
   - `lawnicons_assets/appfilter_plain.xml`
   - `lawnicons_assets/drawable.zip`
   - `lawnicons_assets/version.json`
6. 清理旧缓存，避免继续使用旧图标素材。

如果 `lawnicons_assets/appfilter_plain.xml` 或 `lawnicons_assets/drawable.zip` 被删除、损坏，脚本启动时会自动重新下载 Lawnicons 稳定版 APK 与源码包，并重新生成这些资源文件。

如果网络不可用、下载失败、解析失败或图标对应关系校验失败，脚本会保留现有本地资源并继续运行，不会用不完整的新资源覆盖旧文件。

如需临时跳过自动检查，可在运行前设置环境变量：

```powershell
$env:MONET_SKIP_LAWNICONS_UPDATE = "1"
python main.py
```

## 💖 特别感谢

[Lawnicons 项目主页](https://github.com/LawnchairLauncher/lawnicons)
