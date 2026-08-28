from cdflib import cdfwrite
from cdflib import cdfread
from pathlib import Path
import numpy as np
import tomli
import shutil
import concurrent.futures
"""
This script contains functions to: 
* Create a mastercdf from a template with new name/logical source, and update associated CDF attributes/variable names which match that logical source
* Update CDF metadata using an input argument
"""

def set_cdf_variable(cdf_variable:dict) -> dict:
    """
    Converts data_val data type/dtype based on cdf_datatype. If data_val is None, applies a default null value to the variable data.

    Inspired by _convert_nptype from cdflib.cdfwrite

    returns modified dict with corrected variable data dtype, pad value, and fillval
    """
    cdf_default_pad_values = {
        "CDF_UINT1":254, # 11
        "CDF_INT2":-32767, # 2
        "CDF_UINT2":65534, # 12
        "CDF_INT4":-2147483647, # 4
        "CDF_UINT4":4294967294, # 14
        "CDF_EPOCH":0.0, # 31
        "CDF_EPOCH16":[0.0, 0.0], #32
    }
    cdf_default_pad_values.update(dict.fromkeys(["CDF_BYTE", "CDF_INT1"], -127)) # 1, 41
    cdf_default_pad_values.update(dict.fromkeys(["CDF_INT8", "CDF_TIME_TT2000"], -9223372036854775807)) # 8, 33
    cdf_default_pad_values.update(dict.fromkeys(["CDF_REAL4","CDF_FLOAT","CDF_REAL8","CDF_DOUBLE"], -1.0e30)) # 21, 44, 22, 45
    cdf_default_pad_values.update(dict.fromkeys(["CDF_CHAR", "CDF_UCHAR"]," ")) # 51, 52
    
    # after matching the variable datatype, set appropriate variable datatype, pad value, and fillval
    if cdf_variable["VarInfo"]["Data_Type"] in [51,52]:
        cdf_variable["VarInfo"]["Pad"]=str(cdf_default_pad_values[cdf_variable["VarInfo"]["Data_Type_Description"]])
    elif cdf_variable["VarInfo"]["Data_Type"] in [21,44,22,45,31,32]:
        cdf_variable["VarInfo"]["Pad"]=float(cdf_default_pad_values[cdf_variable["VarInfo"]["Data_Type_Description"]])
    else: 
        cdf_variable["VarInfo"]["Pad"]=int(cdf_default_pad_values[cdf_variable["VarInfo"]["Data_Type_Description"]])

    if "FILLVAL" in cdf_variable["VarAttrs"].keys():
        if cdf_variable["VarAttrs"]["FILLVAL"] is None:
            if cdf_variable["VarInfo"]["Data_Type"] in [21,44,22,45,31,32]:
                cdf_variable["VarAttrs"]["FILLVAL"] = np.array([np.nan])
            else:
                cdf_variable["VarAttrs"]["FILLVAL"] = np.array([cdf_variable["VarInfo"]["Pad"]])
        else:
            if isinstance(cdf_variable["VarAttrs"]["FILLVAL"],list):
                cdf_variable["VarAttrs"]["FILLVAL"] = np.array(cdf_variable["VarAttrs"]["FILLVAL"])
            elif not isinstance(cdf_variable["VarAttrs"]["FILLVAL"],np.ndarray):
                cdf_variable["VarAttrs"]["FILLVAL"] = np.array([cdf_variable["VarAttrs"]["FILLVAL"]])

    if cdf_variable["VarInfo"]["Last_Rec"] >= 0:
        if cdf_variable["VarData"] is None:
            if "FILLVAL" in cdf_variable["VarAttrs"].keys():
                cdf_variable["VarData"] = cdf_variable["VarAttrs"]["FILLVAL"]
            else:
                if cdf_variable["VarInfo"]["Data_Type"] in [21,44,22,45,31,32]:
                    cdf_variable["VarData"] = np.array([np.nan])
                else:
                    cdf_variable["VarData"] = np.array([cdf_variable["VarInfo"]["Pad"]])
        else:
            if isinstance(cdf_variable["VarData"],list):
                cdf_variable["VarData"] = np.array(cdf_variable["VarData"])
            elif not isinstance(cdf_variable["VarData"],np.ndarray):
                cdf_variable["VarData"] = np.array([cdf_variable["VarData"]])

    match cdf_variable["VarInfo"]["Data_Type"]:
        case 1 | 41:
            dtype_toset = np.int8            
        case 2:
            dtype_toset = np.int16 
        case 4: 
            #dtype_toset = np.int32 
            dtype_toset = np.int64 
        case 8 | 33:
            dtype_toset = np.int64 
        case 11:
            dtype_toset = np.uint8 
        case 12:
            dtype_toset = np.uint16
        case 14:
            dtype_toset = np.uint32
        case 21 | 44:
            #dtype_toset = np.float32
            dtype_toset = np.float64
        case 22 | 45 | 31:
            dtype_toset = np.float64
        case 32:
            dtype_toset = np.complex128
        case 51 | 52:
            dtype_toset = np.str_
        case _:
            raise ValueError(f"ERROR! Variable Datatype not recognized. Please check variable: {cdf_variable["VarInfo"]["Variable"]}")
    for attrname in ["FILLVAL","VALIDMIN","VALIDMAX"]:
        if attrname in cdf_variable["VarAttrs"].keys():
            cdf_variable["VarAttrs"][attrname] = dtype_toset(cdf_variable["VarAttrs"][attrname])        
    if cdf_variable["VarInfo"]["Last_Rec"] >= 0:
        if dtype_toset == np.str_:
            # Instead, encode as utf-8:
            str_array=cdf_variable["VarData"]
            np.strings.encode(cdf_variable["VarData"], encoding='utf-8')
            cdf_variable["VarData"]=str_array
        else:
            cdf_variable["VarData"] = dtype_toset(cdf_variable["VarData"])
    return cdf_variable    

