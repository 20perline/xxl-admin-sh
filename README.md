# xxl-admin-sh
### 安装

> 要求python>=3.9

```shell
pip install xxl-admin-sh
```

安装成功后可直接用`xxl`进入程序

```shell
xxl
```


### 用法

首次使用会使用默认配置，退出后会自动保存到配置文件

#### 帮助命令

```shell
help
```
可显示所有可用命令

#### 配置命令

```shell
config env-set #设置环境配置
config list-clusters #当前环境可用集群列表
config add-cluster #添加集群到当前环境
config remove-cluster #从当前环境移除集群
```

#### 切换命令

```shell
goto prod #可切环境
goto prod cn #可切环境+集群
goto cn #可在当前环境切集群
```

可显示所有可用命令

#### 执行器列表

```shell
group list
group list -a #显示所有集群下面的
```

#### 任务列表

```shell
job list
job list xxx #模糊搜索
job list xxx -a #模糊搜索所有集群下面的
job list DemoJobHanlder #精确搜索
```


#### 任务执行

```shell
job run DemoJobHanlder
job run DemoJobHanlder -a #所有集群都执行
```


其它更多用法请查看帮助信息
```shell
xxx_command -h
```