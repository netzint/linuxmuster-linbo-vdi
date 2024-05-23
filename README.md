<h1 align="center">
    LINUXMUSTER Linbo VDI
</h1>

## Installation

### 1. Install linuxmuster-linbo-vdi package from netzint repository
```
apt-get install linuxmuster-linbo-vdi
```

### 2. Create start.conf.* like this
```
root@server:~# cat /srv/linbo/start.conf.win10-vdi
[LINBO]
Server = 10.0.0.1
Group = win10-vdi
Cache = /dev/sda2
RootTimeout = 600
AutoPartition = no
AutoFormat = no
AutoInitCache = no
DownloadType = torrent
GuiDisabled = no
UseMinimalLayout = no
Locale = de-de
SystemType = bios64
KernelOptions = quiet splash dhcpretry=9
School = default-school

[Partition]
Dev = /dev/sda1
Label = windows
Size = 70G
Id = 7
FSType = ntfs
Bootable = no

[Partition]
Dev = /dev/sda2
Label = cache
Size = 
Id = 83
FSType = ext4
Bootable = no

[OS]
Name = Windows 10
Version = 22H2
Description = Windows 10 1903
IconName = win10.svg
BaseImage = win10-22h2-pro-education.qcow2
Boot = /dev/sda1
Root = /dev/sda1
Kernel = auto
Initrd = 
Append = 
StartEnabled = yes
SyncEnabled = no
NewEnabled = yes
Autostart = yes
AutostartTimeout = 3
DefaultAction = start
Hidden = yes

```

### 3. Create start.conf.*.vdi like this
```
root@server:~# cat /srv/linbo/start.conf.win10-vdi.vdi
{
    "activated" : "yes",
    "vmids" : [1701],
    "bios" : "seabios",
    "boot" : "cn",
    "bootdisk" : "sata0,net0",
    "cores" : 4,
    "memory" : 4096,
    "ostype" : "win10",
    "name" : "lmn72.v001-master",
    "room" : "vdi",
    "hostname" : "vdi-master",
    "group" : "win10-vdi",
    "ip" : "10.0.0.50",
    "storage" : "local-zfs",
    "scsihw" : "virtio-scsi-pci",
    "size" : 120,
    "format" : "raw",
    "bridge" : "vmbr0",
    "tag" : 100,
    "mac" : "AA:EE:4E:B5:5C:00",
    "display" : "type=qxl,memory=16",
    "audio" : "device=ich9-intel-hda,driver=spice",
    "usb0" : "host=spice,usb3=1",
    "spice_enhancements" : "foldersharing=1,videostreaming=all",
    "minimum_vms" : 6,
    "maximum_vms" : 10,
    "prestarted_vms" : 1,
    "timeout_building_master" : 750,
    "timeout_building_clone" : 400
}
```

### 4. Update VDI Service configuration
```
root@server:~# cat /etc/linuxmuster/linbo-vdi/vdiConfig.json
{
    "node" : "hv01",
    "hvIp" : "10.0.8.10",
    "hvUser" : "root@pam",
    "password" : "Muster!",
    "nmapPorts" : "135,455,49665",
    "vdiLocalService" : true,
    "serverIP" : "10.0.0.1",
    "debugging" : true,
    "multischool": true,
    "timeoutConnectionRequest" : 1000,
    "proxy_url": "server.demo.multi.schule",
    "lmn-api-secret": "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
}
```