def dict_equals(
        dict1:dict,
        dict2:dict,
        name1:str,
        name2:str,
        verbose:bool=False):
    """
    Recursively identifies differences between two dicts

    Parameters
    ----------
    verbose : bool

    """
    abort_comp = False
    if len(set(dict1.keys())-set(dict2.keys())) > 0:
        if verbose:
            print(f"The following keys from {name1} are absent from {name2}:")
            for key in set(dict1.keys())-set(dict2.keys()):
                print(key)
        abort_comp = True
    if len(set(dict2.keys())-set(dict1.keys())) > 0:
        if verbose:
            print(f"The following keys from {name2} are absent from {name1}:")
            for key in set(dict2.keys())-set(dict1.keys()):
                print(key)
        abort_comp = True
    if abort_comp:
        return False
    else:
        dict_keys = dict1.keys()
        for dict_key in dict_keys:
            val_1 = dict1[dict_key]
            val_2 = dict2[dict_key]
            if type(val_1) != type(val_2):
                #if not (dict_key in key_ignore_none and (dict1[dict_key] is None or dict2[dict_key] is None)):        
                print(f"Type mismatch between {name1}[\"{dict_key}\"] and {name2}[\"{dict_key}\"].")
                if verbose:
                    print(f">> Type of {name1}[\"{dict_key}\"]: {type(dict1[dict_key])}")
                    print(f">> Type of {name2}[\"{dict_key}\"]: {type(dict2[dict_key])}")
                return
            # Value types should be the same
            match val_1:
                case dict():
                    if not dict_equals(
                        val_1,
                        val_2,
                        f"{name1}[\"{dict_key}\"]",
                        f"{name2}[\"{dict_key}\"]",
                        verbose):
                        abort_comp = True
                case list():
                    if not (len(val_1) == len(val_2) == 0):
                        if val_1 != val_2:
                            #if not (dict_key in key_ignore_none and (dict1[dict_key] is None or dict2[dict_key] is None)):        
                            if len(val_1) != len(val_2):
                                print(f"List mismatch between {name1}[\"{dict_key}\"] and {name2}[\"{dict_key}\"]")
                                print(f">> List values have differing length: {name1}[\"{dict_key}\"] and {name2}[\"{dict_key}\"]")
                                abort_comp = True
                            else:   
                                if all([isinstance(x,dict) for x in val_1]) and all([isinstance(x,dict) for x in val_2]):
                                    # types of val_1 and val_2 are list[dict], (likely attributes list) so they cannot simply be sorted
                                    # convert to list of tuples and use set comparison instead:
                                    val_1_list_tuple=[]
                                    for element in val_1:
                                        for key in element.keys():
                                            val_1_list_tuple.append((key,element[key]))
                                    val_2_list_tuple=[]
                                    for element in val_2:
                                        for key in element.keys():
                                            val_2_list_tuple.append((key,element[key]))
                                    if set(val_1_list_tuple) != set(val_2_list_tuple):
                                        print(f"List mismatch; differing elements found between {name1}[\"{dict_key}\"] and {name2}[\"{dict_key}\"]")
                                        abort_comp = True
                                else:
                                    # lengths should be the same; check for set equivalency:
                                    val_set_1 = val_1.sort()
                                    val_set_2 = val_2.sort()
                                    if val_set_1 != val_set_2:
                                        # the sets are not just reordered; they have different elements
                                        print(f"List mismatch between {name1}[\"{dict_key}\"] and {name2}[\"{dict_key}\"]")
                                        n_diff = 0
                                        for i in range(len(dict1[dict_key])):
                                            if val_1[i] != val_2[i]:
                                                n_diff+=1
                                        print(f">> Found {n_diff} differences out of {len(val_1)} elements.") 
                                        abort_comp = True                                        
                case np.ndarray():
                    if val_1.dtype.name != val_2.dtype.name:
                        print(f"NDArray dtype mismatch between {name1}[\"{dict_key}\"] and {name2}[\"{dict_key}\"]")
                        if verbose:
                            print(f">> dtype of {name1}[\"{dict_key}\"]: {val_1.dtype.name}")
                            print(f">> dtype of {name2}[\"{dict_key}\"]: {val_2.dtype.name}")
                        abort_comp = True
                    elif val_1.dtype.name[0:3] != 'str':
                        if not np.array_equal(val_1,val_2,equal_nan=True):
                            if verbose:
                                print(f">> Value of {name1}[\"{dict_key}\"]: {dict1[dict_key]}")
                                print(f">> Value of {name2}[\"{dict_key}\"]: {dict2[dict_key]}")
                            abort_comp = True
                    else: 
                        if not np.array_equal(val_1,val_2):
                            print(f"NDArray string mismatch between {name1}[\"{dict_key}\"] and {name2}[\"{dict_key}\"]")
                            if verbose:
                                print(f">> Value of {name1}[\"{dict_key}\"]: {dict1[dict_key]}")
                                print(f">> Value of {name2}[\"{dict_key}\"]: {dict2[dict_key]}")
                            abort_comp = True
                case _:
                    if val_1 != val_2:
                        #if not (dict_key in key_ignore_none and (dict1[dict_key] is None or dict2[dict_key] is None)):                        
                        print(f"Value mismatch between {name1}[\"{dict_key}\"] and {name2}[\"{dict_key}\"]")
                        if verbose:
                            print(f">> Value of {name1}[\"{dict_key}\"]: {dict1[dict_key]}")
                            print(f">> Value of {name2}[\"{dict_key}\"]: {dict2[dict_key]}")
                        abort_comp = True                    
    if abort_comp:
        return False
    return True

