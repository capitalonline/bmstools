# bmstools
bmstools是一个在首云裸金属服务器操作系统中代理的工具，在开机情况下可以通过该代理工具与服务器通信，从而可以实现裸金属服务器的相关热操作，如修改IP、修改密码、安装软件包等。

### 安装

#### 1. 证书下载

登录裸金属服务器执行以下命令来下载当前服务器的认证证书：

```shell
# curl -fsSL -o /usr/lib/bmstools/auth/private.pem https://capitalonline.net/bms/${bmId}/bmstools/certs/private
# curl -fsSL -o /usr/lib/bmstools/auth/public.pem https://capitalonline.net/bms/${bmId}/bmstools/certs/public
```

**注意：需将上述url中的${bmId}替换为当前裸金属服务器在GIC控制台的编号ID。**

若当前服务器不能访问外网，可以直接在本地将证书下载，并拷贝到服务器中/usr/lib/bmstools/auth目录中。

每台裸金属服务器会有独立的证书。证书若配置错误，如目录或文件名或内容不正确，bmstools客户端会认证失败，所有基于bmstools的服务将不可用。

#### 2. 安装bmstools

在裸金属服务器内执行如下命令：

```sh
# curl -fsSL -o bmstools.rpm https://capitalonline.net/bms/soft/bmstools.rpm
# rpm -ivh bmstools.rpm
# systemctl start bmstools
# systemctl status bmstools
```

### 设计

#### 1. 通信方式

bmstools在底层是基于raw socket二层MAC+VLAN的方式进行通信的。在二层帧上我们自定义了一个二层协议**0x7fff**，用来识别专属于bmstools服务的收发数据包。在二层帧的基础上，我们封装了一套简单的通信协议，类似于TCP/IP协议，可以实现简单的数据分组、重组、重试等功能。

#### 2. 通信协议

在帧数据中的内容

```
  0               1               2               3
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
  |    ver (1)    |   ptype (1)   |           srckey (2)          |
  +---------------+---------------+---------------+---------------+
  |           dstkey(2)           |          sequence (4)         |
  +-------------------------------+-------------------------------+
  |          sequence (4)         |            count (2)          |
  +-------------------------------+-------------------------------+
  |            offset (2)         |              data             |
  +-------------------------------+-------------------------------+
```

ver： 协议版本，默认为1

ptype：包类型

   0：开启一个新session会话

   1：数据包

   2：Ack确认包

   3：控制包

   255：结束当前session

srckey：源会话key

dstkey：目的会话key

sequence：当前数据包的序列号

count：当前session数据分片数量

offset：当前包的分片偏移量， 一个session要发送的数据量可能会比较大，所以需要在二层帧中将数据分片。

data：当前包的数据，默认最大字节1500 - 12 - = 1488

该字段只有在ptype=1或ptype=3时才有用。如果ptype=3，那么该包为一个控制包，具体字段如下。如果不是，那么是数据包。

```
Control data
---------------

0               1               2               3
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|   ctype (1)   |                  length (4)                   |
+---------------------------------------------------------------+
|   length (4)  |                variable data                  |
+---------------------------------------------------------------+
```

ctype：控制包类型

  0：认证，公钥加密的随机数

  1：执行命令

  2：发送文件

length：控制包的数据字节长度

variable data：控制包中的数据

在一个session中，客户端会先发送一个控制包，表示当前session的具体操作。之后每个sequence的数据都是该操作的数据包。

### 限制

#### 1. 操作系统

由于当前底层通信方式使用raw socket技术，但是windows对raw socket支持不友好，所以暂时没有对windows系统做兼容，目前正在寻找替代方案。

已经过测试的操作系统：centos7.2、centos7.5、centos7.6、centos8、ubuntu16、ubuntu18、ubuntu20。

#### 2. 网络环境

当前bmstools是基于MAC+VLAN二层通信，所以底层的网络环境需要物理二层打通且基于VLAN隔离。