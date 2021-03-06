#!/bin/bash


declare -A dic

function parse_options()
{
    args=$(getopt -l change-ip,change-passwd,ip:,netmask:,vlan:,mac1:,mac2:,bond:,gateway::,user:,passwd:,help -- "$@")

    #echo formatted parameters=[$@]
    if [[ $1 == "--change-ip" ]];then
        while true
        do
            case $2 in
                --ip)
                    ip=$3
                    shift 2
                    ;;
                --netmask)
                    netmask=$3
                    shift 2
                    ;;
                --vlan)
                    vlan=$3
                    shift 2
                    ;;
                --gateway)
                    gw=$3
                    shift 2
                    ;;
                --mac1)
                    mac1=$3
                    shift 2
                    ;;
                --mac2)
                    mac2=$3
                    shift 2
                    ;;
                --bond)
                    bond=$3
                    shift 2
                    ;;
                --)
                    shift
                    break
                    ;;
                *)
                    break
                    ;;
            esac
        done
    elif [[ $1 == "--change-passwd" ]];then
        while true
        do
            case $2 in
                --user)
                    user=$3
                    shift 2
                    ;;
                --passwd)
                    passwd=$3
                    shift 2
                    ;;
                --)
                    shift
                    break
                    ;;
                *)
                    break
                    ;;
            esac
        done
        echo "${user}:${passwd}" | chpasswd
        if [[ $? -ne 0 ]];then
            echo "change passwd failed"
            exit 1
        fi
        exit 0
    fi
}

parse_options $@

Centos_identifier="/etc/redhat-release"
Ubuntu_identifier="/etc/issue"

Operating_system=1

function get_version(){
    if [ -f $Centos_identifier ]; then
        local_version=$(cat $Centos_identifier )

        if [[ $local_version == *"release 6"* ]];then
            echo "centos6"
        elif [[ $local_version == *"release 7"* ]];then
            echo "centos7"
        elif [[ $local_version == *"release 8"* ]];then
            echo "centos8"
        fi
    elif [ -f $Ubuntu_identifier ]; then
        local_version=$(cat $Ubuntu_identifier )
        if [[ $local_version == *"16"* ]];then
            echo "ubuntu16"
        elif [[ $local_version == *"18"* ]];then
            echo "ubuntu18"
        elif [[ $local_version == *"20"* ]];then
            echo "ubuntu20"
        fi
    fi
}

Operating_system=$(get_version)


function create_centos_vlan_conf(){
    conf_file=$1
    conf_dir="/etc/sysconfig/network-scripts/"
    vlan_card=$(echo ${conf_file} | cut -d'-' -f 2)
    card=$(echo ${vlan_card} | cut -d'.' -f 1)

    if [[ $gw != "" ]];then
cat > ${conf_dir}${conf_file} << EOF
BOOTPROTO=none
DEVICE=${card}
IPADDR=${ip}
NETMASK=${netmask}
ONBOOT=yes
PHYSDEV=${card}
TYPE=Ethernet
USERCTL=no
VLAN=yes
GATEWAY=${gw}
EOF
    else
cat > ${conf_dir}${conf_file} << EOF
BOOTPROTO=none
DEVICE=${card}
IPADDR=${ip}
NETMASK=${netmask}
ONBOOT=yes
PHYSDEV=${card}
TYPE=Ethernet
USERCTL=no
VLAN=yes
EOF
fi
}