def dict_number_pair(dict_to_convert:dict) -> dict:
    """
    For each key in dict_to_listify, convert value to list containing value instead
    """
    for key in dict_to_convert.keys():
        if type(dict_to_convert[key]) is not dict:
            key_val_dict = {0:""}
            if isinstance(dict_to_convert[key],list):
                for i in range(len(dict_to_convert[key])):
                    key_val_dict[i]=dict_to_convert[key][i]
            else:
                key_val_dict[0] = dict_to_convert[key]
            dict_to_convert[key] = key_val_dict
    return dict_to_convert

def cdf_get_struct(cdf_path:Path,cdf_path_override:Path | None = None,skip_var_cast:bool = False) -> dict:
    """
    Reads CDF file and writes contents into a CDF dictionary. Mimics the output of cdf_readcdf in IDL. Assumes all variables are zvariables.
    
    Creates a dictionary of the form:
    cdf_metadata = {
        "CDFInfo": CDFInfo()
        "GlobalAttrs": dict
        "Variables": {
            "VARNAME": {
                "VarInfo": VDRInfo(),
                "VarAttrs": dict,
                "VarData": Union[str, np.ndarray]
                "VDRInfo": VDR
            }
        }
    }
    The "CDFInfo" key contains the output of cdf_info() and can be used for writing new CDFs
    The "GlobalAttrs" key contains the output of globalattsget()
    The "Variables" dict contains keys where each key is a variable name and corresponds to a dict containing "VarInfo" (containing the output of varinq()), "VarAttrs" (containing the output of varattsget()), and "VarData" (containing the output of varget())
    """
    with cdfread.CDF(str(cdf_path)) as cdf:
        #cdf=cdfread.CDF(str(cdf_path))
        cdf_metadata={
            # TODO rework to avoid using __dict__
            "CDFInfo":(cdf.cdf_info()).__dict__,
            "GlobalAttrs":dict_number_pair(cdf.globalattsget()),
            "Variables":{}
        }
        for zvar in cdf_metadata["CDFInfo"]["zVariables"]:
            var_dict = {}
            # TODO rework to avoid using __dict__
            var_dict["VarInfo"] = (cdf.varinq(zvar)).__dict__
            var_dict["VarAttrs"] = cdf.varattsget(zvar)
            try:
                var_dict["VarData"] = cdf.varget(zvar)
            except ValueError:
                var_dict["VarData"] = None
            # Update variable dict to enforce correct datatypes, pad value, and fillval
            if not skip_var_cast:
                cdf_metadata["Variables"][zvar] = set_cdf_variable(var_dict)
            else:
                cdf_metadata["Variables"][zvar] = var_dict
    if cdf_metadata["GlobalAttrs"]["Logical_file_id"][0] == " ":
        # Logical File ID should just be the file name without the file type extension
        print(f"WARNING: Loaded CDF structure has empty Logical File ID! Using filepath stem: {cdf_metadata["CDFInfo"]["CDF"].stem}")
        cdf_metadata["GlobalAttrs"]["Logical_file_id"][0] = cdf_metadata["CDFInfo"]["CDF"].stem
    if cdf_path_override is not None:
        cdf_metadata["CDFInfo"]["CDF"] = cdf_path_override
    return cdf_metadata

