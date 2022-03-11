
#from globalValues import node,getSchoolId,proxmox
import paramiko
##node="pve01"
##vmid='410003'
##
##print(proxmox.nodes(node).qemu(vmid).delete())
#fileserver='file01'
#hv='192.168.99.10'
#commandSmbstatus='uptime'
#password = 'Muster!'
#
#with paramiko.SSHClient() as sshSmbstatus:
#    #ssh_key = paramiko.RSAKey.from_private_key_file("/root/.ssh/id_rsa")
#    sshSmbstatus.set_missing_host_key_policy(paramiko.AutoAddPolicy())
#    #sshSmbstatus.connect(fileserver)
#    sshSmbstatus.connect(hv, port=22, username='root')
#    #sshSmbstatus_stdin, sshSmbstatus_stdout, sshSmbstatus_stderr = sshSmbstatus.exec_command(commandSmbstatus)      
#    stdin, stdout, stderr = sshSmbstatus.exec_command("uptime")
#    print (stdout.readlines()) 


from proxmoxer import ProxmoxAPI

proxmox = ProxmoxAPI('192.168.99.10', user='root',  backend='ssh_paramiko')