### 5. Create entries in devices.csv for master and clones like this
- Master MAC-Address should be the same in both config files!
- Set VMID in field 12!
- MAC-Addresses for clones you can set randomly
```
vdi;vdi-master;win10-vdi;AA:EE:4E:B5:5C:00;10.0.0.50;;;;classroom-studentcomputer;;1;;;;;
vdi;vdi-client01;win10-vdi;AA:EE:4E:B5:5C:01;10.0.0.201;;;;classroom-studentcomputer;;1;1801;;;;
vdi;vdi-client02;win10-vdi;AA:EE:4E:B5:5C:02;10.0.0.202;;;;classroom-studentcomputer;;1;1802;;;;
vdi;vdi-client03;win10-vdi;AA:EE:4E:B5:5C:03;10.0.0.203;;;;classroom-studentcomputer;;1;1803;;;;
vdi;vdi-client04;win10-vdi;AA:EE:4E:B5:5C:04;10.0.0.204;;;;classroom-studentcomputer;;1;1804;;;;
vdi;vdi-client05;win10-vdi;AA:EE:4E:B5:5C:05;10.0.0.205;;;;classroom-studentcomputer;;1;1805;;;;
vdi;vdi-client06;win10-vdi;AA:EE:4E:B5:5C:06;10.0.0.206;;;;classroom-studentcomputer;;1;1806;;;;
vdi;vdi-client07;win10-vdi;AA:EE:4E:B5:5C:07;10.0.0.207;;;;classroom-studentcomputer;;1;1807;;;;
vdi;vdi-client08;win10-vdi;AA:EE:4E:B5:5C:08;10.0.0.208;;;;classroom-studentcomputer;;1;1808;;;;
vdi;vdi-client09;win10-vdi;AA:EE:4E:B5:5C:09;10.0.0.209;;;;classroom-studentcomputer;;1;1809;;;;
vdi;vdi-client10;win10-vdi;AA:EE:4E:B5:5C:10;10.0.0.210;;;;classroom-studentcomputer;;1;1810;;;;
vdi;vdi-client11;win10-vdi;AA:EE:4E:B5:5C:11;10.0.0.211;;;;classroom-studentcomputer;;1;1811;;;;
vdi;vdi-client12;win10-vdi;AA:EE:4E:B5:5C:12;10.0.0.212;;;;classroom-studentcomputer;;1;1812;;;;
vdi;vdi-client13;win10-vdi;AA:EE:4E:B5:5C:13;10.0.0.213;;;;classroom-studentcomputer;;1;1813;;;;
vdi;vdi-client14;win10-vdi;AA:EE:4E:B5:5C:14;10.0.0.214;;;;classroom-studentcomputer;;1;1814;;;;
vdi;vdi-client15;win10-vdi;AA:EE:4E:B5:5C:15;10.0.0.215;;;;classroom-studentcomputer;;1;1815;;;;
vdi;vdi-client16;win10-vdi;AA:EE:4E:B5:5C:16;10.0.0.216;;;;classroom-studentcomputer;;1;1816;;;;
vdi;vdi-client17;win10-vdi;AA:EE:4E:B5:5C:17;10.0.0.217;;;;classroom-studentcomputer;;1;1817;;;;
vdi;vdi-client18;win10-vdi;AA:EE:4E:B5:5C:18;10.0.0.218;;;;classroom-studentcomputer;;1;1818;;;;
vdi;vdi-client19;win10-vdi;AA:EE:4E:B5:5C:19;10.0.0.219;;;;classroom-studentcomputer;;1;1819;;;;
vdi;vdi-client20;win10-vdi;AA:EE:4E:B5:5C:20;10.0.0.220;;;;classroom-studentcomputer;;1;1820;;;;
```

### 6. Prepare Image
- Allow Port 135, 445, 49665 over the Windows Firewall
- Install QEMU-Tools ans Spice-Guest-Tools

### 7. Create prestart file for image
/srv/linbo/images/win10-22h2-pro-education/win10-22h2-pro-education.prestart
```
# linuxmuster-linbo-vdi patch

if [[ $HOSTNAME == *"vdi"* ]]; then
  patch="/tmp/patch.reg"

  linbo_mount /dev/sda1 /mnt
  linbo_mount /dev/sda2 /cache

  sed 's|{\$HostName\$}|'"$HOSTNAME"'|g' /cache/*.reg > "$patch"

  linbo_patch_registry "$patch"

  rm -f "$patch"
fi
```

## CLI-Tools / API

### Status of clones

```
python3 /usr/lib/linuxmuster-linbo-vdi/getVmStates.py -clones 
```

```
curl --header "LMN-API-Secret: ABCDEFGHIJKLMNOPQRSTUVWXYZ" http://10.0.0.1:5555/api/status/clones
```

### Status of special clone

```
python3 /usr/lib/linuxmuster-linbo-vdi/getVmStates.py win10-vdi -clones 
```

```
curl --header "LMN-API-Secret: ABCDEFGHIJKLMNOPQRSTUVWXYZ" http://10.0.0.1:5555/api/status/clones/win10-vdi
```

### Status of masters

```
python3 /usr/lib/linuxmuster-linbo-vdi/getVmStates.py -master 
```

```
curl --header "LMN-API-Secret: ABCDEFGHIJKLMNOPQRSTUVWXYZ" http://10.0.0.1:5555/api/status/masters
```

### Status of special master

```
python3 /usr/lib/linuxmuster-linbo-vdi/getVmStates.py win10-vdi -master 
```

```
curl --header "LMN-API-Secret: ABCDEFGHIJKLMNOPQRSTUVWXYZ" http://10.0.0.1:5555/api/status/masters/win10-vdi
```

### Request connection for user

```
python3 /usr/lib/linuxmuster-linbo-vdi/getConnection.py win10-vdi netzint-teacher
```

```
curl -X POST --header "LMN-API-Secret: ABCDEFGHIJKLMNOPQRSTUVWXYZ" --header "Content-Type: application/json" --data '{"group":"win10-vdi","user":"netzint-teacher"}' http://localhost:5555/api/connection/request
```

#### Sample result
```
{"status":true,"data":{"ip":"10.0.0.201","configFile":"/tmp/vdi/start-vdi-20240522173736-EI32IT.vv"}}
```