def cdf_update_struct(cdf_struct:dict,updates:dict) -> dict:
    """
    Update CDF dictionary recursively using update instructions. Returns updated CDF dictionary.
    """
    
    for update_action in updates.keys():
        update_action_obj=updates[update_action]
        match update_action:
            case "update_logicalsource":
                # queues a bunch of updates and calls cdf_update_struct recursively.
                old_logicalsource=cdf_struct["GlobalAttrs"]["Logical_source"][0]
                new_logicalsource=update_action_obj
                new_changes = {
                    "update_attr":{"global":{}},
                    "rename_var":{}
                }
                new_changes["update_attr"]["global"].update({"Logical_source":new_logicalsource})

                if cdf_struct["GlobalAttrs"]["Logical_file_id"][0] == " ":
                    # should not be reached since cdf_struct load routine generates one if it's blank 
                    raise ValueError("Logical file ID is blank!")
                if old_logicalsource in cdf_struct["GlobalAttrs"]["Logical_file_id"][0]:
                    id_suffix = (cdf_struct["GlobalAttrs"]["Logical_file_id"][0].split(old_logicalsource))[-1]
                    new_changes["update_attr"]["global"].update({"Logical_file_id":new_logicalsource+id_suffix})
                # Remove level from logical source before checking variable names:
                var_format=old_logicalsource
                new_var_format=new_logicalsource
                if "l2_" in old_logicalsource:
                    var_format="".join(old_logicalsource.split("l2_",1))
                if "l2_" in new_logicalsource:
                    new_var_format="".join(new_logicalsource.split("l2_",1))
                for var in cdf_struct["Variables"].keys():
                    # Check if a variable is formatted like the logical source, excluding the level
                    if var_format in var:
                        var_suffix = (var.split(var_format))[-1] # should contain _unit, _labl, _epoch, etc...
                        new_changes["rename_var"].update({var:new_var_format+var_suffix}) # reconstructs the variable using the new logical source excluding the level and tacking the suffix on at the end
                    elif len(var) >= 9:
                        # If variable is a component of the B field, apply additional changes:
                        if var[0:9] in ["thg_magh_","thg_magd_","thg_magz_"]:
                            var_suffix = (var.split(var[0:9]))[-1] # should be station code + time resolution (if present)
                            # Remove "thg_mag_" from the new var format
                            new_var_format_suffix=(new_var_format.split("thg_mag_"))[-1]
                            if var_suffix in new_var_format_suffix:
                                new_changes["rename_var"].update({var:var[0:9]+new_var_format_suffix})
                            else:
                                raise ValueError("Component variable name doesn't match logical source.")
                cdf_struct = cdf_update_struct(cdf_struct,new_changes)
            case "rename_var":
                rename_dict = update_action_obj
                new_changes = {
                    "remove_var":[],
                    "update_var":{},
                    "update_var_dependencies":rename_dict
                }
                for var_oldname in rename_dict.keys():
                    var_newname = rename_dict[var_oldname]
                    if cdf_struct["Variables"].get(var_oldname) is not None:
                        old_var_value=cdf_struct["Variables"][var_oldname]
                        new_changes["remove_var"].append(var_oldname)
                        new_changes["update_var"].update({var_newname:old_var_value})
                    else:
                        print(f"Variable name \"{var_oldname}\" not found in CDF variables; check if variable as already been renamed")
                # Update CDFInfo:
                renamed_vars=rename_dict.copy()
                # Include variable names which are not changed (value and key are the same):
                for v in cdf_struct["CDFInfo"]["zVariables"]:
                    renamed_vars.setdefault(v,v)
                # Write updated names to a list, preserving order of original zvariables list:
                new_zVar_list = [renamed_vars[v] for v in cdf_struct["CDFInfo"]["zVariables"]]
                cdf_struct["CDFInfo"]["zVariables"] = new_zVar_list
                # Call cdf_update_struct recursively to apply variable and variable attribute changes:
                cdf_struct = cdf_update_struct(cdf_struct,new_changes)
            case "update_var_dependencies":
                dep_updates_dict = update_action_obj
                new_changes = {
                    "update_attr":{}
                }
                for varname in cdf_struct["Variables"].keys():
                    var_attrs = cdf_struct["Variables"][varname]["VarAttrs"]
                    # check variable attributes for dependencies:
                    var_attrs_str_vals = [v for v in var_attrs.values() if type(v) is str]
                    outdated_dependencies = list(set(dep_updates_dict.keys()) & set(var_attrs_str_vals))
                    if len(outdated_dependencies) > 0:
                        new_changes["update_attr"].update({varname:{}})
                        # variable contains dependency in its attributes    
                        for attr in var_attrs.keys():
                            if type(var_attrs[attr]) is str:
                                new_dep_val = dep_updates_dict.get(var_attrs[attr])
                                if new_dep_val is not None:
                                    new_changes["update_attr"][varname].update({attr:new_dep_val})
                cdf_struct = cdf_update_struct(cdf_struct,new_changes)
            case "rename_attr":
                new_changes = {
                    "update_attr":{},
                    "remove_attr":{}
                    }
                for scope in update_action_obj.keys():
                    new_changes["update_attr"].update({scope:{}})
                    new_changes["remove_attr"].update({scope:[]})
                    for attr_oldname in update_action_obj[scope].keys():
                        match scope:
                            case "global":
                                attr_dict = dict_number_pair(cdf_struct["GlobalAttrs"].get(attr_oldname))
                            case _:
                                # assume scope is variable
                                attr_dict = cdf_struct["Variables"][scope]["VarAttrs"].get(attr_oldname)
                        if attr_dict is not None:
                            new_changes["update_attr"][scope].update({update_action_obj[scope][attr_oldname]:attr_dict})
                            new_changes["remove_attr"][scope].append(attr_oldname)
                cdf_struct = cdf_update_struct(cdf_struct,new_changes)
            case "append_attr":
                new_changes = {}
                for scope in update_action_obj.keys():
                    for attr_name in update_action_obj[scope]:
                        match scope:
                            case "global":
                                attr_val = cdf_struct["GlobalAttrs"].get(attr_name)
                            case _:
                                attr_val = cdf_struct["Variables"][scope]["VarAttrs"].get(attr_name)
                        if type(attr_val) is not list:
                            attr_val = [attr_val]
                        attr_vals_toappend = update_action_obj[scope].get(attr_name)
                        if type(attr_vals_toappend) is not list:
                            attr_vals_toappend = [attr_vals_toappend]
                        for item_to_append in attr_vals_toappend:
                            attr_val.append(item_to_append)
                        new_changes["update_attr"][scope].update({attr_name:attr_val})
                cdf_struct = cdf_update_struct(cdf_struct,new_changes)
            case "update_var":
                cdf_struct["Variables"].update(update_action_obj)
            case "remove_var":
                for var_to_remove in update_action_obj:
                    cdf_struct["Variables"].pop(var_to_remove)
            case "update_attr":
                for scope in update_action_obj.keys():
                    match scope:
                        case "global":
                            cdf_struct["GlobalAttrs"].update(dict_number_pair(update_action_obj[scope]))
                        case _:
                            cdf_struct["Variables"][scope]["VarAttrs"].update(update_action_obj[scope])
            case "remove_attr":
                for scope in update_action_obj.keys():
                    for attr_name in update_action_obj[scope]:
                        match scope:
                            case "global":
                                cdf_struct["GlobalAttrs"].pop(attr_name)
                            case _:
                                cdf_struct["Variables"][scope]["VarAttrs"].pop(attr_name)
            case "update_CDFInfo_VarInfo":
                # Update CDFInfo Attributes:
                att_list_g=[]
                for ga_key in cdf_struct["GlobalAttrs"].keys():
                    # Update CDFInfo Global Attributes:
                    att_list_element = {ga_key:'Global'}
                    if att_list_element not in att_list_g:
                        att_list_g.append(att_list_element)
                att_list_v=[]
                for v in cdf_struct["Variables"].keys():
                    # for each variable, update the VarInfo Variable attribute to be the current name of the CDF variable:
                    cdf_struct["Variables"][v]["VarInfo"]["Variable"] = v
                    # Update CDFInfo Variable Attributes:
                    for va_key in cdf_struct["Variables"][v]["VarAttrs"].keys():
                        att_list_element = {va_key:'Variable'}
                        if att_list_element not in att_list_v:
                            att_list_v.append(att_list_element)
                cdf_struct["CDFInfo"]["Attributes"] = att_list_g + att_list_v
                # Reorder variables according to zvariables list:
                cdf_struct["Variables"] = {varname: cdf_struct["Variables"][varname] for varname in cdf_struct["CDFInfo"]["zVariables"]}
            case _:
                raise ValueError(f"ERROR: Update action {update_action} not recognized.")
    # Do one last check to make sure global attribute values are all indexed dictionaries:
    cdf_struct["GlobalAttrs"] = dict_number_pair(cdf_struct["GlobalAttrs"])
    # return cdf_struct:
    return cdf_struct

