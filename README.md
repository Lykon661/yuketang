雨课堂刷课脚本

致谢 / Credits

本项目基于 Cat1007/yuketangHelperSCUTLite 进行二次开发和改进。

原项目地址：[Cat1007/yuketangHelperSCUTLite](https://github.com/Cat1007/yuketangHelperSCUTLite)

改进内容：新增加了讨论区自动复制他人评论回复功能，新增利用ai自动答题功能

#### 使用方法：

1. 安装好python环境

2. 安装pip（最好换一下国内的镜像源）[参考](https://blog.csdn.net/yuzaipiaofei/article/details/80891108)

3. 克隆或下载该仓库

4. 安装vscode以及vscode的python插件，并根据提示使用pip安装所需要的包

   ![image-20210419085901386](https://gitee.com/cat1007/markdown-pics/raw/master/uPic/image-20210419085901386.png)

5. 打开浏览器，登录云课堂并获取对应的cookie  [参考](https://blog.csdn.net/lenfranky/article/details/90316262)

6. 修改 `videoHelper.py` 源代码并填入你自己的值
   
7. 如果需要使用考试自动答题需进入考试页面后按F12在网络中获取x_access_token，若考试内容涉及时政等最新消息需为LLM配置一个search api帮助LLM答题（建议使用免费的https://api.tavily.com/search）

8. 右上角绿色三角点击运行

8. 终端按提示输入对应的课程编号并回车