function create_centols_bond_conf(){
    conf_file=$1
    conf_dir="/etc/sysconfig/network-scripts/"
    vlan_card=$(echo ${conf_file} | cut -d'-' -f 2)

cat > ${conf_dir}${conf_file} << EOF
BONDING_MASTER=yes
BONDING_OPTS="mode=active-backup miimon=100"
BONDING_SLAVE0=${dic[${mac1}]}
BONDING_SLAVE1=${dic[${mac2}]}
BOOTPROTO=none
DEVICE=${vlan_card}
ONBOOT=yes
TYPE=Bond
USERCTL=no
EOF

cat > ${conf_dir}ifcfg-${dic[${mac1}]} << EOF
BOOTPROTO=none
DEVICE=${mac1}
HWADDR=${dic[${mac1}]}
MASTER=${vlan_card}
ONBOOT=yes
SLAVE=yes
TYPE=Ethernet
USERCTL=no
EOF

cat > ${conf_dir}ifcfg-${dic[${mac2}]} << EOF
BOOTPROTO=none
DEVICE=${mac2}
HWADDR=${dic[${mac2}]}
MASTER=${vlan_card}
ONBOOT=yes
SLAVE=yes
TYPE=Ethernet
USERCTL=no
EOF

} 

function get_card(){
    eth_list=$(ls /sys/class/net)
    for card in $eth_list
    do
        eval bool=$(bool_file /sys/class/net/${card}/address)
        if [[ $bool -eq 1 ]];then
            mac=$(cat /sys/class/net/${card}/address)
            dic+=([$mac]=$card)
        fi
    done
}



function bool_file(){
    filepath=$1
    if [[ -f $filepath ]];then
        echo "1"
    fi
}

function sed_str(){
    conf_path=$1
    if [[ $gw != "" ]];then
        sed -i "/IPADDR/c\IPADDR=${ip}" ${conf_path} 
        sed -i "/NETMASK/c\NETMASK=${netmask}" ${conf_path} 
        sed -i "/GATEWAY/c\GATEWAY=${gw}" ${conf_path} 
    else
        sed -i "/IPADDR/c\IPADDR=${ip}" ${conf_path} 
        sed -i "/NETMASK/c\NETMASK=${netmask}" ${conf_path} 
    fi
}

function ubuntu_sed_str(){
    conf_path=$1
    local_ip=$2
    sed -i "s/${local_ip}/${ip}/" ${conf_path}
}


function up_card(){
    n=0
    for i in ${dic[*]}
    do
        ip link set $i up
        bool=$(bool_file "/sys/devices/virtual/net/$i")
        if [[ $bool -ne 1 ]];then
            ((n++))
        fi
    done
    echo $n
}

function conn(){
  result=$(ping -c 4 ${ip} | grep "100% packet loss")
  echo $result
}


function backup(){
    file_path=$1
    bak_dir=$2
    if [ ! -d $bak_dir ]; then
        mkdir $bak_dir
    fi
    cp -a $file_path ${bak_dir}
}

function c7_restart_net(){
    eth_bk=$1
    systemctl restart network
    state=$(systemctl status network|grep "active")
    if [[ $state != "" ]];then
        echo "change ip success"
    else
        rm -rf /etc/sysconfig/network-scripts/ifcfg-*
        cp -a $eth_bk/ifcfg-* /etc/sysconfig/network-scripts/
        systemctl restart networ
        exit 1
    fi
}

function c6_restart_net(){
    eth_bk=$1
    /etc/init.d/network restart
    state=$(/etc/init.d/network status|grep "active")
    if [[ $state != "" ]];then
        echo "change ip success"
    else
        rm -rf /etc/sysconfig/network-scripts/ifcfg-*
        cp -a $eth_bk/ifcfg-* /etc/sysconfig/network-scripts/
        /etc/init.d/network restart
        exit 1
    fi
}

function ubuntu_restart_net(){
    eth_bk=$1
    if [[ $Operating_system == "ubuntu16" ]];then
        /etc/init.d/networking restart
        if [[ $? -eq 0 ]];then
            echo "change ip success"
        else
            cp -a $eth_bk/50-cloud-init.cfg /etc/network/interfaces.d/
            /etc/init.d/networking restart
            exit 1
        fi
    elif [[ $Operating_system == "ubuntu18" ]];then
        netplan apply
        if [[ $? -eq 0 ]];then
            echo "change ip success"
        else
            cp -a $eth_bk/50-cloud-init.yaml /etc/netplan/
            netplan apply
            exit 1
        fi
    fi
}