def validate_updates_dict(updates:dict):
    """
    Checks the keys and values of the updates dictionary against the requirements for cdf_update_struct.

    The updates dictionary has the following form:
    updates {        
        "rename_var": {
            "var_oldname":"var_newname"
        }
        "update_var":{
            "varname":var_dict
        }
        "rename_attr":{
            "global":{attr_oldname:attr_newname}
            "varname":{attr_oldname:attr_newname}
        }
        "update_attr":{
            "global":global_atts_dict
            "varname":var_atts_dict
        }
        "append_attr":{
            "global":global_atts_dict
            "varname":var_atts_dict
        }
        "remove_attr":{
            "global":global_atts_list
            "varname":var_atts_list
        }
        "update_logicalsource": "new_logicalsource_name"
        "remove_var":["varname1","varname2",...]
    }
    """
    def _checktype(name,value,type_to_enforce):
        if isinstance(value,type_to_enforce):
            return
        else:
            raise ValueError(f"{name} value is supposed to be of type: {type_to_enforce}")
    def _checkelementtype(name,elements,type_to_enforce):
        if all(isinstance(x, type_to_enforce) for x in elements):
            return
        else:
            raise ValueError(f"Every element of {name} is supposed to be of type: {type_to_enforce}")
    for keyname,value in updates.items():
        match keyname:
            case "rename_var":
                _checktype(keyname,value,dict)
                _checkelementtype(keyname,value.values(),str)
            case "update_var" | "rename_attr" | "update_attr" | "append_attr":
                _checktype(keyname,value,dict)
                _checkelementtype(keyname,value.values(),dict)
            case "remove_attr":
                _checktype(keyname,value,dict)
                _checkelementtype(keyname,value.values(),list)
            case "update_logicalsource":
                _checktype(keyname,value,str)
            case "remove_var":
                _checktype(keyname,value,list)
                _checkelementtype(keyname,value,str)
            case "update_CDFInfo_VarInfo":
                # type of value does not matter
                continue
            case _:
                raise ValueError(f"Update action not recognized: {keyname}")
    return

