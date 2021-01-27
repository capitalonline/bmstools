Name:       bmstools
#版本号,一定要与tar包的一致
Version:    1.1.0
#释出号,也就是第几次制作RPM
Release:    3%{?dist}
#软件包简介,最好不要超过50个字符
Summary:    bmstools server

#组名,可以通过more /usr/share/doc/rpm-4.11.3/GROUPS 选择合适组
Group:      Development/Tools
#Redis为BSD
License:    GBLv2
##Redis官网
URL:        https://capitalonline.net
#定义用到的source,也可以直接写名字
Source0:    bmstools.conf
Source1:    bmstools
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

#制作过程中用到的软件包
BuildRequires: gcc
#软件运行的依赖包
Requires: bash

#软件包的描述
%description
Bmstools server

### 2. The Prep section: 准备阶段,主要目的解药source并cd
%prep                    #宏开始

### 3. The build section: 编译制作阶段,主要目的就是编译
%build

### 4. Install section: 安装阶段
%install
rm -rf %{buildroot}
install -p -D -m 755 %{SOURCE0} %{buildroot}/etc/init.d/bmstools
install -p -D -m 755 %{SOURCE1} %{buildroot}/usr/lib/bmstools/bmstools

### 4.1 Scripts section 没必要可以不写,表示脚本区域
#安装前执行的脚本
%pre
#$1有三个值，1表示安装,2表示升级,0表示卸载
if [ $1 == 1 ]; then
  mkdir -p /usr/lib/bmstools/auth
fi

if [ $1 == 2 ]; then
  /etc/init.d/bmstools stop
fi

#安装后执行的脚本
%post
if [ $1 == 1 ]; then
  chmod 755 /usr/lib/bmstools/bmstools
  chmod 775 /etc/init.d/bmstools
fi

#卸载前执行的脚本
%preun
if [ $1 == 0 ]; then
  /etc/init.d/bmstools stop
fi

#卸载后执行的脚本
%postun
if [ $1 == 0 ]; then
  rm -rf /etc/init.d/bmstools
fi

### 5 Clean section: 清理段,clean的主要作用就是删除BUILD
%clean
rm -rf %{buildroot}

### 6 File section: 文件列表段,这个阶段是把前面已经编译好的内容要打包了,其中exclude是指要排除什么不打包进来
%files
%defattr(-,root,root,0755)
/usr/lib/bmstools
#%attr后面的是权限,属主,数组
#%attr(0755,root,root) /etc/rc.d/init.d/redis
#%config表明是个配置文件,noreplace表明不能替换
%config(noreplace) /etc/init.d/bmstools

%changelog