function change_ip_ubuntu(){
    result=$(conn)
    if [[ $result == "" ]];then
        echo "ip already exists"
        exit 1
    fi
    curday=$(date '+%Y-%m-%d-%H-%M-%S')
    if [[ $Operating_system == "ubuntu16" ]];then
        conf_path="/etc/network/interfaces.d/50-cloud-init.cfg"
        backup ${conf_path} /tmp/${curday}_ethbk
        eval local_ip=$(grep -A3 "\.$vlan" $conf_path |  grep -w "address" | awk -F"[ /]+" '/address [0-9]/{print $3}')
    elif [[ $Operating_system == "ubuntu18" ]];then
        conf_path="/etc/netplan/50-cloud-init.yaml"
        backup ${conf_path} /tmp/${curday}_ethbk
        eval local_ip=$(grep -A5 "\.$vlan" $conf_path | awk '-F[-/ ]+' '/[0-9].[0-9].[0-9].[0-9]/ {print $2}')
    fi
    ubuntu_sed_str ${conf_path} ${local_ip}
    ubuntu_restart_net /tmp/${curday}_ethbk
}

function change_ip_c7(){
    result=$(conn)
    if [[ $result == "" ]];then
        echo "ip already exists"
        exit 1
    fi

    curday=$(date '+%Y-%m-%d-%H-%M-%S')
    backup "/etc/sysconfig/network-scripts/ifcfg-*"  /tmp/${curday}_ethbk
    get_card
    conf_dir="/etc/sysconfig/network-scripts/"
    eval conf_file=$(ls ${conf_dir} | grep ${vlan})
    conf_path=${conf_dir}${conf_file}
    if [[ $conf_file != "" ]];then
        sed_str ${conf_path}
    else
        bond0_vlan_num=$(ls ${conf_dir} | grep -w "ifcfg-bond0.[0-9]*" | wc -l)
        bond1_vlan_num=$(ls ${conf_dir} | grep -w "ifcfg-bond1.[0-9]*" | wc -l)
        card_num=$(lspci |grep -i eth | grep -v "Gigabit" | wc -l)
        bool_bond0=$(bool_file "/etc/sysconfig/network-scripts/ifcfg-bond0")
        bool_bond1=$(bool_file "/etc/sysconfig/network-scripts/ifcfg-bond1")
        bond_vlan_num=$(ls ${conf_dir} | grep -w "ifcfg-${bond}.[0-9]*" | wc -l)

        bool_vlan=$(bool_file "/etc/sysconfig/network-scripts/ifcfg-${bond}.${vlan}")
        bool_bond=$(bool_file "/etc/sysconfig/network-scripts/ifcfg-${bond}")
        up_num=$(up_card)
        #eval bool_bond0=$(echo ${dic[*]} | grep "bond0." )
        #if [[ $bool_bond0 != "" ]] && [[  != "" ]] ;then

        # With bond0, without bond0 VLAN 
        if [[ $bond_vlan_num -eq 0 ]] && [[ $bool_bond -eq 1 ]];then
            conf_file="ifcfg-${bond}.${vlan}"
            create_centos_vlan_conf $conf_file
        # Without bond0, without bond0 VLAN 
        elif [[ $bond_vlan_num -eq 0 ]] && [[ $bool_bond -ne 1 ]];then
            conf_file="ifcfg-${bond}.${vlan}"
            create_centols_bond_conf $conf_file
            create_centos_vlan_conf $conf_file
        fi
    fi
    if [[ $Operating_system == "centos7" ]];then
       c7_restart_net /tmp/${curday}_ethbk
    else
       c6_restart_net /tmp/${curday}_ethbk
    fi
}



function main(){
    if [[ $Operating_system == "centos7" ]] || [[ $Operating_system == "centos6" ]] || [[ $Operating_system == "centos8" ]];then
        change_ip_c7
    elif [[ $Operating_system == "ubuntu18" ]] || [[ $Operating_system == "ubuntu16" ]] ;then
        change_ip_ubuntu
    fi
}

main