def cdf_generate(
        output_cdf_struct:dict,
        updates:dict = {}):
    """
    Takes a CDF dictionary, applies changes specified in the updates dictionary, and writes to the path specified within the CDF dictionary. If a file already exists which shares the same path, a copy is first made in a temporary processing directory.

    The new CDF file is loaded into a separate CDF dictionary, and a comparison is made between the CDF dictionary used the write the file and the CDF dictionary read from the file. If there is a difference detected, a list of differences are recorded, and the newly written CDF is removed. If a CDF with the same name had been moved to the temporary processing directory, is is then moved back to its original location. Finally, an error is thrown to stop the updating process.

    See validate_updates_dict for a description of how the updates dictionary should be formatted.
    """
    # Initialize updates dictionary if not passed. Otherwise, validate the updates dict to make sure it's formatted using the correct types.
    if updates is None:
        updates = {}
    else:
        validate_updates_dict(updates)
    updates.update({"update_CDFInfo_VarInfo":None})

    # Get target CDF path from the input CDF dictionary. 
    output_cdf_fp = output_cdf_struct["CDFInfo"]["CDF"]
    # Force the copyright attribute to match the created CDF:
    copy_right = (
        "\nCommon Data Format (CDF)\nhttps://cdf.gsfc.nasa.gov\n"
        + "Space Physics Data Facility\n"
        + "NASA/Goddard Space Flight Center\n"
        + "Greenbelt, Maryland 20771 USA\n"
        + "(User support: gsfc-cdf-support@lists.nasa.gov)\n"
    )
    output_cdf_struct["CDFInfo"]["Copyright"] = copy_right
    # Update the CDF dictionary using the updates dictionary
    output_cdf_struct = cdf_update_struct(output_cdf_struct,updates)

    # Check for duplicate attribute names (case insensitive)
    attr_list_lower = [list(attr_dict.keys())[0].lower() for attr_dict in output_cdf_struct["CDFInfo"]["Attributes"]]
    if len(attr_list_lower) != len(set(attr_list_lower)):
        raise AssertionError(f"{output_cdf_fp.name} has a duplicate attribute name in CDF structure! Check case of attribute letters.")

    overwrite_CDF = False
    output_cdf_tmp_fp = Path("")
    # If the target CDF already exists, move it to the temporary directory for safekeeping.
    if output_cdf_fp.exists():
        overwrite_CDF = True
        # Make temporary directory to hold original file (if it already exists) while new file is being written and verified:
        thmsoc_python_root = Path(__file__).resolve().parent.parent.parent
        thmsoc_python_config = thmsoc_python_root / "thmsoc_python_config.toml"
        try:
            with open(thmsoc_python_config, "rb") as f:
                toml_dict = tomli.load(f)
                TEMPROOT = Path(toml_dict["paths"]["output_dataroot"])
        except FileNotFoundError:
            TEMPROOT = Path("/mydisks/home/thmsoc")
        tmp_proc_p = Path(f"{TEMPROOT}/tmp_cdf_updater")
        tmp_proc_p.mkdir(parents=True, exist_ok=True)
        # Make path for the original file in the temporary directory:
        output_cdf_tmp_fp = Path(f"{tmp_proc_p}/{output_cdf_fp.name}")
        # Remove any duplicates of the original file in temporary directory:
        output_cdf_tmp_fp.unlink(missing_ok=True)
        # Move existing file to temporary directory:
        #if is_file_opened(output_cdf_fp):
        #    raise ValueError("ERROR! file is already open!")
        shutil.move(src=output_cdf_fp,dst=output_cdf_tmp_fp)
    try:
        # Write new CDF file to target directory using updated CDF dictionary:
        with cdfwrite.CDF(path=output_cdf_fp,cdf_spec=output_cdf_struct["CDFInfo"],delete=True) as cdf_output:
            # Write Global attributes:
            cdf_output.write_globalattrs(globalAttrs=output_cdf_struct.get("GlobalAttrs"))
            # Write Variable attributes:
            for var in output_cdf_struct["Variables"].keys():
                cdf_output.write_var(
                    var_spec=output_cdf_struct["Variables"][var]["VarInfo"],
                    var_attrs=output_cdf_struct["Variables"][var]["VarAttrs"],
                    var_data=output_cdf_struct["Variables"][var]["VarData"])
            # Finally, close the newly written CDF: 
            cdf_output.close()
        print(f"{output_cdf_fp.name} has been generated! Validating...")
        # The updated CDF should currently be in the target directory
        # Verify update worked correctly; if update failed, delete new CDF in target directory and move old CDF back to target directory, if it existed:
        updated_cdf_struct = cdf_get_struct(output_cdf_fp)
        if dict_equals(output_cdf_struct,updated_cdf_struct,"output_cdf_struct","updated_cdf_struct",verbose=True):
            print(f"{output_cdf_fp.name} passed verification check!")
            # If original CDF was saved to the processing directory, it can now be removed
            if overwrite_CDF:
                print(f"Removing original copy of {output_cdf_fp.name} from temporary processing directory...")
                output_cdf_tmp_fp.unlink()
        else:
            raise ValueError(f"Generated {output_cdf_fp.name} failed verification check")    
        return
    except Exception as error:
        # Remove new file in target directory:
        output_cdf_fp.unlink()
        # If original CDF was saved to the processing directory, move it back to the target directory:
        if overwrite_CDF:
            shutil.move(
                src=output_cdf_tmp_fp,
                dst=output_cdf_fp)
        raise Exception(f"CDF Update Failed! Reason: {error.args[0]}. Removing temporary CDF file...")

