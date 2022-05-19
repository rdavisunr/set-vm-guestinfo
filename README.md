
# A Python program built to set a VM's extraConfig guestInfo properties

This program was built to workaround the [Terraform VMware Cloud Director Provider's][vcd] inability to set extraConfig guestInfo properties for vCloud VMs.

## Related Issues:

**Support setting guestInfo properties on extraConfig ([#822][i822])**

----

## Method

This program uses the [pyVmomi][pyvmomi] library to set the properties on guestInfo.

It can be packaged as a single executable using [PyInstaller][pyinst] and then called using a Terraform local-exec provisioner.

----

## Build ##

```
pipenv install --python "C:\Python38\python.exe"

pipenv shell

python build-pyinstaller.py
```

----

## Usage Examples 

A command line and Terraform example are provided.

### Command Line

```
Set-Location ".\dist"

# credentials
$user = "user"

$password = "password"

# the vcenter attached to the VCD
$vcenterServer = "server-address"

# VDC Organization
$vcdOrg = "vcd-org"

# name of the VM
$vmName = "vm-name"

# gzip+base64 encoded metadata
$metadata = "H4sIAPgThGIC/zTLsQqAMAwE0H/JbAZXt35KaAsW2qQkEQfx321Ft+Pd3QWUWmHsZHaKJthgRlg+PywrU8vDw4RiruSiY1DYnDhmLPMVesd1aJVIFXcx/29vcT8AAAD//wMAIYa2rGkAAAA="

# a path to a file with gzip+base64 encoded userdata;
# required because of the typical length of userdata (and the limitation for cmd line arg size)
$userdataFilePath = "C:\temp\userdata.txt"

./set-vm-guestinfo.py.exe -s $vcenterServer -nossl -u $user -p $password -v $vmName --vcd-org $vcdOrg --encoded-metadata $metadata --encoded-userdata-file "$userdataFilePath"
```

----

### Terraform (VCD Provider)

Parts of the configuration have been omitted or changed for brevity.

#### variables.tf

```
variable "vcenter_server" {
  description = "The server address for the vcenter attached to vcd"
}

variable "vcenter_username" {
  description = "The username for the account for sufficient access to the vcenter attached to vcd"
}

variable "vcenter_password" {
  description = "The password for the account with sufficient access to the vcenter attached to vcd"
  sensitive   = true
}

variable "vcd_org" {
  description = "The name of the VCD Organization"
}

variable "vm_name" {
  description = "The name for the VM"
}

variable "config_file_content" {
  description = "The encoded content that will be written as a file on the guest OS"
  type        = string
  default     = ""
}

variable "shell_script_content" {
  description = "The string content of the shell script that will be provided to the guest OS (bootstrapper script)"
  type        = string
  default     = ""
}

locals {

  # this data will be read by cloudbase-init's vmware guestinfo service
  # https://cloudbase-init.readthedocs.io/en/latest/services.html#vmware-guestinfo-service
  guestinfo_metadata = base64gzip(jsonencode({
    "instance-id" : var.vm_name,
    "local-hostname" : SomeComputerName,
    "admin-username" : Administrator,
    "admin-password" : SomePassword
  }))

  userdata_filename = "${path.module}/${var.vm_name}_userdata"
}

```

#### main.tf

```
# data that represents a cloudinit configuration
# separated into two parts:
# (1) cloud-config
#     (a) sets the time_zone
#     (b) writes the calling module provided content to the VM disk
# (2) calling module provided shell script (bootstrap)
data "template_cloudinit_config" "cloudinit" {
  gzip          = true
  base64_encode = true
  part {
    content_type = "text/cloud-config"
    content      = <<-EOF
      #cloud-config
      set_timezone: America/Los_Angeles
      write_files:
        - encoding: gzip+base64
          content: |
            ${var.config_file_content}
          path: C:\Destination
          permissions: 755
      EOF
  }
  part {
    filename     = bootstrap.ps1
    content_type = "text/x-shellscript"
    content      = var.shell_script_content
  }
}

# saves the rendered output of the template_cloudinit_config resource
# to a file. The userdata is typically large, so it can't be passed
# to the set_vm_guestinfo.py.exe scripts via environment variables or the cmd line
resource "local_file" "userdata_file" {
  content  = data.template_cloudinit_config.cloudinit.rendered
  filename = local.userdata_filename
}

# creates a vm in a vApp
resource "vcd_vapp_vm" "vapp_vm" {
  vapp_name = var.vapp_name
  name      = var.vm_name

  catalog_name  = var.catalog_name
  template_name = var.template_name

  cpus     = var.vm_cpus
  memory   = var.vm_memory * 1024
  power_on = var.power_on
}

resource "null_resource" "guestinfo" {
  depends_on = [vcd_vapp_vm.vapp_vm]

  # this command is idempotent
  provisioner "local-exec" {
    command     = "${path.module}/set-vm-guestinfo.py.exe -s ${var.vcenter_server} -nossl -u ${vcenter_username} -p {$vcenter_password} -v ${var.vm_name} --vcd-org ${var.vcd_org} --encoded-metadata ${local.guestinfo_metadata} --encoded-userdata-file ${local.userdata_filename}"
    interpreter = ["PowerShell", "-Command"]
  }
}

```

[vcd]: https://github.com/vmware/terraform-provider-vcd
[pyinst]: https://pyinstaller.org/en/stable/index.html
[pyvmomi]: https://github.com/vmware/pyvmomi
[i822]: https://github.com/vmware/terraform-provider-vcd/issues/822
