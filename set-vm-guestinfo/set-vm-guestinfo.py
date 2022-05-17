#!/usr/bin/env python

"""
Python program for managing advanced configuration parameters
"""

import fnmatch
from pathlib import Path
from pyVmomi import vim, vmodl # type: ignore
from tools import cli, service_instance, pchelper
from tools.tasks import wait_for_tasks


def main():
    """
    Program that can update guestinfo
    """

    parser = cli.Parser()
    parser.add_required_arguments(cli.Argument.VM_NAME)
    parser.add_custom_argument('--vcd-org', required=True, help='VCD Organization')
    parser.add_custom_argument('--encoded-metadata', required=True, help='The encoded metadata')
    parser.add_custom_argument('--encoded-userdata-file', required=True, help='The path to the encoded userdata')
    args = parser.get_args()

    try:

        # create the connection
        si = service_instance.connect(args)

        # Assumes the vcd-org name will be included in the resource pool
        # name. For example, when vcd-org (from vCloud) is something like
        # "some-org", the get_rp function will take that fragment and try
        # to find the actual resource pool name, which may be something
        # like "some-org (6a599705-6e7a-41cd-9c1d-214a87539aeb)"
        resource_pool = get_rp(si,  args.vcd_org)

        vm = get_vm(si, resource_pool, args.vm_name)

        encoded_userdata = Path(args.encoded_userdata_file).read_text()

        set_guestinfo(si, vm, args.encoded_metadata, encoded_userdata)

    except vmodl.MethodFault as error: # type: ignore
        print("Caught vmodl fault : " + error.msg)
    except Exception as error:
        print("Caught Exception : " + str(error))


def get_rp(si, rp_name_fragment):
    """
    Get a resource pool given a Resource Pool Name fragment
    """
    content = si.RetrieveContent()
    resource_pools = pchelper.get_all_obj(content, [vim.ResourcePool])

    try:
        for resource_pool in resource_pools:
            if fnmatch.fnmatch(resource_pool.name, f"{rp_name_fragment}*"):
                print(f"Found resource pool named {resource_pool.name}")
                return resource_pool
    except:
        print(f"Failed to find resource pool {rp_name_fragment}")
    raise Exception(f"Failed to find resource pool {rp_name_fragment}")


def get_vm(si, rp, vm_name_fragment):
    """
    Get a VM in a resource pool given a VM Name fragment
    """

    # Retreive the list of Virtual Machines from the inventory objects

    obj_view = None
    try:

        content = si.content

        obj_view = content.viewManager.CreateContainerView(rp,
                                                       [vim.VirtualMachine],
                                                       True)
        vm_list = obj_view.view

        for vm in vm_list:
            if fnmatch.fnmatch(vm.name, f"{vm_name_fragment}*"):
                print(f"Found VM named {vm.name} in resource pool named {rp.name}")
                return vm
    except:
        print(f"Failed to find VM named {vm_name_fragment}")
    finally:
        obj_view.Destroy()

    raise Exception(f"Failed to find VM named {vm_name_fragment}")


def set_guestinfo(si, vm, encoded_metadata, encoded_userdata):
    """
    Set advanced configuration guest info parameters
    """

    guestinfo = {
        "guestinfo.metadata": encoded_metadata,
        "guestinfo.metadata.encoding": "gzip+base64",
        "guestinfo.userdata": encoded_userdata,
        "guestinfo.userdata.encoding": "gzip+base64"
    }

    # first remove any existing guest info values
    remove_guestinfo(si, vm, guestinfo)

    # next, add the current guestinfo values to the current configuration
    current_extraConfig = vm.config.extraConfig

    for guest_info_key in guestinfo.keys():
        opt = vim.option.OptionValue()
        opt.key = guest_info_key
        opt.value = guestinfo[guest_info_key]
        current_extraConfig.append(opt)

    spec = vim.vm.ConfigSpec()
    spec.extraConfig = current_extraConfig

    task = vm.ReconfigVM_Task(spec)

    wait_for_tasks(si, [task])

    print("guestinfo properties have been set")


def remove_guestinfo(si, vm, guestinfo):
    """
    Remove advanced configuration guestinfo parameters
    """

    current_extraConfig = vm.config.extraConfig

    updated_extraConfig = {}

    # this loop goes through the current options in extraConfig
    # and creates a new dictionary which excludes anything in 
    # guest_info by setting the value of its key to empty string
    # then, the host will remove that particular key and value
    for optionValue in current_extraConfig:
        if optionValue.key in guestinfo:
            updated_extraConfig[optionValue.key] = ""
        else:
            updated_extraConfig[optionValue.key] = optionValue.value

    if any (key in updated_extraConfig for key in guestinfo):
        print("existing guestinfo found, removing it")
        
        spec = vim.vm.ConfigSpec()
        spec.extraConfig = []

        for k, v in updated_extraConfig.items():
            opt = vim.option.OptionValue()
            opt.key = k
            opt.value = v
            spec.extraConfig.append(opt)

        task = vm.ReconfigVM_Task(spec)

        wait_for_tasks(si, [task])

        print("guestinfo properties have been removed")

    else:
        print("no guestinfo properties found; nothing to remove")


# Start program
if __name__ == "__main__":
    main()