def cdf_load_and_generate(outputcdf_fp:str | Path, mastercdf_fp:str | Path | None = None, updates:dict = {}):
    if isinstance(outputcdf_fp,str):
        outputcdf_fp=Path(outputcdf_fp)
    if outputcdf_fp.exists():
        print(f"{outputcdf_fp.name} exists; getting existing CDF structure...")
        # get outputcdf data
        cdf_output = cdf_get_struct(outputcdf_fp)
    else:
        print(f"{outputcdf_fp.name} does not exist; attempting to use mastercdf as template...")
        if mastercdf_fp is not None:
            if isinstance(mastercdf_fp,str):
                mastercdf_fp = Path(mastercdf_fp)
        else:
            raise ValueError("ERROR! Target CDF does not exist, but mastercdf_fp is not provided! Please provide a filepath to the mastercdf so that a CDF can be created from it.")
        if not mastercdf_fp.exists():
            raise ValueError("ERROR! mastercdf_fp does not point to a valid existing filepath! Please check that the mastercdf_fp is correct.")
        #print("Getting mastercdf struct...")
        cdf_master = cdf_get_struct(mastercdf_fp,cdf_path_override=outputcdf_fp)
        # set outputcdf data as mastercdf data
        cdf_output = cdf_master.copy()
    print(f"Generating new CDF for {outputcdf_fp.name}...")
    cdf_generate(
        output_cdf_struct=cdf_output,
        updates=updates)
    return

def cdf_updater(
        outputcdf_fp: str | Path | list[str | Path] | None = None,
        outputcdflist_fp: str | Path | None = None,
        mastercdf_fp: str | Path | None = None, 
        updates: dict = {},
        num_parallel_jobs: int = 1):
    """
    Generates one or more CDF file(s) by using an existing CDF (or mastercdf) file as a template, copying the CDF file's contents, and then by applying changes specified by a structure containing update instructions. Creates updated file in temporary directory to prevent file overwrites in the event of update errors. If no update errors detected, moves file from temporary directory to destination directory. 

    The target CDF file path \"outputcdf_fp\" is checked first to see if the file path points to an already existing file; the file exists, then the function attempts to re-create the target CDF file with the applied updates. If the target CDF file path does not point to an existing file, then a new file is created using the provided mastercdf filepath mastercdf_fp as a template.  

    First, it checks if the outputcdf_fp points to an already existing CDF file; if it does,  
    Set output_cdf_strs to mastercdf_str to update mastercdf in-place

    Parameters
    ----------
    outputcdf_fp : str | Path | list[str | Path] | None = None
        The output CDF file path(s). If string path or list of string paths is provided, attempts to parse string as Path object. If None, uses input CDF file path(s) as output CDF file path(s).
    outputcdflist_fp: str | Path | None = None
        A file containing the path to each output file, line separated. If set, overrides outputcdf_fp.
    mastercdf_fp : str | Path | None = None
        The mastercdf file path(s). If a string path is provided, attempts to parse string as Path object. 
    updates : dict
        The update instructions. If left as None, attempts to update the output CDFs using the mastercdf metadata, provided they share the same variables.

        The updates dictionary has a specific format (see validate_updates_dict), where each key is an update action and each value contains the parameters required for the update. Each update action is completed in the order they are defined.
    num_parallel_jobs : int = 1
        Specifies the max number of jobs to run in parallel; defaults to 1 if the provided value is less than 1
    """
    #try:
    output_filelist = []
    if outputcdflist_fp is None:
        # If output CDF path not provided, use mastercdf path instead
        if outputcdf_fp is None:
            print("Output CDF filepath not provided; updating mastercdf in-place instead...")
            if mastercdf_fp is not None:
                if isinstance(mastercdf_fp,str):
                    mastercdf_fp = Path(mastercdf_fp)
                    outputcdf_fp = mastercdf_fp
            else:
                # If neither CDF paths have been passed, throw error: 
                raise ValueError("ERROR! Either the mastercdf_fp or the outputcdf_fp must be provided!")
    else:
        if isinstance(outputcdflist_fp,str):
            outputcdflist_fp = Path(outputcdflist_fp)
        with open(outputcdflist_fp, 'r') as file:
            # Read all lines into a list
            output_filelist = file.readlines()
    # If output CDF path not passed as list, cast as list:
    if isinstance(outputcdf_fp,(str,Path)):
        output_filelist = [outputcdf_fp]
    if len(output_filelist) == 0:
        raise ValueError("Output list has no entries. The output paths were not set properly.")
    max_workers=1
    if (len(output_filelist) > 1) and (num_parallel_jobs > 1):
        max_workers = num_parallel_jobs
    print(f"Updating {len(output_filelist)} CDF(s) in {max_workers} job(s)...")
    if max_workers==1:
        for outputcdf_fp_current in output_filelist:
            cdf_load_and_generate(
                outputcdf_fp=outputcdf_fp_current,
                mastercdf_fp=mastercdf_fp,
                updates=updates)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures_iterable = [executor.submit(
                cdf_load_and_generate,
                outputcdf_fp=outputcdf_fp_current,
                mastercdf_fp=mastercdf_fp,
                updates=updates) for outputcdf_fp_current in output_filelist]
    print("Done!")
    return

