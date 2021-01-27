root@ubuntu:/opt# tree bmstools
bmstools
├── DEBIAN
│   ├── control
│   ├── postinst
│   ├── postrm
│   └── preinst
└── usr
    └── lib
        └── bmstools
            ├── auth
            └── bmstools

5 directories, 5 files
root@ubuntu:/opt#
root@ubuntu:/opt#
root@ubuntu:/opt#
root@ubuntu:/opt#
root@ubuntu:/opt#
root@ubuntu:/opt# cat bmstools/DEBIAN/control
Package: bmstools
Version: 1.1.0
Architecture: all
Maintainer: cds
Installed-Size:
Recommends:
Suggests:
Section: devel
Priority: optional
Multi-Arch: foreign
Description: bmstools server
root@ubuntu:/opt# cat bmstools/DEBIAN/postinst
#!/usr/bin/env bash
chmod 755 /usr/lib/bmstools/bmstools
chmod 755 /usr/lib/systemd/system/bmstools.service
root@ubuntu:/opt# cat bmstools/DEBIAN/postrm

root@ubuntu:/opt# cat bmstools/DEBIAN/preinst
#!/usr/bin/env bash

systemctl stop bmstools
bms_service="/usr/lib/systemd/system/bmstools.service"
if [[ ! -f $bms_service ]];then
cat > $bms_service << EOF
[Unit]
Description=bmstools service

[Service]
Restart=always
User=root
ExecStart=/usr/lib/bmstools/bmstools

[Install]
WantedBy=multi-user.target
EOF
fi
systemctl daemon-reload