if __name__ == "__main__":
    # Remove old mastercdf if it exists:
    mastercdf_dir = "C:/Users/DC/Documents/Projects/thmsoc_svn/src/mastercdfs/thg"
    path_lrv_old = f"{mastercdf_dir}/thg_l2_mag_lrv_00000000_v01.cdf"
    path_lrv_new = f"{mastercdf_dir}/thg_l2_mag_lrv_1min_00000000_v01.cdf"
    path_snkq_old = f"{mastercdf_dir}/thg_l2_mag_snkq_00000000_v01.cdf"
    path_snkq_new = f"{mastercdf_dir}/thg_l2_mag_snkq_1min_00000000_v01.cdf"

    Path(path_lrv_new).unlink(missing_ok=True)
    # Re-create it using cdf_updater:
    cdf_updater(
        mastercdf_fp=path_lrv_old, 
        outputcdf_fp=path_lrv_new, 
        updates={
            "update_logicalsource":"thg_l2_mag_lrv_1min",
            "update_attr":{
                "global":{
                    'Time_resolution':'1 minute',
                    'Generation_date':'20260827',
                    'spase_DatasetResourceID':' ',
                    'Logical_source_description':'Higher latitude chain (Lat 64.2, Long 338.3), Ground-based Vector Magnetic Field at Leirvogur, Iceland, 1 minute resolution data.',
                    'MODS':'Rev-2026-08-27 (dcarpenter): CDF template created.',
                    'TEXT':'Ground based observatory, affiliated with Science Institute, University of Iceland. Data is preliminary 1 minute resolution data.'   
                },
                "thg_mag_lrv_1min_compno":{
                    'CATDESC':'Array containing index of H (North), E (East), and Z (vertically down) magnetic field components.',
                    'FIELDNAM':'HEZ Component Number'
                },
                "thg_mag_lrv_1min_time":{
                    'CATDESC':'UTC time, measured in seconds, since 01-Jan-1970 00:00:00',
                    'FIELDNAM':'Time'
                }
            }
        })
    # Do the same for SNKQ
    Path(path_snkq_new).unlink(missing_ok=True)
    cdf_updater(
        mastercdf_fp=path_snkq_old, 
        outputcdf_fp=path_snkq_new,
        updates={
            "update_logicalsource":"thg_l2_mag_snkq_1min",
            "update_attr":{
                "global":{
                    'Time_resolution':'1 minute',
                    'Generation_date':'20260827',
                    'spase_DatasetResourceID':' ',
                    'Logical_source_description':'Higher latitude chain (Lat 56.5, Long 280.8), Ground-based Vector Magnetic Field at Sanikiluaq, Canada, 1 minute, CARISMA network',
                    'MODS':'Rev-2026-08-27 (dcarpenter): CDF template created.',
                    'TEXT':'THEMIS Ground Based Observatory part of the THEMIS GBO effort. Retrieved via NRCAN FDSN web service. Data transmitted via GOES Primary.'
                },
                'thg_magh_snkq_1min':{
                    'DISPLAY_TYPE':'time_series>y=thg_magh_snkq_1min(0)',
                },
                'thg_magd_snkq_1min':{
                    'DISPLAY_TYPE':'time_series>y=thg_magd_snkq_1min(0)',
                },
                'thg_magz_snkq_1min':{
                    'DISPLAY_TYPE':'time_series>y=thg_magz_snkq_1min(0)',
                }
            }
        })
    print("Loading new LRV structure:")
    lrv_struct = cdf_get_struct(cdf_path=Path(path_lrv_new))
    print("Loading new SNKQ structure:")
    snkq_struct = cdf_get_struct(cdf_path=Path(path_snkq_new))
    print("Main method done!")